from base import Setting, SettingSet
from forms import StringListWidget

from django.utils.translation import ugettext_lazy as _
from django.forms.widgets import Textarea

MODERATION_SET = SettingSet('moderation', _('Moderation Settings'), _("Define the moderation workflow of your site"), 100)

FLAG_TYPES = Setting('FLAG_TYPES',
["Spam", "Advertising", "Offensive, Abusive, or Inappropriate", "Content violates terms of use", "Copyright Violation",
 "Misleading", "Someone is not being nice", "Not relevant/off-topic", "Other"],
MODERATION_SET, dict(
label = _("Flag Reasons"),
help_text = _("Create some flag reasons to use in the flag post popup."),
widget=StringListWidget))