from markupsafe import Markup
from odoo import models, fields, api
from odoo.exceptions import ValidationError

CLOSED_STATES = {
    '1_done': 'Done',
    '1_canceled': 'Canceled',
}


class OdooCalendarInheritence(models.Model):
    _inherit = 'calendar.event'

    # personal_stage_type_id = fields.Many2one('your.model.name', string='Personal Stage Type')
    milestone_id = fields.Many2one('project.milestone', string='Milestone')
    # product_id = fields.Many2one('product.product', string='Product')
    # video_attachment_ids = fields.Many2many(comodel_name='video.attachments')
    # product_qty = fields.Float(string='Quantity', default=1.0)
    # product_uom_id = fields.Many2one('uom.uom', string='Unit of Measure', related='product_id.uom_id', readonly=True)
    agenda_description = fields.Html(name="agenda_description", string="Description")
    mom_description = fields.Html(name="mom_description", string="Description")
    image = fields.Image(name="image", string="Image")
    attachment_ids = fields.Many2many(comodel_name='ir.attachment', string="Attachments")
    video_attachment_ids = fields.One2many(comodel_name='video.attachment', inverse_name='calendar_id',
                                           string="Attachments")
    # video_attachment_ids = fields.Many2many(comodel_name='video_attachment_ids', string="Video Attachments")

    parent_id = fields.Many2one('calendar.event', string='Parent Task', index=True, tracking=True)
    child_ids = fields.One2many('calendar.event', 'parent_id', string="Sub-tasks")

    project_id = fields.Many2one('project.project', string='Project',
                                 domain="['|', ('company_id', '=', False), ('company_id', '=?',  company_id)]",
                                 index=True, tracking=True, change_default=True)

    # allow_milestones = fields.Boolean(related='project_id.allow_milestones')
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
    # # milestone_id = fields.Many2one(
    # #         'project.milestone',
    # #         'Milestone',
    # #         domain="[('project_id', '=', project_id)]",
    # #         compute='_compute_milestone_id',
    # #         readonly=False,
    # #         store=True,
    # #         tracking=True,
    # #         index='btree_not_null',
    # #         help="Deliver your services automatically when a milestone is reached by linking it to a sales order item."
    # #     )
    partner_id = fields.Many2one('res.partner',
                                 string='Customer', recursive=True, tracking=True, store=True, readonly=False,
                                 domain="['|', ('company_id', '=?', company_id), ('company_id', '=', False)]")

    company_id = fields.Many2one('res.company', string='Company', store=True, readonly=False, recursive=True, copy=True)

    tag_ids = fields.Many2many('project.tags', string='Tags')

    # Test
    new_project_id = fields.Many2one('project.project', string='Action Point')
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
                                       string='Product Lines')
    product_document_ids = fields.Many2many(comodel_name='product.document', compute='_compute_product_documents',
                                            string='Product Documents')

    article_exists = fields.Boolean(compute='_compute_article_exists', store=False)
    article_id = fields.Many2one('knowledge.article', string='Related Article')
    description_article_id = fields.Many2one('knowledge.article', string='Related Description Article')
    task_created = fields.Boolean(string="Task Created", default=False)
    description = fields.Html(string="Description")

    # -------------------------------------------------------------------
    #                         KNOWLEDGE APP WORK
    # -------------------------------------------------------------------

    # def create_knowledge_article(self, description):
    #     knowledge_article = self.env['knowledge.article'].create({
    #         'name': 'Meeting Minutes',  # Title of the article
    #         'body': description,  # Content of the article
    #     })
    #     return knowledge_article

    # @api.model
    # def create(self, vals):
    #     res = super(OdooCalendarInheritence, self).create(vals)
    #     if res.mom_description:
    #         res.create_knowledge_article(res.mom_description)
    #     return res
    #
    # def write(self, vals):
    #     res = super(OdooCalendarInheritence, self).write(vals)
    #     for record in self:
    #         if 'mom_description' in vals and record.mom_description:
    #             record.create_knowledge_article(record.mom_description)
    #     return res

    @api.depends('article_id')
    def _compute_article_exists(self):
        for record in self:
            record.article_exists = bool(record.article_id)

    # def action_create_html_all(self):
    #     if not self.product_line_ids:
    #         raise ValidationError("Please add data before making an Article!")
    #
    #     counter = 1
    #     company_id = self.env.company.id
    #     html_content = """
    #                 <table class='table'>
    #                     <thead>
    #                         <tr style="border: 0px; background-color: #ffffff;">
    #                             <th style="padding: 10px; border: 0px;">ID</th>
    #                             <th style="padding: 10px; border: 0px;">Description</th>
    #                             <th style="padding: 10px; border: 0px;">Presenter</th>
    #                             <th style="padding: 10px; border: 0px;">Start Time</th>
    #                             <th style="padding: 10px; border: 0px;">End Time</th>
    #                             <th style="padding: 10px; border: 0px;">Document</th>
    #                         </tr>
    #                     </thead>
    #                     <tbody>
    #     """
    #
    #     mom_description_content = ""
    #
    #     # Build the table rows for each agenda line
    #     for line in self.product_line_ids:
    #         product_documents = line.product_id.product_document_ids
    #         print('----------------->',product_documents)
    #         if product_documents:
    #             active_id = product_documents[0].id
    #             file_name = product_documents[0].name or "No File Name"
    #             view_button = Markup(
    #                 '<a href="/web?#active_id=%d&amp;action=qxm_product_pdf_annotation_tool.product_pdf_annotation&amp;cids=%d" style="padding: 5px 10px; color: #FFFFFF; text-decoration: none; background-color: #875A7B; border: 1px solid #875A7B; border-radius: 3px; display: flex; align-items: center; gap: 5px; max-width: 200px; text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' +
    #                 '<i class="fa fa-file" style="font-size: 16px; margin-right: 5px;"></i>' +
    #                 '%s</a>') % (active_id, company_id, file_name)
    #         else:
    #             view_button = Markup(
    #                 '<span style="padding: 5px 10px; color: #000000; background-color: #F0F0F0; border-radius: 3px; display: flex; align-items: center; gap: 5px; max-width: 200px; text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' +
    #                 '<i class="fa fa-file" style="font-size: 16px; margin-right: 5px;"></i>' +
    #                 'No Document</span>'
    #             )
    #
    #         # Get the presenter names as a comma-separated string
    #         presenters = ', '.join(presenter.name for presenter in line.presenter_id)
    #
    #         # Format each agenda line as a table row
    #         html_content += f"""
    #         <tr style="border: 0px;">
    #             <td style="padding: 10px; border: 0px;">{counter}</td>
    #             <td style="padding: 10px; border: 0px;">{line.description or 'N/A'}</td>
    #             <td style="padding: 10px; border: 0px;">{presenters or 'N/A'}</td>
    #             <td style="padding: 10px; border: 0px;">{line.start_date}</td>
    #             <td style="padding: 10px; border: 0px;">{line.end_date}</td>
    #             <td style="padding: 10px; border: 0px; text-align: center;">{view_button}</td>
    #         </tr>
    #         """
    #
    #         mom_description_content += f"""
    #                 Presenter: {presenters or 'N/A'},<br> Start Date: {line.start_date},<br> End Date: {line.end_date}<br> <br> <b>Description:</b> {line.description or 'N/A'}<br><br><hr>
    #                 """
    #
    #         counter += 1
    #
    #     html_content += """
    #                 </tbody>
    #             </table>
    #         """
    #
    #     # Include event details and agenda table in the body of the article
    #     body_content = f"""
    #         <div>
    #             <h3 style="text-align: center;"><strong>{self.name}</strong></h3>
    #             <p><strong>Start Date:</strong> {self.start_date}</p>
    #             <p><strong>End Date:</strong> {self.end_date}</p>
    #             <p><strong>Organizer:</strong> {self.user_id.name}</p>
    #             <hr/>
    #             {html_content}
    #         </div>
    #     """
    #
    #     article_values = {
    #         'name': self.name,  # Use the calendar event name for the article
    #         'body': body_content,
    #         'calendar_id': self.id,
    #     }
    #
    #     # Create the knowledge article with the prepared values
    #     article = self.env['knowledge.article'].sudo().create(article_values)
    #     self.article_id = article.id
    #     # Write data to mom_description field
    #     self.mom_description = mom_description_content

    def action_create_agenda_descriptions(self):
        if not self.product_line_ids:
            raise ValidationError("Please add data before making an Article!")
        if not self.description_article_id:
            counter = 1
            company_id = self.env.company.id
            mom_description_content = ""
            # Build the table rows for each agenda line
            for line in self.product_line_ids:
                product_documents = line.product_id.product_document_ids
                for index in range(len(product_documents)):
                    if product_documents[index]:
                        mom_description_content += f"""
                                {line.description or 'N/A'}<hr>
                                """

                        counter += 1
            article_values = {
                'name': f"{self.name}, (Agenda Items)",  # Name for the description, for that Agenda!
                'body': mom_description_content,
                'calendar_id': self.id,
            }

            description_article = self.env['knowledge.article'].sudo().create(article_values)
            self.description_article_id = description_article
            return self.action_view_description_article()
        else:
            counter = 1
            company_id = self.env.company.id
            mom_description_content = ""
            # Build the table rows for each agenda line
            for line in self.product_line_ids:
                product_documents = line.product_id.product_document_ids
                for index in range(len(product_documents)):
                    if product_documents and product_documents[index]:
                        mom_description_content += f"""
                                            {line.description or 'N/A'}<hr>
                                            """

                        counter += 1
            article_values = {
                'name': f"{self.name}, (Agenda Items)",  # Name for the description, for that Agenda!
                'body': mom_description_content,
                'calendar_id': self.id,
            }
            self.description_article_id.sudo().write(
                article_values
            )
            return self.action_view_description_article()

    def action_create_html_all(self):
        if not self.product_line_ids:
            raise ValidationError("Please add data before making an Article!")

        counter = 1
        company_id = self.env.company.id
        html_content = """
                    <table class='table'>
                        <thead>
                            <tr style="border: 0px; background-color: #ffffff;">
                                <th style="padding: 10px; border: 0px;">ID</th>
                                <th style="padding: 10px; border: 0px;">Agenda Item</th>
                                <th style="padding: 10px; border: 0px;">Presenter</th>
                                <th style="padding: 10px; border: 0px;">Time</th>
                                <th style="padding: 10px; border: 0px;">Document</th>
                            </tr>
                        </thead>
                        <tbody>
        """

        mom_description_content = ""

        # Build the table rows for each agenda line
        for line in self.product_line_ids:
            product_documents = line.product_id.product_document_ids
            for index in range(len(product_documents)):
                if product_documents and product_documents[index]:
                    active_id = product_documents[index].id
                    file_name = product_documents[index].name or "No File Name"
                    view_button = Markup(
                        '<a href="/web?#active_id=%d&amp;action=qxm_product_pdf_annotation_tool.product_pdf_annotation&amp;cids=%d" style="padding: 5px 10px; color: #FFFFFF; text-decoration: none; background-color: #875A7B; border: 1px solid #875A7B; border-radius: 3px; display: flex; align-items: center; gap: 5px; max-width: 200px; text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' +
                        '<i class="fa fa-file" style="font-size: 16px; margin-right: 5px;"></i>' +
                        '%s</a>') % (active_id, company_id, file_name)
                else:
                    view_button = Markup(
                        '<span style="padding: 5px 10px; color: #000000; background-color: #F0F0F0; border-radius: 3px; display: flex; align-items: center; gap: 5px; max-width: 200px; text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' +
                        '<i class="fa fa-file" style="font-size: 16px; margin-right: 5px;"></i>' +
                        'No Document</span>'
                    )

                # Get the presenter names as a comma-separated string
                presenters = ', '.join(presenter.name for presenter in line.presenter_id)

                # Format each agenda line as a table row
                html_content += f"""
                <tr style="border: 0px;">
                    <td style="padding: 10px; border: 0px;">{counter}</td>
                    <td style="padding: 10px; border: 0px;">{line.description or 'N/A'}</td>
                    <td style="padding: 10px; border: 0px;">{presenters or 'N/A'}</td>
                    <td style="padding: 10px; border: 0px;">{line.time}</td>
                    <td style="padding: 10px; border: 0px; text-align: center;">{view_button}</td>
                </tr>
                """

                mom_description_content += f"""
                        Agenda Item:</b> {line.description or 'N/A'}<br><br><hr>
                        """

                counter += 1

        html_content += """
                    </tbody>
                </table>
            """

        # Include event details and agenda table in the body of the article
        body_content = f"""
            <div>
                <h3 style="text-align: center;"><strong>{self.name}</strong></h3>
                <p><strong>Start Date:</strong> {self.start_date if self.start_date else ' '}</p>
                <p><strong>Organizer:</strong> {self.user_id.name}</p>
                <hr/>
                {html_content}
            </div>
        """

        article_values = {
            'name': self.name,  # Use the calendar event name for the article
            'body': body_content,
            'calendar_id': self.id,
        }

        # Create the knowledge article with the prepared values
        article = self.env['knowledge.article'].sudo().create(article_values)
        self.article_id = article.id
        # Write data to mom_description field
        self.mom_description = mom_description_content

    def action_update_html_all(self):
        company_id = self.env.company.id

        existing_article = self.env['knowledge.article'].search([('calendar_id', '=', self.id)], limit=1)
        if not existing_article:
            raise ValidationError("No Article for these records in Knowledge Module!")

        counter = 1
        html_content = """
                    <table class='table'>
                        <thead>
                            <tr style="border: 0px; background-color: #ffffff;">
                                <th style="padding: 10px; border: 0px;">ID</th>
                                <th style="padding: 10px; border: 0px;">Agenda Item</th>
                                <th style="padding: 10px; border: 0px;">Presenter</th>
                                <th style="padding: 10px; border: 0px;">Time</th>
                                <th style="padding: 10px; border: 0px;">Document</th>
                            </tr>
                        </thead>
                        <tbody>
        """

        mom_description_content = ""

        # Build the table rows for each agenda line
        for line in self.product_line_ids:

            product_documents = line.product_id.product_document_ids
            for index in range(len(product_documents)):

                if product_documents and product_documents[index]:
                    active_id = product_documents[index].id
                    file_name = product_documents[index].name or "No File Name"
                    view_button = Markup(
                        '<a href="/web?#active_id=%d&amp;action=qxm_product_pdf_annotation_tool.product_pdf_annotation&amp;cids=%d" style="padding: 5px 10px; color: #FFFFFF; text-decoration: none; background-color: #875A7B; border: 1px solid #875A7B; border-radius: 3px; display: flex; align-items: center; gap: 5px; max-width: 200px; text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' +
                        '<i class="fa fa-file" style="font-size: 16px; margin-right: 5px;"></i>' +
                        '%s</a>') % (active_id, company_id, file_name)
                else:
                    view_button = Markup(
                        '<span style="padding: 5px 10px; color: #000000; background-color: #F0F0F0; border-radius: 3px; display: flex; align-items: center; gap: 5px; max-width: 200px; text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' +
                        '<i class="fa fa-file" style="font-size: 16px; margin-right: 5px;"></i>' +
                        'No Document</span>'
                    )

                # Get the presenter names as a comma-separated string
                presenters = ', '.join(presenter.name for presenter in line.presenter_id)

                # Format each agenda line as a table row
                html_content += f"""
                <tr style="border: 0px;">
                    <td style="padding: 10px; border: 0px;">{counter}</td>
                    <td style="padding: 10px; border: 0px;">{line.description or 'N/A'}</td>
                    <td style="padding: 10px; border: 0px;">{presenters or 'N/A'}</td>
                    <td style="padding: 10px; border: 0px;">{line.time}</td>
                    <td style="padding: 10px; border: 0px; text-align: center;">{view_button}</td>
                </tr>
            """

                mom_description_content += f"""
                        {line.description or 'N/A'}<hr>
                        """

                counter += 1

        html_content += """
                    </tbody>
                </table>
            """

        # Include event details and agenda table in the body of the article
        body_content = f"""
            <div>
                <h3 style="text-align: center;"><strong>{self.name}</strong></h3>
                <p><strong>Start Date:</strong> {self.start_date if self.start_date else ' '}</p>
                <p><strong>Organizer:</strong> {self.user_id.name}</p>
                <hr/>
                {html_content}
            </div>
        """

        # Update the article with the new content
        self.article_id.sudo().write({
            'name': self.name,
            'body': body_content,
        })

        # Write data to mom_description field
        self.mom_description = mom_description_content

    def action_view_knowledge_article(self):
        self.ensure_one()
        if self.article_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Knowledge Article',
                'res_model': 'knowledge.article',
                'view_mode': 'form',
                'res_id': self.article_id.id,
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


class AgendaLines(models.Model):
    _name = 'agenda.lines'
    _description = 'Agenda Lines'

    calendar_id = fields.Many2one('calendar.event', string="Calendar")
    description = fields.Html(related='calendar_id.agenda_description')
    partner_ids = fields.Many2many('res.partner', string='Attendees')
    duration = fields.Float(related="calendar_id.duration", string='Duration')
    agenda_attachment_ids = fields.Many2many(comodel_name='ir.attachment', string="Attachments")
