from base import *
import re

user_action = django.dispatch.Signal(providing_args=['instance'])

class ActionManager(models.Manager):
    use_for_related_fields = True

    def get_query_set(self):
        qs = super(ActionManager, self).get_query_set().filter(canceled=False)

        if self.model is not Action:
            return qs.filter(action_type=self.model.get_type())
        else:
            return qs

    def get(self, *args, **kwargs):
        action = super(ActionManager, self).get(*args, **kwargs)
        if self.model == Action:
            return action.leaf()
        return action

    def get_for_types(self, types, *args, **kwargs):
        kwargs['action_type__in'] = [t.get_type() for t in types]
        return self.get(*args, **kwargs)
        

class Action(models.Model):
    user = models.ForeignKey(User, related_name="actions")
    node = models.ForeignKey(Node, null=True, related_name="actions")
    action_type = models.CharField(max_length=16)
    action_date = models.DateTimeField(default=datetime.datetime.now)

    extra = models.CharField(max_length=255)

    canceled = models.BooleanField(default=False)
    canceled_by = models.ForeignKey(User, null=True, related_name="canceled_actions")
    canceled_at = models.DateTimeField(null=True)

    objects = ActionManager()

    def repute_users(self):
        pass

    def process_action(self):
        pass

    def cancel_action(self):
        pass

    def repute(self, user, value):
        repute = ActionRepute(action=self, user=user, value=value)
        repute.save()
        return repute

    def cancel_reputes(self):
        for repute in self.reputes.all():
            cancel = ActionRepute(action=self, user=repute.user, value=(-repute.value), by_canceled=True)
            cancel.save()

    def leaf(self):
        leaf_cls = ActionProxyMetaClass.types.get(self.action_type, None)

        if leaf_cls is None:
            return self

        leaf = leaf_cls()
        leaf.__dict__ = self.__dict__
        return leaf

    @classmethod
    def get_type(cls):
        return re.sub(r'action$', '', cls.__name__.lower())

    def save(self, *args, **kwargs):
        if not self.id:
            self.action_type = self.__class__.get_type()

        super(Action, self).save(*args, **kwargs)

        if self._is_new:
            self.repute_users()
            self.process_action()
            user_action.send(sender=self.__class__, instance=self)

    def cancel_or_delete(self, user=None):
        if self.action_date > (datetime.datetime.now() - datetime.timedelta(minutes=1)):
            for repute in self.reputes.all():
                repute.delete()
            self.delete()
        else:
            self.cancel(user)

    def delete(self):
        self.cancel_action()
        super(Action, self).delete()

    def cancel(self, user=None):
        if not self.canceled:
            self.canceled = True
            self.canceled_at = datetime.datetime.now()
            self.canceled_by = (user is None) and self.user or user
            self.save()
            self.cancel_reputes()
            self.cancel_action()

    @classmethod
    def get_current(cls, **kwargs):
        kwargs['canceled'] = False

        try:
            return cls.objects.get(**kwargs)
        except cls.MultipleObjectsReturned:
            #todo: log this stuff
            raise
        except cls.DoesNotExist:
            return None

    @classmethod
    def create_or_cancel(cls, issuer=None, **kwargs):
        issuer = (issuer is not None) and issuer or kwargs.get('user', None)        
        old = cls.get_current(**kwargs)

        if old is not None:
            old.cancel_or_delete(issuer)
            return old
        else:
            new = cls(**kwargs)
            new.save()
            return new

    class Meta:
        app_label = 'forum'

class ActionProxyMetaClass(models.Model.__metaclass__):
    types = {}

    def __new__(cls, *args, **kwargs):
        new_cls = super(ActionProxyMetaClass, cls).__new__(cls, *args, **kwargs)
        cls.types[new_cls.get_type()] = new_cls

        class Meta:
            proxy = True

        new_cls.Meta = Meta
        return new_cls

class ActionProxy(Action):
    __metaclass__ = ActionProxyMetaClass
    
    class Meta:
        proxy = True


class ActionRepute(models.Model):
    action = models.ForeignKey(Action, related_name='reputes')
    user = models.ForeignKey(User)
    value = models.IntegerField(default=0)
    by_canceled = models.BooleanField(default=False)

    @property
    def reputed_at(self):
        return self.by_canceled and self.action.canceled_at or self.action.action_date

    @property
    def positive(self):
        if self.value > 0: return self.value
        return 0

    @property
    def negative(self):
        if self.value < 0: return self.value
        return 0

    def save(self, *args, **kwargs):
        super(ActionRepute, self).save(*args, **kwargs)
        self.user.reputation += self.value
        self.user.save()

    def delete(self):
        self.user.reputation -= self.value
        self.user.save()
        super(ActionRepute, self).delete()

    class Meta:
        app_label = 'forum'

