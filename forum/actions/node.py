from django.utils.html import strip_tags
from django.utils.translation import ugettext as _
from forum.models.action import ActionProxy
from forum.models import Comment, Question, Answer

class NodeEditAction(ActionProxy):
    def create_revision_data(self, initial=False, **data):
        revision_data = dict(summary=data.get('summary', (initial and _('Initial revision' or ''))), body=data['text'])

        if data.get('title', None):
            revision_data['title'] = strip_tags(data['title'].strip())

        if data.get('tags', None):
            revision_data['tagnames'] = data['tags'].strip()

        return revision_data

class AskAction(NodeEditAction):
     def process_data(self, **data):
        question = Question(author=self.user)
        question.create_revision(user=self.user, **self.create_revision_data(True, **data))
        self.node = question

class AnswerAction(NodeEditAction):
     def process_data(self, **data):
        answer = Answer(author=self.user, parent=data['question'])
        answer.create_revision(user=self.user, **self.create_revision_data(True, **data))
        self.node = answer


class CommentAction(ActionProxy):
    def process_data(self, text='', parent=None):
        comment = Comment(author=self.user, parent=parent)
        comment.create_revision(user=self.user, body=text)
        self.node = comment

class ReviseAction(NodeEditAction):
    def process_data(self, **data):
        revision_data = self.create_revision_data(**data)
        revision = self.node.create_revision(self.user, revise=self, **revision_data)
        self.extra = revision.id

class RetagAction(ActionProxy):
    def process_data(self, tagnames=''):
        active = self.node.active_revision
        revision_data = dict(summary=_('Retag'), title=active.title, tagnames=strip_tags(tagnames.strip()), body=active.body)
        self.node.create_revision(self.user, revise=self, **revision_data)

class RollbackAction(ActionProxy):
    def process_data(self, activate=None):
        previous = self.node.active_revision
        self.node.activate_revision(self.user, activate, self)
        self.extra = "%d:%d" % (previous.revision, activate.revision)