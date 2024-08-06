from markupsafe import Markup
from odoo import models, fields, _, api
from odoo.exceptions import ValidationError

class CalendarEventProductLine(models.Model):
    _name = 'calendar.event.product.line'
    _description = 'Calendar Event Product Line'
    _order = 'sequence'

    sequence = fields.Integer(string='Sequence', default=10)
    calendar_id = fields.Many2one('calendar.event', string="Calendar Event")
    product_id = fields.Many2one('product.template', string="Product")
    quantity = fields.Float(string="Quantity")
    uom_id = fields.Many2one('uom.uom', string="Unit of Measure")
    agenda = fields.Char(string='Agenda', default=_('new'))
    presenter_id = fields.Many2many('hr.employee', string="Presenter", tracking=True)
    duration = fields.Float(string="Duration")
    start_date = fields.Datetime(string='Start Date', default=lambda self: fields.Datetime.now())
    end_date = fields.Datetime(string='End Date')
    description = fields.Html(string='Description')
    time = fields.Char(string='Time')

    @api.model_create_multi
    def create(self, values):

        for value in values:
            if not value.get('agenda') or value['agenda'] == _('new'):
                value['agenda'] = self.env['ir.sequence'].next_by_code('knowledge.article.sequence')
                # self._check_unique_agenda(value['agenda'])
        rtn = super(CalendarEventProductLine, self).create(values)
        for rec in rtn:
            print(rec.agenda)
            product_values = {
                'name': rec.agenda,
                'categ_id': self.env.ref("odoo_calendar_inheritence.product_category_dummy").id,
            }
            create_product = self.env['product.template'].sudo().create(product_values)
            rec.product_id = create_product.id
        return rtn

    def action_create_html(self):
        active_id = self.product_id.product_document_ids.id
        company_id = self.env.company.id
        html=Markup('<a href="/web?#active_id=%d&amp;action=qxm_product_pdf_annotation_tool.product_pdf_annotation&amp;cids=%d" style="padding: 5px 10px; color: #FFFFFF; text-decoration: none; background-color: #875A7B; border: 1px solid #875A7B; border-radius: 3px">View</a>')%(active_id, company_id)
        vALS={'name':"PDF test","body":html}
        res=self.env['knowledge.article'].sudo().create(vALS)
        # Markup("<div><b>%s</b></div>") % _("Lead Reset to Draft")
        print(res)
        # http://localhost:8069/web?debug=1#action=qxm_product_pdf_annotation_tool.product_pdf_annotation&active_id=26&cids=1&menu_id=100

    def write(self, values):
        if 'agenda' in values and values['agenda']:
            self._check_unique_agenda(values['agenda'], self.id)
        return super(CalendarEventProductLine, self).write(values)

    def _check_unique_agenda(self, agenda, exclude_id=None):
        domain = [('agenda', '=', agenda)]
        if exclude_id:
            domain.append(('id', '!=', exclude_id))
        if self.search_count(domain):
            raise ValidationError(_('The agenda "%s" already exists! Please change the name.') % agenda)

    @api.model
    def _delete_unused_dummy_products(self):
        dummy_category = self.env.ref('odoo_calendar_inheritence.product_category_dummy')
        product_lines = self.search([]).mapped('product_id.id')
        products_to_delete = self.env['product.template'].search([
            ('categ_id', '=', dummy_category.id),
            ('id', 'not in', product_lines)
        ])
        products_to_delete.unlink()

    def action_open_documents(self):
        # self.ensure_one()
        company_id = self.env.company.id
        for rec in self:
            return {
                'name': _('Documents'),
                'type': 'ir.actions.act_window',
                'res_model': 'product.document',
                'view_mode': 'kanban,tree,form',
                'context': {
                    'default_res_model': rec.product_id._name,
                    'default_res_id': rec.product_id.id,
                    'default_company_id': company_id,
                },
                'domain': [
                    '|',
                        '&', ('res_model', '=', 'product.template'), ('res_id', '=', rec.product_id.id),
                        '&',
                            ('res_model', '=', 'product.template'),
                            ('res_id', 'in', rec.product_id.product_variant_ids.ids),
                ],
                'target': 'current',
                'help': """
                    <p class="o_view_nocontent_smiling_face">
                        %s
                    </p>
                    <p>
                        %s
                        <br/>
                        %s
                    </p>
                    <p>
                        <a class="oe_link" href="https://www.odoo.com/documentation/17.0/_downloads/5f0840ed187116c425fdac2ab4b592e1/pdfquotebuilderexamples.zip">
                        %s
                        </a>
                    </p>
                """ % (
                    _("Upload files to your product"),
                    _("Use this feature to store any files you would like to share with your customers"),
                    _("(e.g: product description, ebook, legal notice, ...)."),
                    _("Download examples")
                )
            }