from urllib.parse import urlencode

from ...http_client import HttpClient
from .constants import HyperpureConstants


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


class HyperpureAuthService:
    """OTP handshake per Hyperpure's official "External POS integration" spec:
    getOutletPhoneNumbers returns masked_contacts[{phone_number, user_id}] -
    sendOTP/validateOTP operate on that user_id, not a raw phone number. On
    success, validateOTP returns a JWT in the response header, sent back as
    `Authorization: Bearer <jwt>` on every later call. No X-AccountId header -
    it isn't part of the real API despite an earlier draft doc implying it."""

    @staticmethod
    def _url(config, path_template):
        base_url = getattr(config, "base_url", False) or HyperpureConstants.DEFAULT_BASE_URL
        path = path_template.format(client_name=config.client_name)
        return f"{base_url.rstrip('/')}{path}"

    @staticmethod
    def _base_headers(config):
        return {
            "ApiAccessKey": config.api_access_key,
            "Content-Type": "application/json",
        }

    @staticmethod
    def get_outlet_phone_numbers(config, outlet_id, page_no=None):
        url = HyperpureAuthService._url(config, HyperpureConstants.OUTLET_PHONE_NUMBERS_PATH)
        params = {"outlet_id": outlet_id}
        if page_no:
            params["page_no"] = page_no
        headers = {"ApiAccessKey": config.api_access_key}
        return HttpClient.get(f"{url}?{urlencode(params)}", headers)

    @staticmethod
    def _identity_payload(config, user_id):
        # Confirmed Mode A (JWT) per Hyperpure's account-specific doc: our
        # onboarding flow (outlet_phone_numbers lookup -> user_id) is Mode A,
        # whose send_otp/validate_otp body is user_id only - no phone_number
        # or account_id (those belong to the separate, unused Mode B).
        return {"user_id": _as_int(user_id)}

    @staticmethod
    def request_otp(config, user_id):
        url = HyperpureAuthService._url(config, HyperpureConstants.SEND_OTP_PATH)
        payload = HyperpureAuthService._identity_payload(config, user_id)
        return HttpClient.post(url, payload, HyperpureAuthService._base_headers(config))

    @staticmethod
    def verify_otp(config, otp, user_id):
        url = HyperpureAuthService._url(config, HyperpureConstants.VALIDATE_OTP_PATH)
        payload = {"otp": otp, **HyperpureAuthService._identity_payload(config, user_id)}
        return HttpClient.post(url, payload, HyperpureAuthService._base_headers(config))
