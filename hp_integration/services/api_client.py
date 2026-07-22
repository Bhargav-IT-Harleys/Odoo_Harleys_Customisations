import logging
import requests

_logger = logging.getLogger(__name__)


class HyperpureAPIClient:

    TIMEOUT = 30

    @staticmethod
    def post(url, payload=None, headers=None):

        response = requests.post(
            url=url,
            json=payload or {},
            headers=headers or {},
            timeout=HyperpureAPIClient.TIMEOUT,
        )

        _logger.info(
            "POST %s Status:%s",
            url,
            response.status_code,
        )

        return response

    @staticmethod
    def get(url, headers=None):

        response = requests.get(
            url=url,
            headers=headers or {},
            timeout=HyperpureAPIClient.TIMEOUT,
        )

        _logger.info(
            "GET %s Status:%s",
            url,
            response.status_code,
        )

        return response