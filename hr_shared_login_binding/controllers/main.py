from odoo import http, _
from odoo.exceptions import AccessDenied
from odoo.http import request
from odoo.addons.web.controllers import home as web_home


class Home(web_home.Home):

    @http.route(
        '/web/login/employee_verify',
        type='http', auth='public', methods=['GET', 'POST'], sitemap=False,
        website=True, multilang=False,
    )
    def web_login_employee_verify(self, redirect=None, **kwargs):
        # Mirrors auth_totp's /web/login/totp: the shared account's credentials
        # were already accepted (pre_uid is set), we only need to confirm which
        # employee is behind it before finalizing the session.
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
        # Validates the employee's own login/password without switching
        # the session's active user - raises AccessDenied if invalid,
        # unrelated to an employee, or not authorized for this account.
        credential = {'login': login, 'password': password, 'type': 'password'}
        wsgienv = {
            'interactive': True,
            'base_location': request.httprequest.url_root.rstrip('/'),
            'HTTP_HOST': request.httprequest.environ['HTTP_HOST'],
            'REMOTE_ADDR': request.httprequest.environ['REMOTE_ADDR'],
        }
        # Same pattern core uses in Session.authenticate(): resolve the
        # credential against an anonymous env, independently of the
        # functional account's own (still pending) session.
        env = request.env(user=None, su=False)
        auth_info = env['res.users'].authenticate(credential, wsgienv)

        # res.users.employee_id is company-scoped (filters on env.company),
        # and there is no reliable company context yet on this pre-login
        # request - search hr.employee directly instead of relying on it.
        employee = request.env['hr.employee'].sudo().search(
            [('user_id', '=', auth_info['uid'])], limit=1)
        if not employee:
            raise AccessDenied(_("This login is not linked to an employee record."))

        authorized = functional_user.authorized_employee_ids
        if authorized and employee not in authorized:
            raise AccessDenied(_("This employee is not authorized to use this account."))

        return employee
