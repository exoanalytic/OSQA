from forum.models.action import ActionProxy
import settings

class VoteAction(ActionProxy):
    def update_node_score(self, inc):
        self.node.score += inc
        self.node.save()


class VoteUpAction(VoteAction):
    def repute_users(self):
        self.repute(self.node.author, int(settings.REP_GAIN_BY_UPVOTED))

    def process_action(self):
        self.update_node_score(1)

    def cancel_action(self):
        self.update_node_score(-1)


class VoteDownAction(VoteAction):
    def repute_users(self):
        self.repute(self.node.author, -int(settings.REP_LOST_BY_DOWNVOTED))
        self.repute(self.user, -int(settings.REP_LOST_BY_DOWNVOTING))

    def process_action(self):
        self.update_node_score(-1)

    def cancel_action(self):
        self.update_node_score(+1)


class VoteUpCommentAction(VoteUpAction):
    def repute_users(self):
        pass


class FlagAction(ActionProxy):
    def repute_users(self):
        self.repute(self.node.author, -int(settings.REP_LOST_BY_FLAGGED))

    def process_action(self):
        self.node.reset_flag_count_cache()

        if self.node.flag_count == int(settings.FLAG_COUNT_TO_HIDE_POST):
            self.repute(self.node.author, -int(settings.REP_LOST_BY_FLAGGED_3_TIMES))

        if self.node.flag_count == int(settings.FLAG_COUNT_TO_DELETE_POST):
            self.repute(self.node.author, -int(settings.REP_LOST_BY_FLAGGED_5_TIMES))
            #todo: issue a delete action


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
        self.node.save()

    def cancel_action(self):
        self.node.parent.extra_ref = None
        self.node.parent.save()
        self.node.marked = False
        self.node.save()


class FavoriteAction(ActionProxy):
    def process_action(self):
        self.node.reset_favorite_count_cache()

    def cancel_action(self):
        self.proccess_action()