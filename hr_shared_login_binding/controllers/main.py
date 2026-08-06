import logging

import odoo
from odoo import http
from odoo.exceptions import AccessDenied
from odoo.http import request
from odoo.addons.web.controllers.home import Home as WebHome, SIGN_UP_REQUEST_PARAMS, CREDENTIAL_PARAMS
from odoo.addons.web.controllers.utils import ensure_db
from odoo.tools.translate import _, LazyTranslate

_lt = LazyTranslate(__name__)

_logger = logging.getLogger(__name__)


class Home(WebHome):

    @http.route('/web/login', type='http', auth='none', readonly=False, list_as_website_content=_lt("Login"))
    def web_login(self, redirect=None, **kw):
        ensure_db()
        request.params['login_success'] = False
        if request.httprequest.method == 'GET' and redirect and request.session.uid:
            return request.redirect(redirect)

        if request.env.uid is None:
            if request.session.uid is None:
                request.env["ir.http"]._auth_method_public()
                if hasattr(request, 'website'):
                    request.website = request.env['website'].browse(request.website.id)
            else:
                request.update_env(user=request.session.uid)

        values = {k: v for k, v in request.params.items() if k in SIGN_UP_REQUEST_PARAMS}
        try:
            values['databases'] = http.db_list()
        except odoo.exceptions.AccessDenied:
            values['databases'] = None

        if request.httprequest.method == 'POST':
            try:
                credential = {key: value for key, value in request.params.items() if key in CREDENTIAL_PARAMS and value}
                credential.setdefault('type', 'password')
                if request.env['res.users']._should_captcha_login(credential):
                    request.env['ir.http']._verify_request_recaptcha_token('login')
                auth_info = request.session.authenticate(request.env, credential)
                request.params['login_success'] = True
                return request.redirect(self._login_redirect(auth_info['uid'], redirect=redirect))
            except odoo.exceptions.AccessDenied as e:
                if e.args == odoo.exceptions.AccessDenied().args:
                    values['error'] = _("Wrong login/password")
                else:
                    values['error'] = e.args[0]
        else:
            if 'error' in request.params and request.params.get('error') == 'access':
                values['error'] = _('Only employees can access this database. Please contact the administrator.')

        if 'login' not in values and request.session.get('auth_login'):
            values['login'] = request.session.get('auth_login')

        if not odoo.tools.config['list_db']:
            values['disable_database_manager'] = True

        response = request.render('web.login', values)
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Content-Security-Policy'] = "frame-ancestors 'self'"
        return response

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
