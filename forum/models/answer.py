from base import *

class Answer(Node):
    class Meta(Node.Meta):
        proxy = True

    @property    
    def accepted(self):
        return self.marked

    @property
    def headline(self):
        return self.question.headline

    def get_absolute_url(self):
        return '%s#%s' % (self.question.get_absolute_url(), self.id)


class AnswerRevision(NodeRevision):
    class Meta:
        proxy = True