from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import respx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from dnstapir.key_resolver import FileKeyResolver, UrlKeyResolver


def test_file_key_resolver():
    key_id = "xyzzy"
    public_key = ed25519.Ed25519PrivateKey.generate().public_key()
    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    with TemporaryDirectory(prefix="dnstapir") as directory:
        pem_filename = Path(directory) / f"{key_id}.pem"
        with open(pem_filename, "wb") as fp:
            fp.write(public_key_pem)

        resolver = FileKeyResolver(client_database_directory=directory)
        res = resolver.resolve_public_key(key_id)
        assert res == public_key

        with pytest.raises(KeyError):
            _ = resolver.resolve_public_key("hostname.example.com")

        with pytest.raises(ValueError):
            _ = resolver.resolve_public_key("🔐")

        with pytest.raises(KeyError):
            _ = resolver.resolve_public_key("unknown")


def test_url_key_resolver(httpx2_mock: respx.Router):
    key_id = "xyzzy"
    public_key = ed25519.Ed25519PrivateKey.generate().public_key()
    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    httpx2_mock.get(f"https://keys/{key_id}.pem").respond(content=public_key_pem)
    httpx2_mock.get("https://keys/unknown.pem").respond(404)

    resolver = UrlKeyResolver(client_database_base_url="https://keys")
    res = resolver.resolve_public_key(key_id)
    assert res == public_key

    request = httpx2_mock.calls.last.request
    assert request.headers["Accept"] == "application/x-pem-file"

    with pytest.raises(ValueError):
        _ = resolver.resolve_public_key("🔐")

    with pytest.raises(KeyError):
        _ = resolver.resolve_public_key("unknown")


def test_url_key_resolver_pattern(httpx2_mock: respx.Router):
    key_id = "xyzzy"
    public_key = ed25519.Ed25519PrivateKey.generate().public_key()
    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    httpx2_mock.get(f"https://nodeman/api/v1/node/{key_id}/public_key").respond(content=public_key_pem)
    httpx2_mock.get("https://nodeman/api/v1/node/unknown/public_key").respond(404)

    resolver = UrlKeyResolver(client_database_base_url="https://nodeman/api/v1/node/{key_id}/public_key")
    res = resolver.resolve_public_key(key_id)
    assert res == public_key

    request = httpx2_mock.calls.last.request
    assert request.headers["Accept"] == "application/x-pem-file"

    with pytest.raises(KeyError):
        _ = resolver.resolve_public_key("unknown")


def test_url_bad_key_resolver_pattern():
    with pytest.raises(ValueError):
        _ = UrlKeyResolver(client_database_base_url="ftp://nodeman/api/v1/node/{key_id}/public_key")

    with pytest.raises(ValueError):
        _ = UrlKeyResolver(client_database_base_url="ftp://keys")


def test_url_key_resolver_contextlib(httpx2_mock: respx.Router):
    key_id = "xyzzy"
    public_key = ed25519.Ed25519PrivateKey.generate().public_key()
    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    httpx2_mock.get(f"https://keys/{key_id}.pem").respond(content=public_key_pem)
    httpx2_mock.get("https://keys/unknown.pem").respond(404)

    with UrlKeyResolver(client_database_base_url="https://keys") as resolver:
        res = resolver.resolve_public_key(key_id)
        assert res == public_key

    with pytest.raises(KeyError):
        _ = resolver.resolve_public_key("unknown")
