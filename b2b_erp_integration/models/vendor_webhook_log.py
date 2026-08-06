from odoo import fields, models


class VendorWebhookLog(models.Model):
    _name = 'vendor.webhook.log'
    _description = 'Vendor Webhook Log'

    platform_id = fields.Many2one('vendor.platform')
    request_payload = fields.Text()
    response_payload = fields.Text()
    status = fields.Selection([
        ('received', 'Received'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
    ], default='received')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
