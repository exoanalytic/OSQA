from forum.models.action import ActionProxy
import settings

class VoteUpAction(ActionProxy):
    def repute_users(self):
        self.repute(self.node.author, int(settings.REP_GAIN_BY_UPVOTED))

    def proccess_action(self):
        self.node.score += 1
        self.node.save()

    def cancel_action(self):
        self.node.score -= 1
        self.node.save()

class VoteDownAction(ActionProxy):
    def repute_users(self):
        self.repute(self.node.author, -int(settings.REP_LOST_BY_DOWNVOTED))

    def proccess_action(self):
        self.node.score -= 1
        self.node.save()

    def cancel_action(self):
        self.node.score += 1
        self.node.save()


class FavoriteAction(ActionProxy):
    def proccess_action(self):
        self.node.reset_favorite_count_cache()

    def cancel_action(self):
        self.proccess_action()