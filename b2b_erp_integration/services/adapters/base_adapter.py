class BaseAdapter:

    def authenticate(self):
        raise NotImplementedError

    def place_order(self):
        raise NotImplementedError

    def build_order_payload(self, purchase_order):
        raise NotImplementedError

    def webhook(self):
        raise NotImplementedError

    def search_products(self):
        raise NotImplementedError
