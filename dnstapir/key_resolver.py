import logging
from abc import abstractmethod
from pathlib import Path
from urllib.parse import urljoin

import httpx
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicKey
from cryptography.hazmat.primitives.asymmetric.ed448 import Ed448PublicKey
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from opentelemetry import metrics, trace

from .key_cache import KeyCache

PublicKey = Ed25519PublicKey | Ed448PublicKey | EllipticCurvePublicKey | RSAPublicKey

tracer = trace.get_tracer("dnstapir.tracer")
meter = metrics.get_meter("dnstapir.meter")

public_key_get_counter = meter.create_counter(
    "aggregates.public_key_get_counter",
    description="The number of public key lookups",
)


def key_resolver_from_client_database(client_database: str, key_cache: KeyCache | None = None):
    if client_database.startswith("http://") or client_database.startswith("https://"):
        return UrlKeyResolver(client_database_base_url=client_database, key_cache=key_cache)
    else:
        return FileKeyResolver(client_database_directory=client_database, key_cache=key_cache)


class KeyResolver:

    def __init__(self):
        self.logger = logging.getLogger(__name__).getChild(self.__class__.__name__)

    @abstractmethod
    def resolve_public_key(self, key_id: str) -> PublicKey:
        pass


class CacheKeyResolver(KeyResolver):
    def __init__(self, key_cache: KeyCache | None):
        super().__init__()
        self.key_cache = key_cache

    @abstractmethod
    def get_public_key_pem(self, key_id: str) -> bytes:
        pass

    def resolve_public_key(self, key_id: str):
        with tracer.start_as_current_span("resolve_public_key"):
            if self.key_cache:
                public_key_pem = self.key_cache.get(key_id)
                if not public_key_pem:
                    public_key_pem = self.get_public_key_pem(key_id)
                    self.key_cache.set(key_id, public_key_pem)
                    public_key_get_counter.add(1)
            else:
                public_key_pem = self.get_public_key_pem(key_id)
        return load_pem_public_key(public_key_pem)


class FileKeyResolver(CacheKeyResolver):
    def __init__(self, client_database_directory: str, key_cache: KeyCache | None = None):
        super().__init__(key_cache=key_cache)
        self.client_database_directory = client_database_directory

    def get_public_key_pem(self, key_id: str) -> bytes:
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
        self._httpx_client: httpx.Client | None = None
        self.key_id_pattern = "%s"

    def get_public_key_pem(self, key_id: str) -> bytes:
        with tracer.start_as_current_span("get_public_key_pem_from_url"):
            if self.key_id_pattern in self.client_database_base_url:
                public_key_url = self.client_database_base_url.replace(self.key_id_pattern, key_id)
            else:
                public_key_url = urljoin(self.client_database_base_url, f"{key_id}.pem")
            self.logger.debug("Fetching public key for %s from %s", key_id, public_key_url)
            try:
                response = self.httpx_client.get(public_key_url)
                response.raise_for_status()
                return response.content
            except httpx.HTTPError as exc:
                raise KeyError(key_id) from exc

    @property
    def httpx_client(self) -> httpx.Client:
        if self._httpx_client is None:
            self._httpx_client = httpx.Client(headers={"Accept": "application/x-pem-file"})
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
