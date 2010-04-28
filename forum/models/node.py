from base import *
from tag import Tag

import markdown
from django.utils.safestring import mark_safe
from django.utils.html import strip_tags
from forum.utils.html import sanitize_html

class NodeContent(models.Model):
    title      = models.CharField(max_length=300)
    tagnames   = models.CharField(max_length=125)
    author     = models.ForeignKey(User, related_name='%(class)ss')
    body       = models.TextField()

    @property
    def user(self):
        return self.author

    @property
    def html(self):
        return mark_safe(sanitize_html(markdown.markdown(self.body)))

    @property
    def headline(self):
        return self.title

    def tagname_list(self):
        if self.tagnames:
            return [name for name in self.tagnames.split(u' ')]
        else:
            return []

    def tagname_meta_generator(self):
        return u','.join([unicode(tag) for tag in self.tagname_list()])

    class Meta:
        abstract = True
        app_label = 'forum'

class NodeMetaClass(BaseMetaClass):
    types = {}

    def __new__(cls, *args, **kwargs):
        new_cls = super(NodeMetaClass, cls).__new__(cls, *args, **kwargs)

        if not new_cls._meta.abstract and new_cls.__name__ is not 'Node':
            NodeMetaClass.types[new_cls.get_type()] = new_cls

        return new_cls

    @classmethod
    def setup_relations(cls):
        for node_cls in NodeMetaClass.types.values():
            NodeMetaClass.setup_relation(node_cls)        

    @classmethod
    def setup_relation(cls, node_cls):
        name = node_cls.__name__.lower()

        def children(self):
            return node_cls.objects.filter(parent=self)

        def parent(self):
            p = self.__dict__.get('_%s_cache' % name, None)

            if p is None and (self.parent is not None) and self.parent.node_type == name:
                p = self.parent.leaf
                self.__dict__['_%s_cache' % name] = p

            return p

        Node.add_to_class(name + 's', property(children))
        Node.add_to_class(name, property(parent))


node_create = django.dispatch.Signal(providing_args=['instance'])
node_edit = django.dispatch.Signal(providing_args=['instance'])

class NodeManager(CachedManager):
    use_for_related_fields = True

    def get_query_set(self):
        qs = super(NodeManager, self).get_query_set().filter(deleted=False)

        if self.model is not Node:
            return qs.filter(node_type=self.model.get_type())
        else:
            return qs

    def get(self, *args, **kwargs):
        node = super(NodeManager, self).get(*args, **kwargs)
        if self.model == Node:
            return node.leaf
        return node

    def get_for_types(self, types, *args, **kwargs):
        kwargs['node_type__in'] = [t.get_type() for t in types]
        return self.get(*args, **kwargs)


class Node(BaseModel, NodeContent, DeletableContent):
    __metaclass__ = NodeMetaClass

    node_type            = models.CharField(max_length=16, default='node')
    parent               = models.ForeignKey('Node', related_name='children', null=True)
    abs_parent           = models.ForeignKey('Node', related_name='all_children', null=True)

    added_at             = models.DateTimeField(default=datetime.datetime.now)

    score                 = models.IntegerField(default=0)

    last_edited_at        = models.DateTimeField(null=True, blank=True)
    last_edited_by        = models.ForeignKey(User, null=True, blank=True, related_name='last_edited_%(class)ss')

    last_activity_at     = models.DateTimeField(null=True, blank=True)
    last_activity_by     = models.ForeignKey(User, null=True)

    tags                 = models.ManyToManyField('Tag', related_name='%(class)ss')
    active_revision       = models.OneToOneField('NodeRevision', related_name='active', null=True)

    extra_ref = models.ForeignKey('Node', null=True)
    extra_count = models.IntegerField(default=0)
    
    marked = models.BooleanField(default=False)
    wiki = models.BooleanField(default=False)

    comment_count = DenormalizedField("children", node_type="comment", canceled=False)
    flag_count = DenormalizedField("actions", action_type="flag", canceled=False)

    objects = NodeManager()

    @classmethod
    def cache_key(cls, pk):
        return '%s.node:%s' % (settings.APP_URL, pk)

    @classmethod
    def get_type(cls):
        return cls.__name__.lower()

    @property
    def leaf(self):
        leaf_cls = NodeMetaClass.types.get(self.node_type, None)

        if leaf_cls is None:
            return self

        leaf = leaf_cls()
        leaf.__dict__ = self.__dict__
        return leaf

    @property    
    def absolute_parent(self):
        if not self.abs_parent_id:
            return self.leaf

        return self.abs_parent.leaf

    @property
    def summary(self):
        return strip_tags(self.html)[:300]

    def update_last_activity(self, user):
        self.last_activity_by = user
        self.last_activity_at = datetime.datetime.now()

        if self.parent:
            self.parent.update_last_activity(user)

    def create_revision(self, user, **kwargs):
        revision = NodeRevision(author=user, **kwargs)
        
        if not self.id:
            self.author = user
            self.save()
            revision.revision = 1
        else:
            revision.revision = self.revisions.aggregate(last=models.Max('revision'))['last'] + 1

        revision.node_id = self.id
        revision.save()
        self.activate_revision(user, revision)

    def activate_revision(self, user, revision):
        self.title = revision.title
        self.tagnames = revision.tagnames
        self.body = revision.body

        old_revision = self.active_revision
        self.active_revision = revision

        if not old_revision:
            signal = node_create
        else:
            self.last_edited_at = datetime.datetime.now()
            self.last_edited_by = user
            signal = node_edit

        self.update_last_activity(user)
        self.save()
        signal.send(sender=self.__class__, instance=self)

    def get_tag_list_if_changed(self):
        dirty = self.get_dirty_fields()

        if 'tagnames' in dirty:
            new_tags = self.tagname_list()
            old_tags = dirty['tagnames']

            if old_tags is None or not old_tags:
                old_tags = []
            else:
                old_tags = [name for name in dirty['tagnames'].split(u' ')]

            tag_list = []

            for name in new_tags:
                try:
                    tag = Tag.objects.get(name=name)
                except:
                    tag = Tag.objects.create(name=name, created_by=self.last_edited_by or self.author)

                tag_list.append(tag)

                if not name in old_tags:
                    tag.used_count = tag.used_count + 1
                    if tag.deleted:
                        tag.unmark_deleted()
                    tag.save()

            for name in [n for n in old_tags if not n in new_tags]:
                tag = Tag.objects.get(name=name)
                tag.used_count = tag.used_count - 1
                if tag.used_count == 0:
                    tag.mark_deleted(self.last_edited_by or self.author)
                tag.save()

            return tag_list

        return None

    def save(self, *args, **kwargs):
        if not self.id:
            self.node_type = self.get_type()

        if self.parent_id and not self.abs_parent_id:
            self.abs_parent = self.parent.absolute_parent
            
        tags = self.get_tag_list_if_changed()
        super(Node, self).save(*args, **kwargs)
        if tags is not None: self.tags = tags

    def __unicode__(self):
        return self.title

    class Meta:
        app_label = 'forum'


class NodeRevision(BaseModel, NodeContent):
    node       = models.ForeignKey(Node, related_name='revisions')
    summary    = models.CharField(max_length=300)
    revision   = models.PositiveIntegerField()
    revised_at = models.DateTimeField(default=datetime.datetime.now)

    class Meta:
        unique_together = ('node', 'revision')
        app_label = 'forum'


class FavoriteNode(models.Model):
    node          = models.ForeignKey(Node, "favorites")
    user          = models.ForeignKey(User, related_name='user_favorite_nodes')
    added_at      = models.DateTimeField(default=datetime.datetime.now)

    class Meta:
        unique_together = ('node', 'user')
        app_label = 'forum'

    def __unicode__(self):
        return '[%s] favorited at %s' %(self.user, self.added_at)

    def _update_question_fav_count(self, diff):
        self.question.favourite_count = self.question.favourite_count + diff
        self.question.save()

    def save(self, *args, **kwargs):
        super(FavoriteNode, self).save(*args, **kwargs)
        if self._is_new:
            self._update_question_fav_count(1)

    def delete(self):
        self._update_question_fav_count(-1)
        super(FavoriteNode, self).delete()

