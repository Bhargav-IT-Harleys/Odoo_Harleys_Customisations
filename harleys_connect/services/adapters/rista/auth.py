import base64
import hashlib
import hmac
import json
import time
import uuid


def _b64url(raw_bytes):
    return base64.urlsafe_b64encode(raw_bytes).rstrip(b"=")


def _generate_jwt_hs256(payload, secret_key):
    # Minimal HS256 JWT encoder (stdlib only - PyJWT isn't installed in this
    # environment). Mirrors rista_api_tester's generate_jwt(): same claim shape,
    # same algorithm, just without the third-party dependency.
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = b".".join([
        _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8")),
        _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
    ])
    signature = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return b".".join([signing_input, _b64url(signature)]).decode("ascii")


class RistaAuthService:
    """Rista's JWT auth scheme, as confirmed by rista_api_tester: API key + secret
    key sign a short-lived HS256 JWT, sent as x-api-key / x-api-token headers."""

    @staticmethod
    def generate_jwt(method, api_key, secret_key):
        if not api_key or not secret_key:
            raise ValueError("Rista API key and secret key must be configured.")

        payload = {"iss": api_key, "iat": int(time.time())}
        if method.upper() in ("POST", "PUT", "DELETE"):
            payload["jti"] = str(uuid.uuid4())

        return _generate_jwt_hs256(payload, secret_key)

    @staticmethod
    def get_auth_headers(method, api_key, secret_key):
        token = RistaAuthService.generate_jwt(method, api_key, secret_key)
        headers = {
            "x-api-key": api_key,
            "x-api-token": token,
        }
        if method.upper() in ("POST", "PUT", "DELETE"):
            headers["Content-Type"] = "application/json"
        return headers
