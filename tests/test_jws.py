import json
import logging

import respx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, mldsa
from cryptography.hazmat.primitives.asymmetric.types import PrivateKeyTypes
from jwcrypto.jwk import JWK
from jwcrypto.jws import JWS

from dnstapir.jws import ResolverJWKSet
from dnstapir.key_resolver import UrlKeyResolver


def _test_jws_verifier(httpx2_mock: respx.Router, private_key: PrivateKeyTypes, alg: str, protected_alg: bool = True):
    """Test JWS verifier"""

    logging.basicConfig(level=logging.DEBUG)

    # Create key
    key_id = "xyzzy"
    public_key = private_key.public_key()
    public_jwk = JWK.from_pyca(public_key)

    # Mock key server response
    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    httpx2_mock.get(f"https://keys/api/v1/node/{key_id}/public_key").respond(content=public_key_pem)

    # Create message
    payload = {"hello": "world"}
    client_jws = JWS(payload=json.dumps(payload))
    client_jws.add_signature(
        key=JWK.from_pyca(private_key),
        alg=alg,
        protected={"kid": key_id, "alg": alg} if protected_alg else {"kid": key_id},
        header={"alg": alg} if not protected_alg else None,
    )
    message = client_jws.serialize()

    # Set up key resolver
    client_database_base_url = "https://keys/api/v1/node/{key_id}/public_key"
    key_resolver = UrlKeyResolver(client_database_base_url=client_database_base_url)
    keyset = ResolverJWKSet(key_resolver=key_resolver)

    # Verify message (public key lookup via resolver)
    jws = JWS()
    jws.deserialize(message)
    verified_jwk = keyset.verify_jws(jws)
    assert verified_jwk.thumbprint() == public_jwk.thumbprint()


def test_jws_verifier_ed25519(httpx2_mock: respx.Router):
    """Test JWS verifier with Ed25519 and protected alg"""

    private_key = ed25519.Ed25519PrivateKey.generate()
    alg = "EdDSA"

    _test_jws_verifier(httpx2_mock=httpx2_mock, private_key=private_key, alg=alg, protected_alg=True)


def test_jws_verifier_ed25519_unprotected_alg(httpx2_mock: respx.Router):
    """Test JWS verifier with Ed25519 and unprotected alg"""

    private_key = ed25519.Ed25519PrivateKey.generate()
    alg = "EdDSA"

    _test_jws_verifier(httpx2_mock=httpx2_mock, private_key=private_key, alg=alg, protected_alg=False)


def test_jws_verifier_mldsa44(httpx2_mock: respx.Router):
    """Test JWS verifier with ML-DSA-44 and protected alg"""

    private_key = mldsa.MLDSA44PrivateKey.generate()
    alg = "ML-DSA-44"

    _test_jws_verifier(httpx2_mock=httpx2_mock, private_key=private_key, alg=alg, protected_alg=True)


def test_jws_verifier_complex(httpx2_mock: respx.Router):
    """Test JWS verifier with multiple signatures"""

    logging.basicConfig(level=logging.DEBUG)

    # Create key 1
    key_id1 = "xyzzy1"
    private_key1 = ed25519.Ed25519PrivateKey.generate()
    public_key1 = private_key1.public_key()
    public_jwk1 = JWK.from_pyca(public_key1)
    alg1 = "EdDSA"

    # Create key 2
    key_id2 = "xyzzy2"
    private_key2 = mldsa.MLDSA44PrivateKey.generate()
    public_key2 = private_key2.public_key()
    public_jwk2 = JWK.from_pyca(public_key2)
    alg2 = "ML-DSA-44"

    # Create message
    payload = {"hello": "world"}
    client_jws = JWS(payload=json.dumps(payload))
    client_jws.add_signature(key=JWK.from_pyca(private_key1), alg=alg1, protected={"kid": key_id1, "alg": alg1})
    client_jws.add_signature(key=JWK.from_pyca(private_key2), alg=alg2, protected={"kid": key_id2, "alg": alg2})
    message = client_jws.serialize()

    # Set up key resolver
    client_database_base_url = "https://keys/api/v1/node/{key_id}/public_key"
    key_resolver = UrlKeyResolver(client_database_base_url=client_database_base_url)
    keyset = ResolverJWKSet(key_resolver=key_resolver)

    # Mock key server responses (1st key available, 2nd key unavailable)
    httpx2_mock.get(f"https://keys/api/v1/node/{key_id1}/public_key").respond(
        content=public_key1.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    httpx2_mock.get(f"https://keys/api/v1/node/{key_id2}/public_key").respond(404)

    # Verify message (public key lookup via resolver)
    jws = JWS()
    jws.deserialize(message)
    verified_jwk = keyset.verify_jws(jws)
    assert verified_jwk.thumbprint() == public_jwk1.thumbprint()

    # Mock key server responses (1st key unavailable, 2nd key available)
    httpx2_mock.get(f"https://keys/api/v1/node/{key_id1}/public_key").respond(404)
    httpx2_mock.get(f"https://keys/api/v1/node/{key_id2}/public_key").respond(
        content=public_key2.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    # Verify message (public key lookup via resolver)
    jws = JWS()
    jws.deserialize(message)
    verified_jwk = keyset.verify_jws(jws)
    assert verified_jwk.thumbprint() == public_jwk2.thumbprint()
