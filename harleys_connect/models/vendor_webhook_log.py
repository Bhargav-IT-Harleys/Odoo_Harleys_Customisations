from odoo import fields, models


class VendorWebhookLog(models.Model):
    _name = 'vendor.webhook.log'
    _description = 'Vendor Webhook Log'
    _order = 'create_date desc'

    platform_id = fields.Many2one('vendor.platform')
    account_id = fields.Many2one('vendor.account')
    vendor_code = fields.Char()
    vendor_event_id = fields.Char(string='Vendor Event ID', index=True)
    idempotency_key = fields.Char(string='Idempotency Key', index=True)
    outlet_id = fields.Char(string='Outlet ID')
    purchase_order_id = fields.Many2one('purchase.order', string='Purchase Order', index=True)
    request_payload = fields.Text(groups="harleys_connect.group_connect_manager")
    response_payload = fields.Text(groups="harleys_connect.group_connect_manager")
    http_status = fields.Integer()
    status = fields.Selection([
        ('received', 'Received'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
    ], default='received')
    error_message = fields.Text()
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
