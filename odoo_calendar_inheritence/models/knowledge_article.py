from odoo import models, fields, api
from odoo.exceptions import UserError

class KnowledgeArticle(models.Model):
    _inherit = 'knowledge.article'
    #
    # # name = fields.Char('Title', required=True)
    # body = fields.Html('Body', sanitize=False)
    calendar_id = fields.Many2one('calendar.event', string='Calendar Event')

    @api.model
    def create_article_with_attachments(self, name, attachment_ids):
        if not attachment_ids:
            raise UserError("No attachments provided.")

        # Create a new Knowledge article
        article = self.create({'name': name})

        # Attach documents to the newly created article
        for attachment in self.env['ir.attachment'].browse(attachment_ids):
            attachment.copy({
                'res_model': 'knowledge.article',
                'res_id': article.id,
            })
        return article
