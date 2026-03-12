# -*- coding: utf-8 -*-
"""Inheriting the controller"""
from odoo import http
from odoo.addons.portal.controllers import portal
from odoo.http import Controller, route, request

class EmployeePayslipPortal(Controller):

    @route(['/my/payslips', '/my/payslips/page/<int:page>'], auth='public', website=True)
    def portal_my_payslips(self, page=1, **kwargs):
        Payslip = request.env['hr.payslip'].sudo()
        domain = [('employee_id.user_id', '=', request.env.user.id)]
        payslips = Payslip.search(domain, order='payslip_run_id asc')

        grouped_payslips = {}
        for payslip in payslips:
            batch = payslip.payslip_run_id.name
            if batch not in grouped_payslips:
                grouped_payslips[batch] = []
            grouped_payslips[batch].append(payslip)

        return request.render("employee_portal.payslip_template", {
            'grouped_payslips': grouped_payslips,
            'page_name': 'payslips'
        })


class PayslipCount(portal.CustomerPortal):
    """Class for Time Off Count in Portal"""

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)

        employee = request.env['hr.employee'].sudo().search([
            ('user_id', '=', request.env.uid)
        ], limit=1)

        if employee and 'payslip_count' in counters:
            values['payslip_count'] = request.env['hr.payslip'].sudo().search_count([
                ('employee_id', '=', employee.id)
            ])
        return values


    @http.route('/my/payslip/<int:payslip_id>/print', type='http', auth='user', website=True)
    def portal_print_payslip(self, payslip_id, **kwargs):
        payslip = request.env['hr.payslip'].sudo().browse(payslip_id)
        if not payslip or payslip.employee_id.user_id != request.env.user:
            return request.not_found()
        pdf_content, content_type = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'hr_payroll.report_payslip_lang',
            [payslip_id]
        )
        return request.make_response(
            pdf_content,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'attachment; filename="payslip_{payslip.date_from.strftime("%B_%Y")}.pdf"'),
            ]
        )

