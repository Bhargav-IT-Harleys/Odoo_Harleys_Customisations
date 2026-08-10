from ...http_client import HttpClient
from .constants import HyperpureConstants


class HyperpureAuthService:
    @staticmethod
    def _build_url(config):
        if getattr(config, 'auth_url', False):
            return config.auth_url
        base_url = getattr(config, 'base_url', False) or HyperpureConstants.DEFAULT_BASE_URL
        return f"{base_url.rstrip('/')}{HyperpureConstants.AUTH_PATH}"

    @staticmethod
    def request_otp(config):
        payload = {
            "account_id": getattr(config, 'account_id', False),
            "client_name": getattr(config, 'client_name', False),
            "api_access_key": getattr(config, 'api_access_key', False),
            "mobile": getattr(config, 'mobile_number', False),
        }
        return HttpClient.post(HyperpureAuthService._build_url(config), payload)

    @staticmethod
    def verify_otp(config, otp):
        payload = {
            "account_id": getattr(config, 'account_id', False),
            "client_name": getattr(config, 'client_name', False),
            "api_access_key": getattr(config, 'api_access_key', False),
            "mobile": getattr(config, 'mobile_number', False),
            "otp": otp,
        }
        return HttpClient.post(HyperpureAuthService._build_url(config), payload)