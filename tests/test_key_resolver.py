from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from pytest_httpx import HTTPXMock

from dnstapir.key_resolver import FileKeyResolver, UrlKeyResolver


def test_file_key_resolver(httpx_mock: HTTPXMock):
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
            _ = resolver.resolve_public_key("unknown")


def test_url_key_resolver(httpx_mock: HTTPXMock):
    key_id = "xyzzy"
    public_key = ed25519.Ed25519PrivateKey.generate().public_key()
    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    httpx_mock.add_response(url=f"https://keys/{key_id}.pem", content=public_key_pem)
    httpx_mock.add_response(url="https://keys/unknown.pem", status_code=404)

    resolver = UrlKeyResolver(client_database_base_url="https://keys")
    res = resolver.resolve_public_key(key_id)
    assert res == public_key

    with pytest.raises(KeyError):
        _ = resolver.resolve_public_key("unknown")


def test_url_key_resolver_pattern(httpx_mock: HTTPXMock):
    key_id = "xyzzy"
    public_key = ed25519.Ed25519PrivateKey.generate().public_key()
    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    httpx_mock.add_response(url=f"https://nodeman/api/v1/node/{key_id}/public_key", content=public_key_pem)
    httpx_mock.add_response(url="https://nodeman/api/v1/node/unknown/public_key", status_code=404)

    resolver = UrlKeyResolver(client_database_base_url="https://nodeman/api/v1/node/%s/public_key")
    res = resolver.resolve_public_key(key_id)
    assert res == public_key

    with pytest.raises(KeyError):
        _ = resolver.resolve_public_key("unknown")


def test_url_key_resolver_contextlib(httpx_mock: HTTPXMock):
    key_id = "xyzzy"
    public_key = ed25519.Ed25519PrivateKey.generate().public_key()
    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    httpx_mock.add_response(url=f"https://keys/{key_id}.pem", content=public_key_pem)
    httpx_mock.add_response(url="https://keys/unknown.pem", status_code=404)

    with UrlKeyResolver(client_database_base_url="https://keys") as resolver:
        res = resolver.resolve_public_key(key_id)
        assert res == public_key

    with pytest.raises(KeyError):
        _ = resolver.resolve_public_key("unknown")
