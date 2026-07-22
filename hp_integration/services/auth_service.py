from .api_client import HyperpureAPIClient


class HyperpureAuthService:

    @staticmethod
    def request_otp(config):

        payload = {
            "mobile": config.mobile_number,
        }

        return HyperpureAPIClient.post(
            config.auth_url,
            payload,
        )

    @staticmethod
    def verify_otp(config, otp):

        payload = {
            "mobile": config.mobile_number,
            "otp": otp,
        }

        return HyperpureAPIClient.post(
            config.auth_url,
            payload,
        )