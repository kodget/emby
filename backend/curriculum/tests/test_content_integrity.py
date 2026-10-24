from io import BytesIO
from unittest.mock import patch
from zipfile import ZipFile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import ClassGroup, ClassRole, PlatformRole, School
from curriculum.models import Subject, Block, SubBlock, Topic, Slide, Material
from curriculum.serializers import BlockSerializer, SubBlockSerializer, TopicSerializer, SlideSerializer, MaterialSerializer
from curriculum.slide_uploads import validate_slide_file
from curriculum.views import SlideViewSet, MaterialViewSet


class ContentIntegrityTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name='Test school')
        self.group = ClassGroup.objects.create(school=self.school, set_name='Year 1', code='100001')
        self.other_group = ClassGroup.objects.create(school=self.school, set_name='Year 2', code='100002')
        self.subject = Subject.objects.create(id='anatomy', name='Anatomy', class_group=self.group)
        self.other_subject = Subject.objects.create(id='physiology', name='Physiology', class_group=self.other_group)
        self.block = Block.objects.create(id='upper', name='Upper limb', subject=self.subject)
        self.other_block = Block.objects.create(id='heart', name='Heart', subject=self.other_subject)
        self.sub = SubBlock.objects.create(id='hand', name='Hand', block=self.block)
        self.other_sub = SubBlock.objects.create(id='rhythm', name='Rhythm', block=self.other_block)
        self.topic = Topic.objects.create(id='bones', name='Bones', sub_block=self.sub, block=self.block)
        self.uploader = self.user('uploader', ClassRole.MATERIAL_UPLOADER)
        self.student = self.user('student', ClassRole.STUDENT)
        self.pending = self.user('pending', ClassRole.CLASS_HEAD)
        self.factory = APIRequestFactory()

    def user(self, name, role):
        user = User.objects.create_user(name)
        profile = user.profile
        profile.class_role = role
        profile.class_group = self.group
        profile.save()
        return user

    def call(self, action, data=None, *, user=None, pk=None, method='post', view=SlideViewSet, multipart=False):
        request = getattr(self.factory, method)('/content/', data or {}, format='multipart' if multipart else 'json')
        force_authenticate(request, user=user or self.uploader)
        return view.as_view({method: action})(request, **({'pk': pk} if pk else {}))

    def slide(self, **kwargs):
        return Slide.objects.create(id='existing', title='Original', subject=self.subject, block=self.block,
                                    sub_block=self.sub, topic=self.topic, uploaded_by=self.uploader,
                                    class_group=self.group, **kwargs)

    def upload_data(self, **kwargs):
        return {'file': SimpleUploadedFile('lecture.pdf', b'%PDF-1.7\noriginal'),
                'title': 'Lecture', 'topic': self.topic.pk, **kwargs}

    def test_child_only_input_fills_its_real_ancestors(self):
        serializer = SlideSerializer(data={'title': 'Bones', 'topic': self.topic.pk})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['subject'], self.subject)
        self.assertEqual(serializer.validated_data['block'], self.block)
        self.assertEqual(serializer.validated_data['sub_block'], self.sub)

    def test_cross_branch_ids_and_explicit_null_parent_are_rejected(self):
        for field, value in [('subject', self.other_subject.pk), ('block', self.other_block.pk),
                             ('sub_block', self.other_sub.pk), ('sub_block', None)]:
            with self.subTest(field=field, value=value):
                serializer = SlideSerializer(data={'title': 'Bones', 'topic': self.topic.pk, field: value})
                self.assertFalse(serializer.is_valid())
                self.assertIn(field, serializer.errors)

    def test_partial_update_checks_existing_ancestors(self):
        slide = self.slide()
        serializer = SlideSerializer(slide, data={'block': self.other_block.pk}, partial=True)
        self.assertFalse(serializer.is_valid())
        slide.refresh_from_db()
        self.assertEqual(slide.block, self.block)

    def test_topic_requires_a_parent_and_rejects_conflicting_legacy_alias(self):
        for data in ({'name': 'Orphan'}, {'name': 'Conflict', 'sub_block': self.sub.pk, 'topic': self.other_sub.pk},
                     {'name': 'Mismatch', 'sub_block': self.sub.pk, 'block': self.other_block.pk}):
            self.assertFalse(TopicSerializer(data=data).is_valid())

    def test_topic_infers_block_and_preserves_legacy_direct_block_creation(self):
        for data in ({'name': 'Child', 'sub_block': self.sub.pk}, {'name': 'Legacy child', 'block': self.block.pk}):
            serializer = TopicSerializer(data=data)
            self.assertTrue(serializer.is_valid(), serializer.errors)
            self.assertEqual(serializer.save().block, self.block)

    def test_legacy_topic_rename_can_fill_its_missing_redundant_module(self):
        self.topic.block = None
        self.topic.save()
        serializer = TopicSerializer(self.topic, data={'name': 'Renamed bones'}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.save().block, self.block)

    def test_nested_module_topics_exclude_submodule_topics(self):
        Topic.objects.create(id='direct', name='Direct', block=self.block)
        data = BlockSerializer(self.block).data
        self.assertEqual([topic['id'] for topic in data['topics']], ['direct'])
        self.assertEqual(data['sub_blocks'][0]['topics'][0]['id'], self.topic.pk)

    def test_reparenting_or_changing_primary_key_does_not_break_descendants(self):
        for serializer_class, instance, data in (
            (BlockSerializer, self.block, {'subject': self.other_subject.pk}),
            (SubBlockSerializer, self.sub, {'block': self.other_block.pk}),
            (TopicSerializer, self.topic, {'sub_block': self.other_sub.pk, 'block': self.other_block.pk}),
            (SlideSerializer, self.slide(), {'id': 'replacement'}),
        ):
            with self.subTest(serializer=serializer_class.__name__):
                serializer = serializer_class(instance, data=data, partial=True)
                self.assertFalse(serializer.is_valid())

    def test_material_ancestry_uses_the_same_checks(self):
        serializer = MaterialSerializer(data={'title': 'Wrong', 'subject': self.subject.pk,
                                             'block': self.other_block.pk})
        self.assertFalse(serializer.is_valid())

    def test_client_cannot_forge_uploader_or_processing_state(self):
        response = self.call('create', {'title': 'Uploaded', 'topic': self.topic.pk,
                                      'uploaded_by': self.student.pk, 'page_count': 999,
                                      'generation_status': 'completed'})
        self.assertEqual(response.status_code, 201, response.data)
        slide = Slide.objects.get(pk=response.data['id'])
        self.assertEqual(slide.uploaded_by, self.uploader)
        self.assertEqual(slide.page_count, 0)
        self.assertEqual(slide.generation_status, 'pending')

    def test_students_and_pending_heads_cannot_write_either_content_type(self):
        for user in (self.student, self.pending):
            for view in (SlideViewSet, MaterialViewSet):
                response = self.call('create', {'title': 'Forbidden'}, user=user, view=view)
                self.assertEqual(response.status_code, 403)
            response = self.call('upload_and_process', self.upload_data(), user=user, multipart=True)
            self.assertEqual(response.status_code, 403)

    def test_student_cannot_update_or_delete_existing_slide(self):
        slide = self.slide()
        for action, method in [('partial_update', 'patch'), ('destroy', 'delete')]:
            response = self.call(action, {'title': 'Tampered'}, user=self.student, pk=slide.pk, method=method)
            self.assertEqual(response.status_code, 403)
        slide.refresh_from_db()
        self.assertEqual(slide.title, 'Original')

    def test_another_uploader_cannot_modify_content_even_in_same_class(self):
        slide = self.slide()
        other = self.user('other-uploader', ClassRole.MATERIAL_UPLOADER)
        response = self.call('partial_update', {'title': 'Tampered'}, user=other, pk=slide.pk, method='patch')
        self.assertEqual(response.status_code, 403)
        material = Material.objects.create(class_group=self.group, id='material', title='Source', subject=self.subject,
                                           block=self.block, uploaded_by=self.uploader)
        response = self.call('destroy', user=other, pk=material.pk, method='delete', view=MaterialViewSet)
        self.assertEqual(response.status_code, 403)

    def test_owner_and_platform_admin_can_edit(self):
        slide = self.slide()
        response = self.call('partial_update', {'title': 'Renamed'}, pk=slide.pk, method='patch')
        self.assertEqual(response.status_code, 200, response.data)
        self.student.profile.platform_role = PlatformRole.ADMIN
        self.student.profile.save()
        response = self.call('partial_update', {'title': 'Reviewed'}, user=self.student, pk=slide.pk, method='patch')
        self.assertEqual(response.status_code, 200, response.data)

    def test_inactive_class_or_classless_uploader_cannot_upload(self):
        self.group.is_active = False
        self.group.save()
        self.uploader.profile.refresh_from_db()
        self.assertEqual(self.call('create', {'title': 'Blocked'}).status_code, 403)
        self.uploader.profile.class_group = None
        self.uploader.profile.save()
        self.assertEqual(self.call('create', {'title': 'Blocked'}).status_code, 403)

    def test_submodule_filter_does_not_return_sibling_content(self):
        self.slide()
        sibling = SubBlock.objects.create(id='arm', name='Arm', block=self.block)
        Slide.objects.create(class_group=self.group, id='sibling', title='Sibling', block=self.block, subject=self.subject, sub_block=sibling)
        response = self.call('list', {'sub_block': self.sub.pk}, method='get', user=self.student)
        self.assertEqual([row['id'] for row in response.data], ['existing'])

    @patch('cloudinary.uploader.upload')
    def test_invalid_hierarchy_never_reaches_storage(self, upload):
        response = self.call('upload_and_process', self.upload_data(block=self.other_block.pk), multipart=True)
        self.assertEqual(response.status_code, 404, response.data)
        upload.assert_not_called()
        self.assertFalse(Slide.objects.exists())

    @patch('cloudinary.uploader.upload')
    def test_bad_empty_and_oversized_uploads_never_reach_storage(self, upload):
        cases = [('renamed.pdf', b'MZprogram', 400), ('empty.pdf', b'', 400), ('image.png', b'png', 400)]
        for filename, content, expected in cases:
            response = self.call('upload_and_process', self.upload_data(file=SimpleUploadedFile(filename, content)), multipart=True)
            self.assertEqual(response.status_code, expected)
        with patch('curriculum.slide_uploads.MAX_SLIDE_BYTES', 4):
            response = self.call('upload_and_process', self.upload_data(), multipart=True)
            self.assertEqual(response.status_code, 413)
        upload.assert_not_called()

    def test_office_archive_type_is_checked_and_stream_rewound(self):
        archive = BytesIO()
        with ZipFile(archive, 'w') as zipped:
            zipped.writestr('[Content_Types].xml', '<Types/>')
            zipped.writestr('word/document.xml', '<document/>')
        file = SimpleUploadedFile('notes.docx', archive.getvalue())
        self.assertEqual(validate_slide_file(file), 'docx')
        self.assertEqual(file.tell(), 0)
        file.name = 'notes.pptx'
        from rest_framework.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_slide_file(file)
        self.assertEqual(file.tell(), 0)

    @patch('cloudinary.uploader.upload', side_effect=RuntimeError('private-provider-details'))
    def test_storage_outage_returns_safe_error_without_partial_record(self, upload):
        response = self.call('upload_and_process', self.upload_data(), multipart=True)
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('private-provider-details', str(response.data))
        self.assertFalse(Slide.objects.exists())

    def storage_result(self):
        return {'secure_url': 'https://res.cloudinary.com/test/image/upload/v1/lecture.pdf',
                'public_id': 'lecture', 'resource_type': 'image', 'type': 'authenticated', 'format': 'pdf', 'version': 1}

    @patch('curriculum.slide_uploads.dispatch_slide_processing')
    @patch('cloudinary.uploader.upload')
    def test_valid_original_is_saved_and_dispatched_only_after_commit(self, upload, dispatch):
        upload.return_value = self.storage_result()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.call('upload_and_process', self.upload_data(), multipart=True)
            self.assertEqual(response.status_code, 201, response.data)
            dispatch.assert_not_called()
        slide = Slide.objects.get(pk=response.data['id'])
        dispatch.assert_called_once_with(slide.pk)
        self.assertEqual(slide.asset.resource_type, 'image')
        self.assertEqual(slide.subject, self.subject)
        self.assertEqual(slide.file_url, '')
        self.assertEqual(slide.asset.delivery_type, 'authenticated')
        self.assertIn('expires_at=', response.data['file_url'])
        self.assertEqual(slide.processing_status.status, 'pending')

    @patch('curriculum.tasks.process_slide_task.delay', side_effect=RuntimeError('broker-secret'))
    @patch('cloudinary.uploader.destroy')
    @patch('cloudinary.uploader.upload')
    def test_queue_failure_keeps_original_and_records_recoverable_processing_error(self, upload, destroy, delay):
        upload.return_value = self.storage_result()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.call('upload_and_process', self.upload_data(), multipart=True)
        self.assertEqual(response.status_code, 201)
        slide = Slide.objects.get(pk=response.data['id'])
        self.assertTrue(slide.asset_id)
        self.assertEqual(slide.processing_status.status, 'failed')
        self.assertNotIn('broker-secret', slide.processing_status.error_message)
        destroy.assert_not_called()

    @patch('curriculum.models.SlideProcessingStatus.objects.create', side_effect=RuntimeError('db-detail'))
    @patch('cloudinary.uploader.destroy')
    @patch('cloudinary.uploader.upload')
    def test_database_failure_rolls_back_metadata_and_cleans_only_new_asset(self, upload, destroy, create):
        upload.return_value = self.storage_result()
        destroy.return_value = {'result': 'ok'}
        response = self.call('upload_and_process', self.upload_data(), multipart=True)
        self.assertEqual(response.status_code, 503)
        self.assertFalse(Slide.objects.exists())
        from curriculum.models import MediaAsset
        self.assertFalse(MediaAsset.objects.exists())
        destroy.assert_called_once_with('lecture', resource_type='image', type='authenticated', invalidate=True)
