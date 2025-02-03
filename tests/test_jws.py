import json
import logging

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from jwcrypto.jwk import JWK
from jwcrypto.jws import JWS
from pytest_httpx import HTTPXMock

from dnstapir.jws import ResolverJWKSet
from dnstapir.key_resolver import UrlKeyResolver


def test_jws_verifier(httpx_mock: HTTPXMock):
    """Test JWS verifier"""

    logging.basicConfig(level=logging.DEBUG)

    # Create key
    key_id = "xyzzy"
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    public_jwk = JWK.from_pyca(public_key)
    alg = "EdDSA"

    # Mock key server response
    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    httpx_mock.add_response(url=f"https://keys/api/v1/node/{key_id}/public_key", content=public_key_pem)

    # Create message
    payload = {"hello": "world"}
    client_jws = JWS(payload=json.dumps(payload))
    client_jws.add_signature(key=JWK.from_pyca(private_key), alg=alg, protected={"kid": key_id, "alg": alg})
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
