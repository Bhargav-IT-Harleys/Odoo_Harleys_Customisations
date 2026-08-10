from odoo import http
from odoo.exceptions import AccessDenied
from odoo.http import request
from odoo.addons.web.controllers.home import Home as WebHome
from odoo.tools.translate import _, LazyTranslate

_lt = LazyTranslate(__name__)


class Home(WebHome):

    @http.route(
        '/web/login/employee_verify',
        type='http', auth='public', methods=['GET', 'POST'], sitemap=False,
        website=True, multilang=False,
    )
    def web_login_employee_verify(self, redirect=None, **kwargs):
        if request.session.uid:
            return request.redirect(self._login_redirect(request.session.uid, redirect=redirect))

        if not request.session.get('pre_uid'):
            return request.redirect('/web/login')

        functional_user = request.env['res.users'].sudo().browse(request.session['pre_uid'])
        error = None

        if request.httprequest.method == 'POST' and kwargs.get('employee_login') and kwargs.get('employee_password'):
            try:
                employee = self._verify_employee_credential(
                    functional_user, kwargs['employee_login'], kwargs['employee_password'])
            except AccessDenied as exc:
                error = exc.args[0] if exc.args else _("Invalid employee credentials.")
            else:
                request.session.finalize(request.env)
                request.session['employee_binding_id'] = employee.id
                request.update_env(user=request.session.uid)
                request.update_context(**request.session.context)
                return request.redirect(self._login_redirect(request.session.uid, redirect=redirect))

        return request.render('hr_shared_login_binding.employee_verify_form', {
            'error': error,
            'redirect': redirect,
            'functional_user': functional_user,
        })

    def _verify_employee_credential(self, functional_user, login, password):
        credential = {'login': login, 'password': password, 'type': 'password'}
        wsgienv = {
            'interactive': True,
            'base_location': request.httprequest.url_root.rstrip('/'),
            'HTTP_HOST': request.httprequest.environ['HTTP_HOST'],
            'REMOTE_ADDR': request.httprequest.environ['REMOTE_ADDR'],
        }
        env = request.env(user=None, su=False)
        auth_info = env['res.users'].authenticate(credential, wsgienv)

        employee = request.env['hr.employee'].sudo().search(
            [('user_id', '=', auth_info['uid'])], limit=1)
        if not employee:
            raise AccessDenied(_("This login is not linked to an employee record."))

        authorized = functional_user.authorized_employee_ids
        if authorized and employee not in authorized:
            raise AccessDenied(_("This employee is not authorized to use this account."))

        return employee

    def _login_redirect(self, uid, redirect=None):
        request.session['harleys_company_selection_pending'] = True
        return super()._login_redirect(uid, redirect=redirect)

    @http.route('/harleys_company_login_popup/dismiss', type='jsonrpc', auth='user')
    def dismiss_company_selection(self):
        request.session.pop('harleys_company_selection_pending', None)
        return True
