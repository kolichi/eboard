from markupsafe import Markup
from bs4 import BeautifulSoup
import base64
from datetime import time
import logging
import re
from io import BytesIO
import babel
import babel.dates
from markupsafe import Markup, escape
from PIL import Image
from lxml import etree, html
from odoo import models, fields, api, Command, _
from odoo.exceptions import ValidationError, UserError

CLOSED_STATES = {
    '1_done': 'Done',
    '1_canceled': 'Canceled',
}


class OdooCalendarInheritence(models.Model):
    _inherit = 'calendar.event'

    milestone_id = fields.Many2one('project.milestone', string='Milestone')
    agenda_description = fields.Html(name="agenda_description", string="Description")
    mom_description = fields.Html(name="mom_description", string="Description")
    image = fields.Image(name="image", string="Image")
    attachment_ids = fields.Many2many(comodel_name='ir.attachment', string="Attachments")
    video_attachment_ids = fields.One2many(comodel_name='video.attachment', inverse_name='calendar_id',
                                           string="Attachments")
    parent_id = fields.Many2one('calendar.event', string='Parent Task', index=True, tracking=True)
    child_ids = fields.One2many('calendar.event', 'parent_id', string="Sub-tasks")

    project_id = fields.Many2one('project.project', string='Project',
                                 domain="['|', ('company_id', '=', False), ('company_id', '=?',  company_id)]",
                                 index=True, tracking=True, change_default=True)
    display_in_project = fields.Boolean(default=True, readonly=True)
    sequence = fields.Integer(string='Sequence', default=10)
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'High'),
    ], default='0', index=True, string="Priority", tracking=True)
    state = fields.Selection([
        ('01_in_progress', 'In Progress'),
        ('02_changes_requested', 'Changes Requested'),
        ('03_approved', 'Approved'),
        *CLOSED_STATES.items(),
        ('04_waiting_normal', 'Waiting'),
    ], string='State', copy=False, default='01_in_progress', required=True,
        readonly=False, index=True, recursive=True, tracking=True)
    name = fields.Char(string='Title', tracking=True, required=False, index='trigram')
    subtask_count = fields.Integer("Sub-task Count")
    closed_subtask_count = fields.Integer("Closed Sub-tasks Count")
    partner_id = fields.Many2one('res.partner',
                                 string='Customer', recursive=True, tracking=True, store=True, readonly=False,
                                 domain="['|', ('company_id', '=?', company_id), ('company_id', '=', False)]")
    company_id = fields.Many2one('res.company', string='Company', store=True, readonly=False, recursive=True, copy=True,
                                 default=lambda self: self.env.user.company_id
                                 )

    tag_ids = fields.Many2many('project.tags', string='Tags')
    new_project_id = fields.Many2one('project.project', string='Action Point',
                                     domain="['|', ('company_id', '=', False), ('company_id', '=?',  company_id)]")
    new_task_name = fields.Char('Task Title')
    user_ids = fields.Many2many('res.users',
                                string='Assignees', tracking=True, )
    date_deadline = fields.Datetime(string='Deadline', index=True, tracking=True)
    end_date = fields.Datetime(string=' End date', index=True, tracking=True)
    task_id = fields.Many2one('project.task', string='Related Task', domain="[('project_id', '=', new_project_id)]")
    new_task_id = fields.Char(string="Task Name")
    stage_id = fields.Many2one('project.task.type', string='Stage', domain="[('project_ids', '=', new_project_id)]",
                               readonly=False, ondelete='restrict', tracking=True, index=True)
    agenda_lines_ids = fields.One2many(comodel_name='agenda.lines', inverse_name='calendar_id', string='Lines')
    product_line_ids = fields.One2many(comodel_name='calendar.event.product.line', inverse_name='calendar_id',
                                       string='Agenda Lines')
    product_document_ids = fields.Many2many(comodel_name='product.document', compute='_compute_product_documents',
                                            string='Product Documents')
    article_exists = fields.Boolean(compute='_compute_article_exists', store=False)
    article_id = fields.Many2one('knowledge.article', string='Related Article')
    description_article_id = fields.Many2one('knowledge.article', string='Related Description Article')
    task_created = fields.Boolean(string="Task Created", default=False)
    description = fields.Html(string="Description")
    attendees_lines_ids = fields.One2many('attendees.lines', 'calendar_id')
    has_attendees_added = fields.Boolean(default=False)
    has_attendees_confirmed = fields.Boolean(default=False)
    last_write_count = fields.Integer('Last Count')
    last_write_date = fields.Datetime('Last Write Date')
    product_id = fields.Many2one('product.template', string="Product")
    nested_calender = fields.Boolean(default=False)
    agenda_lines_count = fields.Integer(string="Agendas", compute='_compute_agenda_count')
    mom_lines_count = fields.Integer(string="Minutes of Meeting", compute='_compute_mom_count')
    action_point_count = fields.Integer(string="Action Points", compute='_compute_action_count')
    company_logo = fields.Image()
    is_meeting_finished = fields.Boolean(default=False)
    is_description_created = fields.Boolean(default=False)

    @api.depends('product_line_ids')
    def _compute_agenda_count(self):
        for rec in self:
            if rec.product_line_ids:
                rec.agenda_lines_count = len(rec.product_line_ids)
            else:
                rec.agenda_lines_count = 0

    def _compute_action_count(self):
        for rec in self:
            if rec.project_id:
                rec.action_point_count = rec.project_id.task_count
            else:
                rec.action_point_count = 0

    @api.depends('attendees_lines_ids')
    def _compute_mom_count(self):
        count = 0
        for rec in self:
            if rec.attendees_lines_ids:
                for attendee in rec.attendees_lines_ids:
                    if attendee.has_attended:
                        count += 1
                rec.mom_lines_count = count
            else:
                rec.mom_lines_count = 0

    # def _compute_mom_count(self):
    #     pass

    # ----------------------------------------------------------------------------
    #                               Calendar --> Documents
    # ----------------------------------------------------------------------------

    @api.model_create_multi
    def create(self, values):
        # for value in values:
        #     if not value.get('name') or value['name'] == _('new'):
        #
        #         # self._check_unique_agenda(value['agenda'])
        # print(self._context.get('dont_create_nested'))
        for rec in values:
            if not rec.get('nested_calender'):
                print("Here NOT")
                seq_product = self.env['ir.sequence'].next_by_code('knowledge.article.sequence')
                product_values = {
                    'name': seq_product,
                    'categ_id': self.env.ref("odoo_calendar_inheritence.product_category_dummy").id,
                }
                create_product = self.env['product.template'].sudo().create(product_values)
                rec['product_id'] = create_product.id
                if rec.get('name'):
                    project_values = {
                        'name': rec.get('name'),
                    }
                    create_project = self.env['project.project'].sudo().create(project_values)
                    rec['project_id'] = create_project.id
                else:
                    print("Else")
                    project_values = {
                        'name': 'New Project',
                    }
                    create_project = self.env['project.project'].sudo().create(project_values)
                    rec['project_id'] = create_project.id

                stage_data = [
                    {'name': 'New', 'project_ids': [(4, create_project.id)]},
                    {'name': 'In Progress', 'project_ids': [(4, create_project.id)]},
                    {'name': 'Finished', 'project_ids': [(4, create_project.id)]}
                ]
                for stage in stage_data:
                    self.env['project.task.type'].sudo().create(stage)
        rtn = super(OdooCalendarInheritence, self).create(values)

        return rtn

    # ----------------------------------------------------------------------------
    # ----------------------------------------------------------------------------

    def write(self, vals):
        if 'name' in vals:
            if self.project_id:
                self.project_id.sudo().write({
                    'name': vals['name']
                })
        res = super(OdooCalendarInheritence, self).write(vals)
        return res

    @api.depends('article_id')
    def _compute_article_exists(self):
        for record in self:
            record.article_exists = bool(record.article_id)

    def _get_src_data_b64(self, value):
        try:  # FIXME: maaaaaybe it could also take raw bytes?
            image = Image.open(BytesIO(base64.b64decode(value)))
            image.verify()

        except IOError:
            raise ValueError("Non-image binary fields can not be converted to HTML")
        except:  # image.verify() throws "suitable exceptions", I have no idea what they are
            raise ValueError("Invalid image content")

        return "data:%s;base64,%s" % (Image.MIME[image.format], value.decode('ascii'))

    def create_article_calendar(self):
        if not self.product_line_ids:
            raise ValidationError("Please add an agenda before making an Article!")

        counter = 1
        company_id = self.env.company
        product_id = self.product_id.id
        logo = company_id.logo
        if logo:
            logo_html = Markup('<img src="%s" class="bg-view" alt="Company Logo"/>') % self._get_src_data_b64(logo)
        else:
            logo_html = ''

        html_content = Markup("""
                    <table class="table">
                        <thead>
                            <tr style="border: 0px; background-color: #ffffff;">
                                <th style="padding: 10px; border: 0px;">ID</th>
                                <th style="padding: 10px; border: 0px;">Agenda Item</th>
                                <th style="padding: 10px; border: 0px;">Presenter</th>
                            </tr>
                        </thead>
                        <tbody id="article_body">
        """)

        for line in self.product_line_ids:
            presenters = ', '.join(presenter.name for presenter in line.presenter_id)
            html_content += Markup("""
                <tr style="border: 0px;">
                    <td style="padding: 10px; border: 0px;">{counter}</td>
                    <td style="padding: 10px; border: 0px;">{description}</td>
                    <td style="padding: 10px; border: 0px;">{presenters}</td>
                </tr>
            """).format(
                counter=counter,
                description=line.description or 'N/A',
                presenters=presenters or 'N/A'
            )

            counter += 1

        html_content += Markup("""
                        </tbody>
                    </table>
                    """)

        body_content = Markup("""
            <div>
                <header style="text-align: center;">
                    {logo_html}<br><br>
                    <h2><strong>{company_name}<strong></h2>
                </header>
                <div class="container">
                    <div class="card-body border-dark">
                        <div class="row no-gutters align-items-center">
                            <div class="col align-items-center">
                                <p class="mb-0">
                                    <span> {company_street} </span>
                                </p>
                                <p class="mb-0">
                                   <span> {company_city} </span>
                                </p>
                                <p class="m-0">
                                   <span> {company_country} </span>
                                </p>
                            </div>
                            <div class="col-auto">
                                <div class="float-right text-end">
                                    <p class="mb-0 float-right">
                                        <span> {company_phone} </span>
                                        <i class="fa fa-phone-square ms-2 text-info" title="Phone"/>
                                    </p>
                                    <p class="mb-0 float-right">
                                       <span> {company_email} </span>
                                        <i class="fa fa-envelope ms-2 text-info" title="Email"/>
                                    </p>
                                    <p class="mb-0 float-right">
                                        <span> {company_website} </span>
                                        <i class="fa fa-globe ms-2 text-info" title="Website"/>
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div><br><hr>
                <div class="container">
                <p><strong style='font-size: 14px;'>Title: </strong> {event_name}</p>
                <p><strong>Start Date:</strong> {start_date}</p>
                <p><strong>Organizer:</strong> {organizer}</p>
                <p><strong>Subject:</strong> {description}</p>
                </div>
                <hr/>
                {html_content}
            </div>
        """).format(
            logo_html=logo_html,
            company_name=company_id.name,
            company_street=company_id.street,
            company_city=company_id.city,
            company_country=company_id.country_id.name,
            company_phone=company_id.phone,
            company_email=company_id.email,
            company_website=company_id.website,
            event_name=self.name,
            start_date=self.start_date if self.start_date else ' ',
            organizer=self.user_id.name,
            description=self.description,
            html_content=html_content
        )

        article_values = {
            'name': Markup("Agenda: {event_name}").format(event_name=self.name),
            'body': body_content,
            'calendar_id': self.id,
        }

        article = self.env['knowledge.article'].sudo().create(article_values)
        self.article_id = article.id

        self.article_id.product_id = self.product_id.id
        self.last_write_count = len(self.product_line_ids)
        self.last_write_date = fields.Datetime.now()

    def action_add_knowledge_article(self):
        if not self.article_id:
            raise ValidationError("No Article for these records in Knowledge Module!")

        filtered_product_lines_2 = [line for line in self.product_line_ids if line.create_date >= self.last_write_date]

        if not filtered_product_lines_2:
            raise UserError(_("No new data added to the agenda! Please add data before making changes to the article!"))

        existing_content = self.article_id.body
        soup = BeautifulSoup(existing_content, 'html.parser')

        # Find the existing table body
        table_body = soup.find('tbody')
        if not table_body:
            raise UserError(_("No existing table found in the article!"))

        filtered_product_lines = [line for line in self.product_line_ids if line.create_date < self.last_write_date]
        serial = len(filtered_product_lines) + 1

        for line in self.product_line_ids:
            if line.create_date >= self.last_write_date:
                presenters = ', '.join(presenter.name for presenter in line.presenter_id)

                # Strip HTML tags from the description and preserve line breaks
                description_soup = BeautifulSoup(line.description or 'N/A', 'html.parser')
                description_text = description_soup.get_text()
                description_text = description_text.replace('\n', '<br>')

                new_row = soup.new_tag('tr', style="border: 0px;")

                serial_td = soup.new_tag('td', style="padding: 10px; border: 0px;")
                serial_td.string = str(serial)
                new_row.append(serial_td)

                description_td = soup.new_tag('td', style="padding: 10px; border: 0px;")
                description_td.append(BeautifulSoup(description_text, 'html.parser'))
                new_row.append(description_td)

                presenters_td = soup.new_tag('td', style="padding: 10px; border: 0px;")
                presenters_td.string = presenters or 'N/A'
                new_row.append(presenters_td)

                table_body.append(new_row)
                serial += 1

        self.last_write_date = fields.Datetime.now()

        # Convert the modified soup object back to a string
        updated_content = str(soup)

        article_values = {
            'body': Markup(updated_content),
        }
        self.article_id.sudo().write(article_values)

    # def action_add_knowledge_article(self):
    #         if not self.article_id:
    #             raise ValidationError("No Article for these records in Knowledge Module!")
    #
    #         filtered_product_lines_2 = [line for line in self.product_line_ids if
    #                                     line.create_date >= self.last_write_date]
    #
    #         if not filtered_product_lines_2:
    #             raise UserError(
    #                 _("No new data added to the agenda! Please add data before making changes to the article!"))
    #
    #         existing_content = self.article_id.body
    #         soup = BeautifulSoup(existing_content, 'html.parser')
    #
    #         # Find the existing table body
    #         table_body = soup.find('tbody')
    #         if not table_body:
    #             raise UserError(_("No existing table found in the article!"))
    #
    #         filtered_product_lines = [line for line in self.product_line_ids if line.create_date < self.last_write_date]
    #         serial = len(filtered_product_lines) + 1
    #
    #         for line in self.product_line_ids:
    #             if line.create_date >= self.last_write_date:
    #                 presenters = ', '.join(presenter.name for presenter in line.presenter_id)
    #
    #                 new_row = soup.new_tag('tr', style="border: 0px;")
    #
    #                 serial_td = soup.new_tag('td', style="padding: 10px; border: 0px;")
    #                 serial_td.string = str(serial)
    #                 new_row.append(serial_td)
    #
    #                 description_td = soup.new_tag('td', style="padding: 10px; border: 0px;")
    #                 description_td.string = line.description or 'N/A'
    #                 new_row.append(description_td)
    #
    #                 presenters_td = soup.new_tag('td', style="padding: 10px; border: 0px;")
    #                 presenters_td.string = presenters or 'N/A'
    #                 new_row.append(presenters_td)
    #
    #                 table_body.append(new_row)
    #                 serial += 1
    #
    #         self.last_write_date = fields.Datetime.now()
    #
    #         # Convert the modified soup object back to a string
    #         updated_content = str(soup)
    #
    #         article_values = {
    #             'body': Markup(updated_content),
    #         }
    #         self.article_id.sudo().write(article_values)

    # def action_add_knowledge_article(self):
    #     if not self.article_id:
    #         raise ValidationError("No Article for these records in Knowledge Module!")
    #
    #     filtered_product_lines_2 = [line for line in self.product_line_ids if line.create_date >= self.last_write_date]
    #
    #     if not filtered_product_lines_2:
    #         raise UserError(_("No new data added to the agenda! Please add data before making changes to the article!"))
    #
    #     existing_content = self.article_id.body
    #     soup = BeautifulSoup(existing_content, 'html.parser')
    #
    #     # Find the existing table body
    #     table_body = soup.find('tbody')
    #     if not table_body:
    #         raise UserError(_("No existing table found in the article!"))
    #
    #     filtered_product_lines = [line for line in self.product_line_ids if line.create_date < self.last_write_date]
    #     serial = len(filtered_product_lines) + 1
    #
    #     for line in self.product_line_ids:
    #         if line.create_date >= self.last_write_date:
    #             presenters = ', '.join(presenter.name for presenter in line.presenter_id)
    #
    #             # Strip HTML tags from the description
    #             description_soup = BeautifulSoup(line.description or 'N/A', 'html.parser')
    #             description_text = description_soup.get_text()
    #
    #             new_row = soup.new_tag('tr', style="border: 0px;")
    #
    #             serial_td = soup.new_tag('td', style="padding: 10px; border: 0px;")
    #             serial_td.string = str(serial)
    #             new_row.append(serial_td)
    #
    #             description_td = soup.new_tag('td', style="padding: 10px; border: 0px;")
    #             description_td.string = description_text
    #             new_row.append(description_td)
    #
    #             presenters_td = soup.new_tag('td', style="padding: 10px; border: 0px;")
    #             presenters_td.string = presenters or 'N/A'
    #             new_row.append(presenters_td)
    #
    #             table_body.append(new_row)
    #             serial += 1
    #
    #     self.last_write_date = fields.Datetime.now()
    #
    #     # Convert the modified soup object back to a string
    #     updated_content = str(soup)
    #
    #     article_values = {
    #         'body': Markup(updated_content),
    #     }
    #     self.article_id.sudo().write(article_values)


    def action_create_agenda_descriptions(self):
        company_id = self.env.company
        # Get the company logo
        logo = company_id.logo
        if logo:
            logo_html = Markup('<img src="%s" class="bg-view" alt="Company Logo"/>') % self._get_src_data_b64(logo)
            # print(logo_html)
        if not self.product_line_ids:
            raise ValidationError("Please add data before making an Article!")
        if not self.description_article_id:
            counter = 1
            company_id = self.env.company
            mom_description_content = Markup("""""")
            attendees_names = Markup("""""")

            # Build the table rows for each agenda line
            for line in self.product_line_ids:
                mom_description_content += Markup("""
                            {description}<hr>
                            """).format(
                    description=line.description or 'N/A'
                )
                counter += 1
            attendees = self.action_confirm_attendees()
            self.has_attendees_confirmed = True
            if attendees:
                attendees_names += Markup("""
                                                    <strong>Meeting Attendees:</strong><br><br>
                """)
            for attendee in attendees:
                if attendee:
                    attendees_names += Markup("""
                                    {attendee_name}<br>
                """).format(attendee_name=attendee.attendee_name)
            attendees_names += Markup("""
                        <hr>
                """)

            body_content = Markup("""
                <div>
                    <header style="text-align: center;">
                        {logo_html}<br><br>
                        <h2><strong>{company_name}<strong></h2>
                    </header>
                    <div class="container">
                        <div class="card-body border-dark">
                            <div class="row no-gutters align-items-center">
                                <div class="col align-items-center">
                                    <!-- Name and position -->
                                    <p class="mb-0">
                                        <span> {company_street} </span>
                                    </p>
                                    <p class="mb-0">
                                        <span> {company_city} </span>
                                    </p>
                                    <p class="m-0">
                                        <span> {company_country} </span>
                                    </p>
                                </div>
                                <div class="col-auto">
                                    <!-- Phone and email -->
                                    <div class="float-right text-end">
                                        <p class="mb-0 float-right">
                                            <span> {company_phone} </span>
                                            <i class="fa fa-phone-square ms-2 text-info" title="Phone"/>
                                        </p>
                                        <p class="mb-0 float-right">
                                            <span> {company_email} </span>
                                            <i class="fa fa-envelope ms-2 text-info" title="Email"/>
                                        </p>
                                        <p class="mb-0 float-right">
                                            <span> {company_website} </span>
                                            <i class="fa fa-globe ms-2 text-info" title="Website"/>
                                        </p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div><br><hr>
                    {attendees_names}
                    <br>
                    {mom_description_content}
                </div>
            """).format(
                logo_html=logo_html,
                company_name=company_id.name,
                company_street=company_id.street,
                company_city=company_id.city,
                company_country=company_id.country_id.name,
                company_phone=company_id.phone,
                company_email=company_id.email,
                company_website=company_id.website,
                attendees_names=attendees_names,
                mom_description_content=mom_description_content,
            )
            article_values = {
                'name': f"Minutes: {self.name}",  # Name for the description, for that Agenda!
                'body': body_content,
                'calendar_id': self.id,
            }

            description_article = self.env['knowledge.article'].sudo().create(article_values)
            self.description_article_id = description_article
            self.description_article_id.product_id = self.product_id.id
            self.is_description_created = True
            self.description_article_id.is_minutes_of_meeting = True
            return self.action_view_description_article()
        else:
            return self.action_view_description_article()

    def action_view_knowledge_article(self):
        self.ensure_one()
        for record in self:
            if record.article_id:
                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Knowledge Article',
                    'res_model': 'knowledge.article',
                    'view_mode': 'form',
                    'res_id': record.article_id.id,
                    'target': 'current',
                }

    def action_view_description_article(self):
        self.ensure_one()
        if self.description_article_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Knowledge Article',
                'res_model': 'knowledge.article',
                'view_mode': 'form',
                'res_id': self.description_article_id.id,
                'target': 'current',
            }

    # -------------------------------------------------------------------
    # -------------------------------------------------------------------

    @api.depends('product_line_ids')
    def _compute_product_documents(self):
        for event in self:
            product_ids = event.product_line_ids.mapped('product_id')
            documents = self.env['product.document'].search([('product_id', 'in', product_ids.ids)])
            event.product_document_ids = [5, 0, [documents.ids]]

    @api.onchange('new_project_id')
    def _onchange_new_project_id(self):
        if self.new_project_id:
            return {'domain': {'task_id': [('project_id', '=', self.new_project_id.id)]}}
        else:
            return {'domain': {'task_id': []}}

    def action_create_task(self):
        for record in self:
            if record.new_project_id and record.new_task_name:
                task_vals = {
                    'name': record.new_task_name,
                    'project_id': record.new_project_id.id,
                    'user_ids': [(6, 0, record.user_ids.ids)],
                    'date_deadline': record.date_deadline,
                    'stage_id': record.stage_id.id if record.stage_id else False,
                    'parent_id': False,
                }
                new_task = self.env['project.task'].create(task_vals)
                record.task_id = new_task.id
                record.task_created = True  # Set task_created to True

    def action_view_task(self):
        for record in self:
            if record.task_id:
                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Task',
                    'view_mode': 'form',
                    'res_model': 'project.task',
                    'res_id': record.task_id.id,
                    'target': 'current',
                }

    def action_reset_attendees(self):
        for rec in self:
            rec.attendees_lines_ids.unlink()
            rec.is_description_created = False
            rec.has_attendees_added = False
            rec.has_attendees_confirmed = False
            rec.description_article_id.sudo().unlink()

    def action_add_attendees(self):
        partners = []
        for partner in self.partner_ids:
            partners.append(
                Command.create(
                    {
                        'attendee_name': partner.name,
                        'email': partner.email,
                        'phone': partner.phone,
                    }
                )
            )
        if not self.attendees_lines_ids:
            self.attendees_lines_ids = partners
            self.has_attendees_added = True
        # ￼
        else:
            self.attendees_lines_ids.sudo().unlink()
            self.attendees_lines_ids = partners
            self.has_attendees_added = True

    def _calendar_meeting_end_tracker(self):
        calendar_meetings = self.env['calendar.event'].search([])
        if calendar_meetings:
            for record in calendar_meetings:
                if not record.allday:
                    if record.stop and record.stop <= fields.Datetime.now():
                        record.is_meeting_finished = True
                    else:
                        record.is_meeting_finished = False
                if record.allday:
                    if record.stop_date and record.stop_date <= fields.Date.today():
                        record.is_meeting_finished = True
                    else:
                        record.is_meeting_finished = False

    def action_confirm_attendees(self):
        attendees = []
        if not self.attendees_lines_ids:
            raise UserError(_('Kindly, add the attendees!'))
        for attendee in self.attendees_lines_ids:
            if attendee.has_attended:
                attendees.append(attendee)
        return attendees

        # self.attendees_lines_ids =

    def action_open_documents(self):
        # self.ensure_one()
        company_id = self.env.company.id
        current_time = fields.Datetime.now()
        meeting_end_time = self.stop
        active_user = self.env.user.partner_id.id
        domain = [
            '|',
            '&', ('res_model', '=', 'product.template'), ('res_id', '=', self.product_id.id),
            '&',
            ('res_model', '=', 'product.template'),
            ('res_id', 'in', self.product_id.product_variant_ids.ids),
            ('partner_ids', 'in', [active_user]), ]
        # if current_time and meeting_end_time:
        # if current_time >= meeting_end_time: #If Meeting Has Ended
        #     domain = [
        #         '|',
        #         '&', ('res_model', '=', 'product.template'), ('res_id', '=', self.product_id.id),
        #         '&',
        #         ('res_model', '=', 'product.template'),
        #         ('res_id', 'in', self.product_id.product_variant_ids.ids),
        #     ]
        # else: #If meeting is still going!
        #     domain = [
        #         '|',
        #         '&', ('res_model', '=', 'product.template'), ('res_id', '=', self.product_id.id),
        #         '&',
        #         ('res_model', '=', 'product.template'),
        #         ('res_id', 'in', self.product_id.product_variant_ids.ids),
        #         ('partner_ids', 'in', [active_user]),

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
                'domain': domain,
                'target': 'current',
                'help': """
                    <p class="o_view_nocontent_smiling_face">
                        %s
                    </p>
                    <p>
                        %s
                        <br/>
                    </p>
                """ % (
                    _("Upload Pdfs to your agenda"),
                    _("Use this feature to store pdfs you would like to share with your members"),
                )
            }

    def action_points_kanban(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Action Points Kanban View',
            'view_mode': 'kanban,form,tree',
            'res_model': 'project.task',
            'target': 'current',
            'domain': [('project_id', '=', self.project_id.id)],
            'context': {'default_project_id': self.project_id.id},
        }

    def action_open_custom_composer(self):
        if not self.partner_ids:
            raise UserError(_("There are no attendees on these events"))
        template_id = self.env['ir.model.data']._xmlid_to_res_id('appointment.appointment_booked_mail_template',
                                                                 raise_if_not_found=False)
        # The mail is sent with datetime corresponding to the sending user TZ
        default_composition_mode = self.env.context.get('default_composition_mode',
                                                        self.env.context.get('composition_mode', 'comment'))
        compose_ctx = dict(
            default_composition_mode=default_composition_mode,
            default_model='calendar.event',
            default_res_ids=self.ids,
            default_template_id=template_id,
            default_partner_ids=self.partner_ids.ids,
            mail_tz=self.env.user.tz,
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _('Contact Attendees'),
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'context': compose_ctx,
        }

    @api.onchange('partner_ids')
    def compute_visible_users(self):
        for record in self:
            if record.product_id and record.partner_ids:
                record.product_id.product_document_ids.sudo().write(
                    {
                        'partner_ids': [(6, 0, record.partner_ids.ids)]
                    }
                )


class AgendaLines(models.Model):
    _name = 'agenda.lines'
    _description = 'Agenda Lines'

    calendar_id = fields.Many2one('calendar.event', string="Calendar")
    description = fields.Html(related='calendar_id.agenda_description')
    partner_ids = fields.Many2many('res.partner', string='Attendees')
    duration = fields.Float(related="calendar_id.duration", string='Duration')
    agenda_attachment_ids = fields.Many2many(comodel_name='ir.attachment', string="Attachments")
