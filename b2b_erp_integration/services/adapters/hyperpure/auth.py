from ...http_client import HttpClient


class HyperpureAuthService:
    @staticmethod
    def request_otp(config):
        payload = {"mobile": config.mobile_number}
        return HttpClient.post(config.auth_url, payload)

    @staticmethod
    def verify_otp(config, otp):
        payload = {"mobile": config.mobile_number, "otp": otp}
        return HttpClient.post(config.auth_url, payload)