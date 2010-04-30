from django.utils.translation import ugettext as _
from django.db.models import F
from forum.models.action import ActionProxy
import settings

class VoteAction(ActionProxy):
    def update_node_score(self, inc):
        self.node.score = F('score') + inc
        self.node.save()

    def describe_vote(self, vote_desc, viewer=None):
        return _("%(user)s %(vote_desc)s %(post_desc)s") % {
            'user': self.hyperlink(self.user.get_profile_url(), self.friendly_username(viewer, self.user)),
            'vote_desc': vote_desc, 'post_desc': self.describe_node(viewer, self.node)
        }


class VoteUpAction(VoteAction):
    def repute_users(self):
        self.repute(self.node.author, int(settings.REP_GAIN_BY_UPVOTED))

    def process_action(self):
        self.update_node_score(1)

    def cancel_action(self):
        self.update_node_score(-1)

    def describe(self, viewer=None):
        return self.describe_vote(_("voted up"), viewer)

class VoteDownAction(VoteAction):
    def repute_users(self):
        self.repute(self.node.author, -int(settings.REP_LOST_BY_DOWNVOTED))
        self.repute(self.user, -int(settings.REP_LOST_BY_DOWNVOTING))

    def process_action(self):
        self.update_node_score(-1)

    def cancel_action(self):
        self.update_node_score(+1)

    def describe(self, viewer=None):
        return self.describe_vote(_("voted down"), viewer)


class VoteUpCommentAction(VoteUpAction):
    def repute_users(self):
        pass

    def describe(self, viewer=None):
        return self.describe_vote(_("liked"), viewer)


class FlagAction(ActionProxy):
    def repute_users(self):
        self.repute(self.node.author, -int(settings.REP_LOST_BY_FLAGGED))

    def process_action(self):
        self.node.reset_flag_count_cache()

        if self.node.flag_count == int(settings.FLAG_COUNT_TO_HIDE_POST):
            self.repute(self.node.author, -int(settings.REP_LOST_BY_FLAGGED_3_TIMES))

        if self.node.flag_count == int(settings.FLAG_COUNT_TO_DELETE_POST):
            self.repute(self.node.author, -int(settings.REP_LOST_BY_FLAGGED_5_TIMES))
            if not self.node.deleted:
                DeleteAction(node=self.node, user=self.user, extra="BYFLAGGED").save()

        def cancel_action(self):
            self.node.reset_flag_count_cache()

    def describe(self, viewer=None):
        return _("%(user)s flagged %(post_desc)s: %(reason)s") % {
            'user': self.hyperlink(self.user.get_profile_url(), self.friendly_username(viewer, self.user)),
            'post_desc': self.describe_node(viewer, self.node), 'reason': self.extra
        }


class AcceptAnswerAction(ActionProxy):
    def repute_users(self):
        if (self.user == self.node.parent.author) and (not self.user == self.node.author):
            self.repute(self.user, int(settings.REP_GAIN_BY_ACCEPTING))

        if self.user != self.node.author:
            self.repute(self.node.author, int(settings.REP_GAIN_BY_ACCEPTED))

    def process_action(self):
        self.node.parent.extra_ref = self.node
        self.node.parent.save()
        self.node.marked = True
        self.node.extra_action = self
        self.node.save()

    def cancel_action(self):
        self.node.parent.extra_ref = None
        self.node.parent.save()
        self.node.marked = False
        self.node.extra_action = None
        self.node.save()

    def describe(self, viewer=None):
        answer = self.node
        question = answer.parent

        if self.user == question.author:
            asker = (self.user == viewer) and _("your") or _("his")
        else:
            asker = self.hyperlink(question.author.get_profile_url(), question.author.username)

        return _("%(user)s accepted %(answerer)s answer on %(asker)s question %(question)s") % {
            'user': self.hyperlink(self.user.get_profile_url(), self.friendly_username(viewer, self.user)),
            'answerer': self.hyperlink(answer.author.get_profile_url(), self.friendly_username(viewer, answer.author.username)),
            'asker': asker,
            'question': self.hyperlink(question.get_absolute_url(), question.title)
        }


class FavoriteAction(ActionProxy):
    def process_action(self):
        self.node.reset_favorite_count_cache()

    def cancel_action(self):
        self.proccess_action()

    def describe(self, viewer=None):
        return _("%(user)s marked %(post_desc)s as favorite") % {
            'user': self.hyperlink(self.user.get_profile_url(), self.friendly_username(viewer, self.user)),
            'post_desc': self.describe_node(viewer, self.node),
        }


class DeleteAction(ActionProxy):
    def process_action(self):
        self.node.deleted = self
        self.node.save()

    def cancel_action(self):
        self.node.deleted = None
        self.node.save()

    def describe(self, viewer=None):
        return _("%(user)s deleted %(post_desc)s: %(reason)s") % {
            'user': self.hyperlink(self.user.get_profile_url(), self.friendly_username(viewer, self.user)),
            'post_desc': self.describe_node(viewer, self.node), 'reason': self.reason(),
        }

    def reason(self):
        if self.extra != "BYFLAGGED":
            return self.extra
        else:
            return _("flagged by multiple users: ") + "; ".join([f.extra for f in FlagAction.objects.filter(node=self.node)])