"""Applies hr.employee.attribution.mixin to every business/master record model
this module logs employee attribution for. To add another model: inherit it
here (and add its owning module to __manifest__.py depends if needed).

Deliberately NOT covered, and why:
- mail/bus/automation/Studio/IAP internals (mail.message, mail.mail, ir.cron,
  ir.actions.server, base.automation, studio.approval.*, extract.mixin,
  iap.account, spreadsheet.cell.thread, fetchmail.server, mail.alias,
  mail.blacklist, mail.followers, mail.template, mail.thread* mixins
  themselves): not business records, and posting chatter from inside mail's
  own machinery risks recursion.
- gamification.*, rating.mixin, mail.thread.phone/phone.blacklist,
  website_slides.slide.slide: not relevant to who performed a shared-login
  business action.
- point_of_sale (pos.order, pos.session): pos_hr already attributes orders to
  the badged-in cashier natively; adding a second mechanism here would create
  two disagreeing sources of truth on the same order.
"""
from odoo import models


MIXIN = 'hr.employee.attribution.mixin'


# --- Procurement -----------------------------------------------------------

class PurchaseOrder(models.Model):
    _name = 'purchase.order'
    _inherit = ['purchase.order', MIXIN]


class PurchaseRequisition(models.Model):
    _name = 'purchase.requisition'
    _inherit = ['purchase.requisition', MIXIN]


# --- Sales -------------------------------------------------------------

class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', MIXIN]


class CrmTeam(models.Model):
    _name = 'crm.team'
    _inherit = ['crm.team', MIXIN]


class CrmTeamMember(models.Model):
    _name = 'crm.team.member'
    _inherit = ['crm.team.member', MIXIN]


# --- Accounting --------------------------------------------------------

class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', MIXIN]


class AccountPayment(models.Model):
    _name = 'account.payment'
    _inherit = ['account.payment', MIXIN]


class AccountAccount(models.Model):
    _name = 'account.account'
    _inherit = ['account.account', MIXIN]


class AccountJournal(models.Model):
    _name = 'account.journal'
    _inherit = ['account.journal', MIXIN]


class AccountReconcileModel(models.Model):
    _name = 'account.reconcile.model'
    _inherit = ['account.reconcile.model', MIXIN]


class AccountTax(models.Model):
    _name = 'account.tax'
    _inherit = ['account.tax', MIXIN]


class ResPartnerBank(models.Model):
    _name = 'res.partner.bank'
    _inherit = ['res.partner.bank', MIXIN]


class AccountAsset(models.Model):
    _name = 'account.asset'
    _inherit = ['account.asset', MIXIN]


class AccountBatchPayment(models.Model):
    _name = 'account.batch.payment'
    _inherit = ['account.batch.payment', MIXIN]


class AccountLoan(models.Model):
    _name = 'account.loan'
    _inherit = ['account.loan', MIXIN]


class AccountReturn(models.Model):
    _name = 'account.return'
    _inherit = ['account.return', MIXIN]


class AccountReturnType(models.Model):
    _name = 'account.return.type'
    _inherit = ['account.return.type', MIXIN]


class AccountBankStatement(models.Model):
    _name = 'account.bank.statement'
    _inherit = ['account.bank.statement', MIXIN]


class AccountBankStatementLine(models.Model):
    _name = 'account.bank.statement.line'
    _inherit = ['account.bank.statement.line', MIXIN]


class AccountAnalyticAccount(models.Model):
    _name = 'account.analytic.account'
    _inherit = ['account.analytic.account', MIXIN]


# --- Inventory -----------------------------------------------------------

class StockPicking(models.Model):
    _name = 'stock.picking'
    _inherit = ['stock.picking', MIXIN]


class StockScrap(models.Model):
    _name = 'stock.scrap'
    _inherit = ['stock.scrap', MIXIN]


class StockLot(models.Model):
    _name = 'stock.lot'
    _inherit = ['stock.lot', MIXIN]


class StockLandedCost(models.Model):
    _name = 'stock.landed.cost'
    _inherit = ['stock.landed.cost', MIXIN]


class StockPickingBatch(models.Model):
    _name = 'stock.picking.batch'
    _inherit = ['stock.picking.batch', MIXIN]


# --- Manufacturing -------------------------------------------------------

class MrpProduction(models.Model):
    _name = 'mrp.production'
    _inherit = ['mrp.production', MIXIN]


class MrpBom(models.Model):
    _name = 'mrp.bom'
    _inherit = ['mrp.bom', MIXIN]


class MrpUnbuild(models.Model):
    _name = 'mrp.unbuild'
    _inherit = ['mrp.unbuild', MIXIN]


class MrpRoutingWorkcenter(models.Model):
    _name = 'mrp.routing.workcenter'
    _inherit = ['mrp.routing.workcenter', MIXIN]


class MrpWorkcenter(models.Model):
    _name = 'mrp.workcenter'
    _inherit = ['mrp.workcenter', MIXIN]


# --- Quality ---------------------------------------------------------------

class QualityAlert(models.Model):
    _name = 'quality.alert'
    _inherit = ['quality.alert', MIXIN]


class QualityAlertTeam(models.Model):
    _name = 'quality.alert.team'
    _inherit = ['quality.alert.team', MIXIN]


class QualityCheck(models.Model):
    _name = 'quality.check'
    _inherit = ['quality.check', MIXIN]


class QualityPoint(models.Model):
    _name = 'quality.point'
    _inherit = ['quality.point', MIXIN]


# --- HR ----------------------------------------------------------------

class HrDepartment(models.Model):
    _name = 'hr.department'
    _inherit = ['hr.department', MIXIN]


class HrJob(models.Model):
    _name = 'hr.job'
    _inherit = ['hr.job', MIXIN]


class HrVersion(models.Model):
    _name = 'hr.version'
    _inherit = ['hr.version', MIXIN]


class HrEmployee(models.Model):
    _name = 'hr.employee'
    _inherit = ['hr.employee', MIXIN]


class HrAttendance(models.Model):
    _name = 'hr.attendance'
    _inherit = ['hr.attendance', MIXIN]


class HrExpense(models.Model):
    _name = 'hr.expense'
    _inherit = ['hr.expense', MIXIN]


class HrLeave(models.Model):
    _name = 'hr.leave'
    _inherit = ['hr.leave', MIXIN]


class HrLeaveAllocation(models.Model):
    _name = 'hr.leave.allocation'
    _inherit = ['hr.leave.allocation', MIXIN]


class HrPayslip(models.Model):
    _name = 'hr.payslip'
    _inherit = ['hr.payslip', MIXIN]


class HrPayslipRun(models.Model):
    _name = 'hr.payslip.run'
    _inherit = ['hr.payslip.run', MIXIN]


class HrSalaryAttachment(models.Model):
    _name = 'hr.salary.attachment'
    _inherit = ['hr.salary.attachment', MIXIN]


# --- Helpdesk ------------------------------------------------------------

class HelpdeskTicket(models.Model):
    _name = 'helpdesk.ticket'
    _inherit = ['helpdesk.ticket', MIXIN]


class HelpdeskTeam(models.Model):
    _name = 'helpdesk.team'
    _inherit = ['helpdesk.team', MIXIN]


# --- Project -----------------------------------------------------------

class ProjectTask(models.Model):
    _name = 'project.task'
    _inherit = ['project.task', MIXIN]


class ProjectMilestone(models.Model):
    _name = 'project.milestone'
    _inherit = ['project.milestone', MIXIN]


class ProjectUpdate(models.Model):
    _name = 'project.update'
    _inherit = ['project.update', MIXIN]


# --- Product -----------------------------------------------------------

class ProductCategory(models.Model):
    _name = 'product.category'
    _inherit = ['product.category', MIXIN]


class ProductPricelist(models.Model):
    _name = 'product.pricelist'
    _inherit = ['product.pricelist', MIXIN]


class ProductProduct(models.Model):
    _name = 'product.product'
    _inherit = ['product.product', MIXIN]


class ProductTemplate(models.Model):
    _name = 'product.template'
    _inherit = ['product.template', MIXIN]


# --- Fleet -------------------------------------------------------------

class FleetVehicle(models.Model):
    _name = 'fleet.vehicle'
    _inherit = ['fleet.vehicle', MIXIN]


class FleetVehicleLogContract(models.Model):
    _name = 'fleet.vehicle.log.contract'
    _inherit = ['fleet.vehicle.log.contract', MIXIN]


class FleetVehicleLogServices(models.Model):
    _name = 'fleet.vehicle.log.services'
    _inherit = ['fleet.vehicle.log.services', MIXIN]


class FleetVehicleModel(models.Model):
    _name = 'fleet.vehicle.model'
    _inherit = ['fleet.vehicle.model', MIXIN]


# --- Calendar ------------------------------------------------------------

class CalendarEvent(models.Model):
    _name = 'calendar.event'
    _inherit = ['calendar.event', MIXIN]


# --- Contacts ------------------------------------------------------------

class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner', MIXIN]


class ResCompany(models.Model):
    _name = 'res.company'
    _inherit = ['res.company', MIXIN]


# --- India localization ----------------------------------------------------

class L10nInPanEntity(models.Model):
    _name = 'l10n_in.pan.entity'
    _inherit = ['l10n_in.pan.entity', MIXIN]


class L10nInEwaybill(models.Model):
    _name = 'l10n.in.ewaybill'
    _inherit = ['l10n.in.ewaybill', MIXIN]


# --- Harleys custom (Indent) -----------------------------------------------

class IndentRequest(models.Model):
    _name = 'indent.request'
    _inherit = ['indent.request', MIXIN]


class IndentRequestLine(models.Model):
    _name = 'indent.request.line'
    _inherit = ['indent.request.line', MIXIN]


class IndentRequestTemplates(models.Model):
    _name = 'indent.request.templates'
    _inherit = ['indent.request.templates', MIXIN]
