import logging
import re
from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx2
from cryptography.hazmat.primitives.asymmetric.types import PublicKeyTypes
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from opentelemetry import metrics, trace

from .key_cache import KeyCache

tracer = trace.get_tracer("dnstapir.tracer")
meter = metrics.get_meter("dnstapir.meter")

public_key_get_counter = meter.create_counter(
    "dnstapir.public_key_get_counter",
    description="The number of public key lookups",
)

public_key_resolve_counter = meter.create_counter(
    "dnstapir.public_key_resolve_counter",
    description="The number of public key resolutions",
)

KEY_ID_VALIDATOR = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-.]*$")


def key_resolver_from_client_database(client_database: str, key_cache: KeyCache | None = None):
    if client_database.startswith("http://") or client_database.startswith("https://"):
        return UrlKeyResolver(client_database_base_url=client_database, key_cache=key_cache)
    else:
        return FileKeyResolver(client_database_directory=client_database, key_cache=key_cache)


class KeyResolver(ABC):
    def __init__(self):
        self.logger = logging.getLogger(__name__).getChild(self.__class__.__name__)
        self.key_id_validator = KEY_ID_VALIDATOR

    @abstractmethod
    def resolve_public_key(self, key_id: str) -> PublicKeyTypes:
        pass

    def validate_key_id(self, key_id: str) -> None:
        if not self.key_id_validator.fullmatch(key_id):
            raise ValueError(f"Invalid key_id format: {key_id}")


class CacheKeyResolver(KeyResolver):
    def __init__(self, key_cache: KeyCache | None):
        super().__init__()
        self.key_cache = key_cache

    @abstractmethod
    def _get_public_key_pem(self, key_id: str) -> bytes:
        pass

    def resolve_public_key(self, key_id: str) -> PublicKeyTypes:
        self.validate_key_id(key_id)
        public_key_resolve_counter.add(1)
        with tracer.start_as_current_span("resolve_public_key"):
            if self.key_cache:
                public_key_pem = self.key_cache.get(key_id)
                if not public_key_pem:
                    public_key_pem = self._get_public_key_pem(key_id)
                    # Load the public key from PEM format before caching and returning it
                    res = load_pem_public_key(public_key_pem)
                    self.key_cache.set(key_id, public_key_pem)
                    public_key_get_counter.add(1)
                    return res
            else:
                public_key_pem = self._get_public_key_pem(key_id)
        return load_pem_public_key(public_key_pem)


class FileKeyResolver(CacheKeyResolver):
    def __init__(self, client_database_directory: str, key_cache: KeyCache | None = None):
        super().__init__(key_cache=key_cache)
        self.client_database_directory = client_database_directory

    def _get_public_key_pem(self, key_id: str) -> bytes:
        with tracer.start_as_current_span("get_public_key_pem_from_file"):
            filename = Path(self.client_database_directory) / f"{key_id}.pem"
            self.logger.debug("Fetching public key for %s from %s", key_id, filename)
            try:
                with open(filename, "rb") as fp:
                    return fp.read()
            except FileNotFoundError as exc:
                raise KeyError(key_id) from exc


class UrlKeyResolver(CacheKeyResolver):
    def __init__(self, client_database_base_url: str, key_cache: KeyCache | None = None):
        super().__init__(key_cache=key_cache)

        self.client_database_base_url = client_database_base_url
        self._httpx_client: httpx2.Client | None = None
        self.key_id_pattern = "{key_id}"

        if urlparse(self.client_database_base_url).scheme not in ("http", "https"):
            raise ValueError(f"Invalid URL: {self.client_database_base_url}")

        if self.key_id_pattern in self.client_database_base_url:
            test_url = self.client_database_base_url.replace(self.key_id_pattern, "test")
            if urlparse(test_url).scheme not in ("http", "https"):
                raise ValueError(f"Invalid URL pattern: {self.client_database_base_url}")

    def _get_public_key_pem(self, key_id: str) -> bytes:
        with tracer.start_as_current_span("get_public_key_pem_from_url"):
            if self.key_id_pattern in self.client_database_base_url:
                public_key_url = self.client_database_base_url.replace(self.key_id_pattern, key_id)
            else:
                public_key_url = urljoin(self.client_database_base_url, f"{key_id}.pem")

            if urlparse(public_key_url).scheme not in ("http", "https"):
                raise ValueError(f"Invalid URL constructed: {public_key_url}")

            self.logger.debug("Fetching public key for %s from %s", key_id, public_key_url)
            try:
                response = self.httpx_client.get(public_key_url)
                response.raise_for_status()
                return response.content
            except httpx2.HTTPError as exc:
                raise KeyError(key_id) from exc

    @property
    def httpx_client(self) -> httpx2.Client:
        if self._httpx_client is None:
            self._httpx_client = httpx2.Client(http2=True, headers={"Accept": "application/x-pem-file"})
        return self._httpx_client

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()

    def close(self):
        """Explicitly close the client and free resources."""
        if self._httpx_client is not None:
            try:
                self._httpx_client.close()
            finally:
                self._httpx_client = None
