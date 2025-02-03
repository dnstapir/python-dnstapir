import argparse
import json
import logging
from urllib.parse import urljoin

from jwcrypto.common import JWKeyNotFound
from jwcrypto.jwk import JWK, JWKSet
from jwcrypto.jws import JWS, InvalidJWSSignature

from .key_resolver import KeyResolver, UrlKeyResolver

logger = logging.getLogger(__name__)


class ResolvedJWKSet(JWKSet):
    def __init__(self, key_resolver: KeyResolver):
        super().__init__()
        self.key_resolver = key_resolver

    def get_key(self, kid: str) -> JWK:
        return JWK.from_pyca(self.key_resolver.resolve_public_key(kid))

    def get_keys(self, kid: str) -> list[JWK]:
        return [self.get_key(kid)]


def verify_jws_with_keys(jws: JWS, keys: JWKSet) -> JWK:
    """Verify JWS using keys and return key (or raise JWKeyNotFound)"""
    protected_header = json.loads(jws.objects["protected"])
    if kid := protected_header.get("kid"):
        logger.debug("Signature by kid=%s", kid)
        for key in keys.get_keys(kid):
            try:
                jws.verify(key=key)
                if not hasattr(key, "kid"):
                    key.kid = kid
                return key
            except InvalidJWSSignature:
                pass
    else:
        logger.debug("Signature without kid")
    raise JWKeyNotFound


def main() -> None:
    """Main function"""

    parser = argparse.ArgumentParser(description="JWS Verifier")

    parser.add_argument("--nodeman", help="Nodeman API")
    parser.add_argument("--debug", action="store_true", help="Enable debugging")
    parser.add_argument("message", help="JWS message")

    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    client_database_base_url = urljoin(args.nodeman, "/api/v1/node/{key_id}/public_key")

    key_resolver = UrlKeyResolver(client_database_base_url=client_database_base_url)
    keyset = ResolvedJWKSet(key_resolver=key_resolver)

    jws = JWS()
    jws.deserialize(args.message)
    key = verify_jws_with_keys(jws, keyset)

    logging.info("Found JWK: %s", json.dumps(key.export(as_dict=True)))
    logging.info("Message: %s", jws.payload.decode())


if __name__ == "__main__":
    main()
