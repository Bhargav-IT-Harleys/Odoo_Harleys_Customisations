class HyperpureWebhookService:

    @staticmethod
    def handle(config, payload):
        return {
            "vendor": "hyperpure",
            "config": getattr(config, "id", None),
            "payload": payload,
        }

    @staticmethod
    def process(data):
        """
        Placeholder.

        Later this will update
        Purchase Order,
        GRN,
        Delivery Status.
        """

        return True