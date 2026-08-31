import requests


class HttpClient:
    """Thin wrapper around requests for vendor integrations."""

    timeout = 30

    @staticmethod
    def post(url, payload=None, headers=None):
        return requests.post(
            url=url,
            json=payload or {},
            headers=headers or {},
            timeout=HttpClient.timeout,
        )

    @staticmethod
    def get(url, headers=None):
        return requests.get(
            url=url,
            headers=headers or {},
            timeout=HttpClient.timeout,
        )
