"""Explicit class scoping for HTTP reads and content references.

No request-global ORM filtering: workers and reviewed migration commands retain
ordinary managers. Null ownership is unassigned, never a shared library.
"""
from django.db.models import Q
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission


def content_admin(user):
    from accounts.permissions import has_platform_admin_access
    return has_platform_admin_access(user)


def member_class(user):
    if not user or not user.is_authenticated or not user.is_active:
        return None
    profile = getattr(user, 'profile', None)
    if profile is None or not profile.class_group_id or not profile.class_group.is_active:
        return None
    if profile.class_role == 'class_head' and not profile.is_class_head:
        return None
    return profile.class_group


def upload_class(user):
    group = member_class(user)
    if group is None:
        raise PermissionDenied('Join an active class before creating class content.')
    return group


def visible(model, user):
    """A queryset that can safely be further narrowed by an endpoint."""
    qs = model.objects.all()
    if content_admin(user):
        return qs
    group = member_class(user)
    if group is None:
        return qs.none()
    name = model.__name__
    if name == 'SpotStation':
        from .models import Subject, Block
        subjects, blocks = visible(Subject, user), visible(Block, user)
        shared = Q(is_shared=True, subject__isnull=True, block__isnull=True)
        private = Q(is_shared=False) & (Q(subject__in=subjects) | Q(block__in=blocks))
        return qs.filter(shared | private).filter(
            Q(subject__isnull=True) | Q(subject__in=subjects)
        ).filter(Q(block__isnull=True) | Q(block__in=blocks))
    if name in {'Flashcard', 'ScheduleItem'}:
        qs = qs.filter(user=user)
        from .models import Subject, Block, SubBlock, Topic, Slide, QuizQuestion
        relations = {'subject': Subject, 'block': Block, 'sub_block': SubBlock,
                     'topic': Topic, 'slide': Slide, 'source_slide': Slide,
                     'source_question': QuizQuestion}
        fields = {field.name for field in model._meta.fields}
        for field, parent in relations.items():
            if field in fields:
                qs = qs.filter(Q(**{field + '__isnull': True}) | Q(**{field + '__in': visible(parent, user)}))
        return qs
    direct = {'Subject', 'Slide', 'Material', 'SlideDeck'}
    if name in direct:
        qs = qs.filter(class_group=group)
        if name in {'Slide', 'Material'}:
            for path in ('subject', 'block__subject', 'sub_block__block__subject'):
                qs = qs.filter(Q(**{path + '__isnull': True}) | Q(**{path + '__class_group': group}))
            from .models import Topic
            qs = qs.filter(Q(topic__isnull=True) | Q(topic__in=visible(Topic, user)))
        return qs
    paths = {
        'Block': 'subject__class_group', 'SubBlock': 'block__subject__class_group',
        'SlideContent': 'slide__class_group', 'SlideProcessingStatus': 'slide__class_group',
        'SlidePage': 'deck__class_group', 'SlideChunk': 'slide__class_group',
        'UserProgress': 'slide__class_group', 'UpcomingTest': 'subject__class_group',
    }
    if name in paths:
        if paths[name].startswith('slide__'):
            from .models import Slide
            return qs.filter(slide__in=visible(Slide, user))
        if name == 'UpcomingTest':
            from .models import SubBlock
            return qs.filter(subject__class_group=group).exclude(
                sub_blocks__in=SubBlock.objects.exclude(pk__in=visible(SubBlock, user)))
        return qs.filter(**{paths[name]: group})
    if name == 'Topic':
        return qs.filter(Q(sub_block__block__subject__class_group=group) |
                         Q(sub_block__isnull=True, block__subject__class_group=group)).filter(
                             Q(block__isnull=True) | Q(block__subject__class_group=group))
    if name == 'QuizQuestion':
        return qs.filter(subject__class_group=group).filter(
            Q(block__isnull=True) | Q(block__subject__class_group=group)
        ).filter(Q(sub_block__isnull=True) | Q(sub_block__block__subject__class_group=group)).filter(
            Q(source_slide__isnull=True) | Q(source_slide__class_group=group)
        ).filter(Q(source_material__isnull=True) | Q(source_material__class_group=group))
    raise ValueError(f'No class scope defined for {name}')


def require_visible(model, user, pk):
    if not isinstance(pk, (str, int)) or isinstance(pk, bool):
        raise ValidationError({'detail': 'Invalid content identifier.'})
    obj = visible(model, user).filter(pk=pk).first()
    if obj is None:
        raise NotFound('Content not found.')
    return obj


class ClassContentReferences(BasePermission):
    """Validate references before handlers invoke providers, extraction or credits."""
    def has_permission(self, request, view):
        from .models import Slide, SlideDeck, Material, Subject, Block, SubBlock, Topic
        if not request.user or not request.user.is_authenticated:
            return False
        references = {'slide': Slide, 'slide_id': Slide, 'deck': SlideDeck, 'deck_id': SlideDeck,
                      'material': Material, 'material_id': Material,
                      'subject': Subject, 'subject_id': Subject, 'block': Block, 'block_id': Block,
                      'sub_block': SubBlock, 'sub_block_id': SubBlock, 'topic': Topic, 'topic_id': Topic}
        for source in (getattr(view, 'kwargs', {}), request.query_params, request.data):
            for key, model in references.items():
                value = source.get(key)
                if value not in (None, '', 'null', 'undefined', 'None'):
                    if key == 'topic' and view.__class__.__name__ in {'TopicViewSet', 'generate_quiz'}:
                        model = SubBlock  # Deprecated serializer alias, not a Topic ID.
                    if key == 'topic' and view.__class__.__name__ == 'QuizAttemptViewSet':
                        require_quiz_topic(request.user, value)
                        continue
                    require_visible(model, request.user, value)
        return True


def require_quiz_topic(user, pk):
    """The attempt API accepts a Topic or its historical SubBlock alias."""
    from .models import Topic, SubBlock
    if not isinstance(pk, (str, int)) or isinstance(pk, bool):
        raise ValidationError({'detail': 'Invalid content identifier.'})
    topic = visible(Topic, user).filter(pk=pk).first()
    return topic if topic is not None else require_visible(SubBlock, user, pk)


def scoped_optional_parents(qs, user, relations):
    for field, parent in relations.items():
        qs = qs.filter(Q(**{field + '__isnull': True}) | Q(**{field + '__in': visible(parent, user)}))
    return qs


def visible_attempts(user):
    """Fail closed for historical attempts containing foreign source questions."""
    from .models import QuizAttempt, QuizQuestion, Subject, Slide, Block, SubBlock, Topic
    qs = QuizAttempt.objects.filter(user=user)
    if content_admin(user):
        return qs
    group = member_class(user)
    formal_ids = list(qs.filter(assessment__class_group=group).values_list('pk', flat=True)) if group else []
    snapshot_ids = list(qs.filter(snapshot_class=group).values_list('pk', flat=True)) if group else []
    qs = qs.filter(assessment__isnull=True, snapshot_class__isnull=True)
    qs = scoped_optional_parents(qs, user, {'subject': Subject, 'block': Block,
        'sub_block': SubBlock, 'topic': Topic, 'slide': Slide})
    question_ids = set(visible(QuizQuestion, user).values_list('pk', flat=True))
    foreign_ids = set(QuizQuestion.objects.exclude(pk__in=question_ids).values_list('pk', flat=True))
    allowed = []
    for pk, ids, snapshots in qs.values_list('pk', 'question_ids', 'question_snapshots'):
        if isinstance(ids, list) and all(isinstance(i, str) and (
                i in question_ids if snapshots else i not in foreign_ids) for i in ids):
            allowed.append(pk)
    ordinary = qs.filter(pk__in=allowed).exclude(
        responses__question__in=QuizQuestion.objects.exclude(pk__in=question_ids))
    return QuizAttempt.objects.filter(user=user).filter(Q(pk__in=ordinary) | Q(pk__in=formal_ids) | Q(pk__in=snapshot_ids))


def visible_quizzes(user):
    from .models import Quiz, QuizQuestion, Subject, Block, SubBlock
    qs = scoped_optional_parents(Quiz.objects.filter(user=user), user,
        {'subject': Subject, 'block': Block, 'sub_block': SubBlock})
    foreign = QuizQuestion.objects.exclude(pk__in=visible(QuizQuestion, user))
    return qs.exclude(questions__in=foreign).exclude(answers__question__in=foreign)
