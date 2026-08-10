from odoo import api


class HyperpureWebhookService:

    @staticmethod
    def handle(config, payload):
        outlet = False
        outlet_id = payload.get('outlet_id') or payload.get('outlet') or payload.get('outletId')
        if outlet_id:
            outlet = config.env['vendor.outlet'].sudo().search([
                ('vendor_account_id', '=', config.id),
                ('outlet_id', '=', str(outlet_id)),
            ], limit=1)
        return {
            "vendor": "hyperpure",
            "config": getattr(config, "id", None),
            "outlet": outlet.id if outlet else False,
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