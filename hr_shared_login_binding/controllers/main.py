from odoo import http, _
from odoo.exceptions import AccessDenied
from odoo.http import request
from odoo.addons.web.controllers import home as web_home
from odoo.addons.web.controllers.utils import _get_login_redirect_url, ensure_db


class Home(web_home.Home):

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


class CustomLoginController(http.Controller):
    @http.route('/hr_shared_login_binding/login', type='http', auth='none', website=True, sitemap=False)
    def custom_login(self, redirect=None, **kw):
        ensure_db()
        values = {
            'redirect': redirect,
            'databases': http.db_list(),
        }
        if request.httprequest.method == 'POST':
            credential = {
                'login': request.params.get('login'),
                'password': request.params.get('password'),
                'type': 'password',
            }
            try:
                auth_info = request.session.authenticate(request.env, credential)
                user = request.env['res.users'].sudo().browse(auth_info['uid'])
                if user.is_shared_login:
                    request.session['pre_uid'] = auth_info['uid']
                    request.update_env(user=None)
                    return request.redirect('/web/login/employee_verify')
                request.session.finalize(request.env)
                request.session['harleys_company_selection_pending'] = True
                return request.redirect(_get_login_redirect_url(auth_info['uid'], redirect=redirect))
            except AccessDenied as e:
                values['error'] = e.args[0] if e.args else _("Wrong login/password")
        response = request.render('hr_shared_login_binding.custom_login', values)
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Content-Security-Policy'] = "frame-ancestors 'self'"
        return response
