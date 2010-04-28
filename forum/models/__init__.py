from question import Question ,QuestionRevision, QuestionSubscription
from answer import Answer, AnswerRevision
from tag import Tag, MarkedTag
from user import User, Activity, ValidationHash, AuthKeyUserAssociation, SubscriptionSettings
from repute import Badge, Award, Repute
from node import Node, NodeRevision, NodeMetaClass
from comment import Comment
from action import Action, ActionRepute
from utils import KeyValue

try:
    from south.modelsinspector import add_introspection_rules
    add_introspection_rules([], [r"^forum\.models\.\w+\.\w+"])
except:
    pass

from base import *

def is_new(sender, instance, **kwargs):
    try:
        instance._is_new = not bool(instance.id)
    except:
        pass

pre_save.connect(is_new)

__all__ = [
        'Node', 'NodeRevision',  
        'Question', 'QuestionSubscription', 'QuestionRevision',
        'Answer', 'AnswerRevision',
        'Tag', 'Comment', 'MarkedTag', 'Badge', 'Award', 'Repute',
        'Activity', 'ValidationHash', 'AuthKeyUserAssociation', 'SubscriptionSettings', 'KeyValue', 'User',
        'Action', 'ActionRepute',
        ]


from forum.modules import get_modules_script_classes

for k, v in get_modules_script_classes('models', models.Model).items():
    if not k in __all__:
        __all__.append(k)
        exec "%s = v" % k

NodeMetaClass.setup_relations()
BaseMetaClass.setup_denormalizes()