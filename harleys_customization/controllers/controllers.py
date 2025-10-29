# from odoo import http


# class HarleysCustomization(http.Controller):
#     @http.route('/harleys_customization/harleys_customization', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/harleys_customization/harleys_customization/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('harleys_customization.listing', {
#             'root': '/harleys_customization/harleys_customization',
#             'objects': http.request.env['harleys_customization.harleys_customization'].search([]),
#         })

#     @http.route('/harleys_customization/harleys_customization/objects/<model("harleys_customization.harleys_customization"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('harleys_customization.object', {
#             'object': obj
#         })

