from odoo import http
from odoo.http import request


class VendorApiController(http.Controller):
    @http.route('/b2b_erp_integration/api/health', type='http', auth='public', methods=['GET'], csrf=False)
    def health(self, **kwargs):
        return request.make_response('ok', headers={'Content-Type': 'text/plain'})
