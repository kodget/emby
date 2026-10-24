"""Validate the redundant ancestry fields used by the legacy content API."""
from rest_framework import serializers
from .class_access import visible


class ClassScopedRelationsMixin:
    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        if request:
            for field in fields.values():
                relation = getattr(field, 'child_relation', field)
                queryset = getattr(relation, 'queryset', None)
                if queryset is not None and queryset.model.__name__ in {
                    'Subject', 'Block', 'SubBlock', 'Topic', 'Slide', 'Material', 'SlideDeck', 'QuizQuestion',
                }:
                    relation.queryset = visible(queryset.model, request.user)
        return fields


def validate_ancestry(attrs, instance=None, *, topic_record=False):
    names = ('sub_block', 'block') if topic_record else ('topic', 'sub_block', 'block', 'subject')
    values = {name: attrs.get(name, getattr(instance, name, None)) for name in names}

    def inherit(name, parent):
        current = values[name]
        if current is not None and current != parent:
            raise serializers.ValidationError({name: 'This selection does not belong to the selected hierarchy.'})
        if name in attrs and attrs[name] is None and parent is not None:
            raise serializers.ValidationError({name: 'This parent is required by the selected child.'})
        values[name] = parent
        if parent is not None:
            attrs[name] = parent

    topic = values.get('topic')
    if topic is not None:
        inherit('sub_block', topic.sub_block)
        topic_block = topic.sub_block.block if topic.sub_block else topic.block
        if topic.block_id and topic.block != topic_block:
            raise serializers.ValidationError({'topic': 'This topic has inconsistent parents; an administrator must repair it.'})
        if topic_block is None:
            raise serializers.ValidationError({'topic': 'This topic has no module.'})
        inherit('block', topic_block)
    if values.get('sub_block') is not None:
        inherit('block', values['sub_block'].block)
    if not topic_record and values.get('block') is not None:
        inherit('subject', values['block'].subject)
    if topic_record and values['block'] is None:
        raise serializers.ValidationError({'block': 'Select a module or submodule.'})
    if not topic_record and (values['subject'] is None or values['block'] is None):
        raise serializers.ValidationError({'block': 'Select a course and module, or a child within them.'})
    return attrs


class StableHierarchyMixin(ClassScopedRelationsMixin):
    """Moving a node requires a separate operation that also repairs descendants."""
    parent_fields = ()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is None and attrs.get('id') and self.Meta.model.objects.filter(pk=attrs['id']).exists():
            raise serializers.ValidationError({'id': 'This identifier is unavailable. Choose a different identifier.'})
        if self.instance:
            for name in ('id', *self.parent_fields):
                current = getattr(self.instance, name)
                # Filling a missing redundant parent from the unchanged child repairs
                # legacy metadata without moving the node or its descendants.
                inferred_missing_parent = current is None and name not in self.initial_data
                if name in attrs and attrs[name] != current and not inferred_missing_parent:
                    raise serializers.ValidationError({name: 'Moving or renaming this identifier requires a hierarchy migration.'})
        return attrs


class ContentAncestryMixin(StableHierarchyMixin):
    def validate(self, attrs):
        return validate_ancestry(super().validate(attrs), self.instance)
