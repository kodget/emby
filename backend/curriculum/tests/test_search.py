from datetime import date
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate
from accounts.models import ClassGroup, School, Announcement, ExamCountdown
from curriculum.models import (Subject, Block, Topic, Slide, SlideContent, SlideSearchPage,
                               SlideDeck, SlidePage, Flashcard, QuizQuestion, Material)
from curriculum.search_views import search


class SearchTests(TestCase):
    def setUp(self):
        school = School.objects.create(name='Search school')
        self.group = ClassGroup.objects.create(school=school, set_name='One', code='112233')
        self.other = ClassGroup.objects.create(school=school, set_name='Two', code='445566')
        self.user = User.objects.create_user('search-student')
        self.user.profile.class_group = self.group
        self.user.profile.save()
        self.subject = Subject.objects.create(id='anatomy', name='Anatomy', class_group=self.group)
        self.foreign = Subject.objects.create(id='foreign', name='Private Anatomy', class_group=self.other)
        self.block = Block.objects.create(id='upper', subject=self.subject, name='Upper limb')
        self.topic = Topic.objects.create(id='nerves', block=self.block, name='Brachial plexus')
        self.slide = Slide.objects.create(id='lesson', title='Upper limb lecture', class_group=self.group,
            subject=self.subject, block=self.block, topic=self.topic, uploaded_by=self.user)
        self.content = SlideContent.objects.create(slide=self.slide, content_data={'pages': [
            {'page_number': 1, 'text': 'Overview of the upper limb'},
            {'page_number': 4, 'text': 'The brachial plexus supplies the upper limb.'}]})

    def get(self, q='brachial', user=None, **params):
        request = APIRequestFactory().get('/api/search/', {'q': q, **params})
        force_authenticate(request, user or self.user)
        return search(request)

    def test_finds_saved_page_once_with_excerpt_and_deep_link(self):
        response = self.get('BRACHIAL plexus', type='slide')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total'], 1)
        row = response.data['results'][0]
        self.assertEqual(row['page'], 4)
        self.assertEqual(row['url'], '/read/nerves/lesson?page=4')
        self.assertIn('brachial plexus', row['excerpt'])
        cache_control = response['Cache-Control']
        self.assertIn('private', cache_control)
        self.assertIn('no-store', cache_control)

    def test_all_words_must_match_but_can_span_title_and_page(self):
        self.assertEqual(self.get('lecture plexus', type='slide').data['total'], 1)
        self.assertEqual(self.get('plexus missing', type='slide').data['total'], 0)

    def test_class_isolation_in_results_counts_and_subjects(self):
        hidden = Slide.objects.create(id='hidden', title='Brachial secret', subject=self.foreign, class_group=self.other)
        SlideContent.objects.create(slide=hidden, content_data={'text': 'Brachial secret'})
        Announcement.objects.create(class_group=self.other, created_by=self.user, title='Brachial secret', content='Hidden')
        Slide.objects.create(id='unassigned', title='Brachial orphan')
        response = self.get()
        self.assertEqual(response.data['counts']['slide'], 1)
        self.assertEqual(response.data['counts']['announcement'], 0)
        self.assertEqual(response.data['subjects'], [{'id': 'anatomy', 'name': 'Anatomy'}])
        self.assertNotIn('secret', str(response.data))
        self.assertEqual(self.get(subject='foreign').data['total'], 0)

    def test_inconsistent_foreign_parent_is_excluded(self):
        Slide.objects.create(id='bad', title='Brachial corruption', subject=self.foreign, class_group=self.group)
        self.assertEqual(self.get(type='slide').data['total'], 1)

    def test_own_flashcards_only_and_back_is_searchable(self):
        other_user = User.objects.create_user('other-student')
        other_user.profile.class_group = self.group
        other_user.profile.save()
        own = Flashcard.objects.create(user=self.user, front='Name the network', back='Brachial plexus')
        Flashcard.objects.create(user=other_user, front='Brachial private card', back='Secret')
        result = self.get(type='flashcard').data
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['results'][0]['url'], f'/flashcards/manage?card={own.pk}')

    def test_no_class_or_inactive_class_sees_no_content(self):
        self.group.is_active = False
        self.group.save()
        self.assertEqual(self.get().data['total'], 0)
        self.assertEqual(self.get().data['subjects'], [])

    def test_newly_saved_and_deleted_text_updates_search(self):
        self.content.content_data = {'pages': [{'page_number': 8, 'content': 'New radial finding'}]}
        self.content.save(update_fields=['content_data'])
        self.assertEqual(self.get(type='slide').data['total'], 0)
        self.assertEqual(self.get('radial', type='slide').data['results'][0]['page'], 8)
        self.content.delete()
        self.assertFalse(SlideSearchPage.objects.filter(slide=self.slide).exists())
        self.assertEqual(self.get('radial', type='slide').data['total'], 0)

    def test_deck_search_no_duplicate_curriculum_slide(self):
        deck = SlideDeck.objects.create(id='deck', title='Upper limb', uploaded_by=self.user, class_group=self.group,
            file_type='pdf', original_file='file', curriculum_slide=self.slide)
        SlidePage.objects.create(deck=deck, slide_number=3, extracted_text='Brachial plexus', image='image')
        response = self.get()
        self.assertEqual(response.data['counts']['slide'], 0)
        self.assertEqual(response.data['counts']['deck'], 1)
        self.assertEqual(next(r for r in response.data['results'] if r['type'] == 'deck')['url'], '/decks/deck?page=3')

    def test_questions_exclude_review_and_answers_are_never_searched_or_returned(self):
        for id, review in [('published', False), ('draft', True)]:
            QuizQuestion.objects.create(id=id, subject=self.subject, question_type='mcq', source_type='manual',
                needs_review=review, question_text='Describe the brachial plexus', correct_option='A',
                option_a='Answerneedle', explanation='Secret explanation', ideal_answer='Private answer')
        result = self.get(type='question').data
        self.assertEqual(result['total'], 1)
        self.assertNotIn('Answerneedle', str(result))
        self.assertNotIn('Secret explanation', str(result))
        self.assertEqual(self.get('Answerneedle', type='question').data['total'], 0)

    def test_announcement_exam_and_resource(self):
        Announcement.objects.create(class_group=self.group, created_by=self.user, title='Room change', content='Brachial lecture')
        ExamCountdown.objects.create(class_group=self.group, created_by=self.user, title='Brachial exam', exam_date=date(2027, 1, 1))
        Material.objects.create(id='resource', subject=self.subject, block=self.block, title='Brachial notes', material_type='pdf', class_group=self.group)
        counts = self.get().data['counts']
        self.assertEqual([counts[key] for key in ('announcement', 'exam', 'material')], [1, 1, 1])

    def test_relevance_pagination_and_filters(self):
        for number in range(8):
            Slide.objects.create(id=f'match-{number}', title='Brachial' if number == 0 else f'Brachial notes {number}', class_group=self.group, subject=self.subject)
        first = self.get(type='slide', limit=3).data
        second = self.get(type='slide', limit=3, offset=3).data
        self.assertEqual(first['total'], 9)
        self.assertEqual(first['results'][0]['title'], 'Brachial')
        self.assertEqual(first['next_offset'], 3)
        self.assertFalse({r['id'] for r in first['results']} & {r['id'] for r in second['results']})
        self.assertEqual(self.get(type='slide', subject='anatomy').data['total'], 9)
        self.assertTrue(self.get(type='topic').data['counts']['slide'])

    def test_invalid_queries_and_anonymous_access(self):
        for params in ({'limit': 400}, {'offset': -1}, {'type': 'users'}, {'sort': 'unsafe'}, {'q': 'a' * 161}):
            self.assertEqual(self.get(**params).status_code, 400)
        for value in ('', 'a', '!!!', "' OR 1=1 --"):
            self.assertEqual(self.get(value).data['total'], 0)
        self.assertIn(search(APIRequestFactory().get('/api/search/', {'q': 'brachial'})).status_code, (401, 403))

    def test_search_does_not_dispatch_generation(self):
        with patch('backend.task_dispatch.dispatch_task') as dispatch:
            self.assertEqual(self.get().status_code, 200)
            dispatch.assert_not_called()

    def test_find_pages_and_offer_authorized_spelling_suggestions(self):
        data = self.get('privacy').data
        self.assertTrue(any(row['url'] == '/settings' for row in data['results']))
        self.assertEqual(self.get('brachal').data['suggestions'], ['brachial'])
        self.assertEqual(self.get('foriegn').data['suggestions'], [])
