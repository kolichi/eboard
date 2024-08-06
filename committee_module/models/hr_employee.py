from odoo import models, fields, api

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    committees_ids = fields.Many2many('hr.department', string="Committees")

    employee_type = fields.Selection([
        ('member','Member'),
        ('employee', 'Employee'),
        ('student', 'Student'),
        ('trainee', 'Trainee'),
        ('contractor', 'Contractor'),
        ('freelance', 'Freelancer'),
    ], string='Employee Type', default='member', required=True, groups="hr.group_hr_user",
        help="The member type. Although the primary purpose may seem to categorize members, this field has also an impact in the Contract History. Only Member type is supposed to be under contract and will have a Contract History.")

    member_type = fields.Selection([
        ('board_member', 'Board Member'),
        ('employee', 'Employee'),
    ], string='Member Type', default='board_member', required=True)

    @api.onchange("committees_ids","department_id")
    def _onchange_committee(self):

        if self.committees_ids:
           self.department_id = self.committees_ids[0].id
