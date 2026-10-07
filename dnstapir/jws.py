import argparse
import json
import logging
from urllib.parse import urljoin

from jwcrypto.common import JWKeyNotFound
from jwcrypto.jwk import JWK, JWKSet
from jwcrypto.jws import JWS, InvalidJWSSignature

from .key_resolver import KeyResolver, UrlKeyResolver

logger = logging.getLogger(__name__)


class ResolverJWKSet(JWKSet):
    def __init__(self, key_resolver: KeyResolver):
        super().__init__()
        self.key_resolver = key_resolver

    def get_key(self, kid: str) -> JWK:
        return JWK.from_pyca(self.key_resolver.resolve_public_key(kid))

    def get_keys(self, kid: str) -> list[JWK]:
        return [self.get_key(kid)]

    def verify_jws(self, jws: JWS) -> JWK:
        """Verify JWS and return verified key (or raise JWKeyNotFound)"""

        for signature in jws.objects.get("signatures", [jws.objects]):
            if protected_header_str := signature.get("protected"):
                protected_header: dict[str, str] = json.loads(protected_header_str)
                if kid := protected_header.get("kid"):
                    logger.debug("Signature by kid=%s", kid)
                    try:
                        keys = self.get_keys(kid)
                    except (KeyError, ValueError):
                        continue
                    for key in keys:
                        try:
                            jws.verify(key=key)
                            if not hasattr(key, "kid"):
                                key.kid = kid
                            return key
                        except InvalidJWSSignature:
                            pass
                else:
                    logger.debug("Skipping signature without kid")
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
    keyset = ResolverJWKSet(key_resolver=key_resolver)

    jws = JWS()
    jws.deserialize(args.message)
    key = keyset.verify_jws(jws)

    logging.info("Found JWK: %s", json.dumps(key.export(as_dict=True)))
    logging.info("Message: %s", jws.payload.decode())


if __name__ == "__main__":
    main()
