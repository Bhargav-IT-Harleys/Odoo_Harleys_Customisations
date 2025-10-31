from odoo import http
from odoo.http import request


class MultiCompanyToggleWithRefField(http.Controller):

    @http.route('/action_company_reference', methods=["POST"], type="jsonrpc", auth="user")
    def action_company_reference(self, company_id):
        """ multi company reference endpoint"""
        company_record = request.env['res.company'].sudo().browse(company_id)
        return company_record.partner_id.ref or company_record.name
