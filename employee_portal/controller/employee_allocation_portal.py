# -*- coding: utf-8 -*-
"""Inheriting the controller"""
from odoo.addons.portal.controllers import portal
from odoo.http import Controller, route, request


class EmployeeAllocationPortal(Controller):
    """Class for Employee details"""

    @route('/my/allocations', auth='user', website=True)
    def get_allocation(self):
        """Function to get the Allocated Time Off"""
        print("Fetching logged-in user details")

        # Step 1: Find the logged-in user's employee record
        employee = request.env['hr.employee'].sudo().search([
            ('user_id', '=', request.env.uid)
        ], limit=1)

        if not employee:
            print(f"No employee found for user ID {request.env.uid}")
            return request.render('employee_portal.portal_employee_details', {'allocations': []})

        print(f"Found employee {employee.id} for user {request.env.uid}")

        # Step 2: Fetch the allocated time-offs for this employee from hr.leave.allocation
        allocations = request.env['hr.leave.allocation'].sudo().search([
            ('employee_id', '=', employee.id)
        ])

        return request.render('employee_portal.portal_employee_details', {'allocations': allocations})


class AllocationCount(portal.CustomerPortal):
    """Class for Time Off Count in Portal"""

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)

        employee = request.env['hr.employee'].sudo().search([
            ('user_id', '=', request.env.uid)
        ], limit=1)

        if employee and 'lv_count' in counters:
            values['lv_count'] = request.env['hr.leave.allocation'].sudo().search_count([
                ('employee_id', '=', employee.id)
            ])
        return values
