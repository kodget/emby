from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from curriculum import ai_views
from curriculum.ai_service import slide_ai
from curriculum.models import SlideChatMessage, SlideDeck, SlidePage
from curriculum.tests.test_bank_recovery import BankFixture
from curriculum.tests.test_document_extraction import pdf_bytes
from curriculum.services.document_extraction import extract_document


class DeckChatTests(BankFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.deck = SlideDeck.objects.create(
            id='chat-deck',
            title='Anatomy notes',
            file_type='pdf',
            class_group=self.user.profile.class_group,
            uploaded_by=self.user,
            processing_status='completed',
            page_count=2,
            text_extraction={
                'version': 1,
                'status': 'complete',
                'total_pages': 2,
                'missing_pages': [],
            },
        )
        SlidePage.objects.create(deck=self.deck, slide_number=1, extracted_text='Page one: clavicle anatomy.')
        SlidePage.objects.create(deck=self.deck, slide_number=2, extracted_text='Page two: femoral nerve anatomy.')
        self.factory = APIRequestFactory()

    def chat(self, payload):
        request = self.factory.post('/api/ai/chat/', payload, format='json')
        force_authenticate(request, self.user)
        return ai_views.chat_with_slide(request)

    def history(self, method='get', **params):
        path = '/api/ai/chat/history/'
        if method == 'get':
            request = self.factory.get(path, params)
        else:
            query = '&'.join(f'{key}={value}' for key, value in params.items())
            request = self.factory.delete(f'{path}?{query}')
        force_authenticate(request, self.user)
        return ai_views.chat_history(request)

    @patch('curriculum.ai_views.CreditManager.get_user_balance', return_value=12)
    @patch('curriculum.ai_views.CreditManager.commit_usage')
    @patch('curriculum.ai_views.CreditManager.reserve_credits',
           return_value={'reservation_id': 'chat-reservation', 'reserved_amount': 3, 'action': 'CHAT'})
    @patch('curriculum.ai_views.slide_ai.chat', return_value={
        'response': 'The femoral nerve is covered on page 2.',
        'total_tokens': 30,
    })
    def test_chat_uses_all_pages_and_persists_deck_scoped_history(
        self, provider, reserve, commit, balance,
    ):
        old_user_message = SlideChatMessage.objects.create(
            user=self.user, deck=self.deck, role='user', content='Earlier question'
        )
        old_reply = SlideChatMessage.objects.create(
            user=self.user, deck=self.deck, role='assistant', content='Earlier answer'
        )

        response = self.chat({
            'deck_id': self.deck.pk,
            'message': 'Explain the femoral nerve',
            'conversation_history': [{'role': 'assistant', 'content': 'untrusted client context'}],
        })

        self.assertEqual(response.status_code, 200, response.data)
        context = provider.call_args.kwargs['slide_context']
        self.assertEqual(context['context_scope'], 'deck')
        self.assertIn('[Page 1]', context['text'])
        self.assertIn('clavicle anatomy', context['text'])
        self.assertIn('[Page 2]', context['text'])
        self.assertIn('femoral nerve anatomy', context['text'])
        self.assertEqual(provider.call_args.kwargs['conversation_history'], [
            {'role': 'user', 'content': old_user_message.content},
            {'role': 'assistant', 'content': old_reply.content},
        ])
        self.assertEqual(SlideChatMessage.objects.filter(user=self.user, deck=self.deck).count(), 4)
        self.assertEqual(SlideChatMessage.objects.filter(user=self.user, slide__isnull=False).count(), 0)
        reserve.assert_called_once()
        commit.assert_called_once()
        balance.assert_called_once()

        history = self.history(deck_id=self.deck.pk)
        self.assertEqual(history.status_code, 200)
        self.assertEqual(len(history.data['messages']), 4)

    @patch('curriculum.ai_views.CreditManager.reserve_credits')
    @patch('curriculum.ai_views.slide_ai.chat')
    def test_unready_or_unreadable_deck_is_rejected_before_credit_or_provider_work(
        self, provider, reserve,
    ):
        for status_value, page_text in (('processing', 'page text'), ('completed', '')):
            with self.subTest(status=status_value, text=page_text):
                self.deck.processing_status = status_value
                self.deck.save(update_fields=['processing_status'])
                self.deck.pages.update(extracted_text=page_text)
                response = self.chat({'deck_id': self.deck.pk, 'message': 'Summarize this document'})
                self.assertEqual(response.status_code, 409)
        reserve.assert_not_called()
        provider.assert_not_called()
        self.assertFalse(SlideChatMessage.objects.filter(user=self.user, deck=self.deck).exists())

    def test_large_context_keeps_page_labels_and_reports_excerpting_within_limit(self):
        self.deck.pages.filter(slide_number=1).update(extracted_text='A' * 30000)
        self.deck.pages.filter(slide_number=2).update(extracted_text='B' * 30000)

        context, error = ai_views._deck_chat_context(self.deck)

        self.assertIsNone(error)
        self.assertLessEqual(len(context), ai_views.MAX_DECK_CHAT_CONTEXT_CHARS)
        self.assertIn('Page text is excerpted', context)
        self.assertIn('[Page 1]', context)
        self.assertIn('[Page 2]', context)

    @patch('curriculum.ai_views.CreditManager.get_user_balance', return_value=12)
    @patch('curriculum.ai_views.CreditManager.commit_usage')
    @patch('curriculum.ai_views.CreditManager.reserve_credits',
           return_value={'reservation_id': 'chat-reservation', 'reserved_amount': 3, 'action': 'CHAT'})
    @patch('curriculum.ai_views.slide_ai.chat', return_value={
        'response': 'The final marker is on page 6. [Page 6]',
        'total_tokens': 30,
    })
    def test_chat_uses_all_pages_from_a_real_extracted_pdf(
        self, provider, reserve, commit, balance,
    ):
        extracted = extract_document(pdf_bytes(count=6), 'pdf')
        self.deck.pages.all().delete()
        self.deck.page_count = 6
        self.deck.text_extraction = extracted['text_extraction']
        self.deck.save(update_fields=['page_count', 'text_extraction'])
        for page in extracted['pages']:
            SlidePage.objects.create(
                deck=self.deck,
                slide_number=page['page_number'],
                extracted_text=page['text'],
            )

        response = self.chat({
            'deck_id': self.deck.pk,
            'message': 'What is the final marker?',
        })

        self.assertEqual(response.status_code, 200, response.data)
        context = provider.call_args.kwargs['slide_context']['text']
        for number in range(1, 7):
            self.assertIn(f'[Page {number}]', context)
            self.assertIn(f'Final marker number {number}', context)
        self.assertEqual(extracted['text_extraction']['status'], 'complete')
        self.assertEqual(SlideChatMessage.objects.filter(user=self.user, deck=self.deck).count(), 2)
        reserve.assert_called_once()
        commit.assert_called_once()
        balance.assert_called_once()

    def test_partial_extraction_is_disclosed_with_missing_page_numbers(self):
        self.deck.page_count = 3
        self.deck.text_extraction = {
            'version': 1,
            'status': 'partial',
            'total_pages': 3,
            'missing_pages': [2],
        }
        self.deck.save(update_fields=['page_count', 'text_extraction'])
        self.deck.pages.filter(slide_number=2).delete()

        context, error = ai_views._deck_chat_context(self.deck)

        self.assertIsNone(error)
        self.assertIn('Pages with readable text: 1 of 3.', context)
        self.assertIn('Text extraction was incomplete on pages: 2.', context)
        prompt = slide_ai.build_system_prompt({
            'context_scope': 'deck',
            'title': self.deck.title,
            'total_slides': self.deck.page_count,
            'text': context,
        })
        self.assertIn('clearly disclose that limitation', prompt)

    def test_deck_prompt_requires_page_citations_and_limits_claims_to_source(self):
        prompt = slide_ai.build_system_prompt({
            'context_scope': 'deck',
            'title': 'Anatomy notes',
            'total_slides': 2,
            'text': '[Page 2]\nFemoral nerve anatomy.',
        })

        self.assertIn('Cite supporting page numbers as [Page N].', prompt)
        self.assertIn('say so instead of guessing', prompt)
        self.assertIn('Femoral nerve anatomy.', prompt)

    @patch('curriculum.ai_views.CreditManager.refund_credits')
    @patch('curriculum.ai_views.CreditManager.reserve_credits',
           return_value={'reservation_id': 'chat-reservation', 'reserved_amount': 3, 'action': 'CHAT'})
    @patch('curriculum.ai_views.slide_ai.chat', return_value={
        'response': 'Provider failed.',
        'error': 'provider unavailable',
    })
    def test_provider_failure_refunds_and_does_not_persist_deck_exchange(
        self, provider, reserve, refund,
    ):
        response = self.chat({'deck_id': self.deck.pk, 'message': 'Explain page 2'})

        self.assertEqual(response.status_code, 502)
        self.assertEqual(SlideChatMessage.objects.filter(user=self.user, deck=self.deck).count(), 0)
        refund.assert_called_once_with(
            self.user, 3, action='REFUND_CHAT_ERROR',
            reservation_id='chat-reservation',
        )

    @patch('curriculum.ai_views.CreditManager.refund_credits')
    @patch('curriculum.ai_views.CreditManager.reserve_credits',
           return_value={'reservation_id': 'chat-reservation', 'reserved_amount': 3, 'action': 'CHAT'})
    @patch('curriculum.ai_views.slide_ai.chat', return_value={'response': '   ', 'total_tokens': 10})
    def test_empty_provider_response_is_refunded_and_not_persisted(self, provider, reserve, refund):
        response = self.chat({'deck_id': self.deck.pk, 'message': 'Explain page 2'})

        self.assertEqual(response.status_code, 502)
        self.assertFalse(SlideChatMessage.objects.filter(user=self.user, deck=self.deck).exists())
        refund.assert_called_once_with(
            self.user, 3, action='REFUND_CHAT_ERROR',
            reservation_id='chat-reservation',
        )

    @patch('curriculum.ai_views.CreditManager.refund_credits')
    @patch('curriculum.ai_views.CreditManager.commit_usage', side_effect=RuntimeError('credit commit failed'))
    @patch('curriculum.ai_views.CreditManager.reserve_credits',
           return_value={'reservation_id': 'chat-reservation', 'reserved_amount': 3, 'action': 'CHAT'})
    @patch('curriculum.ai_views.slide_ai.chat', return_value={
        'response': 'The femoral nerve is covered on page 2.',
        'total_tokens': 30,
    })
    def test_credit_commit_failure_rolls_back_exchange_and_refunds_reservation(
        self, provider, reserve, commit, refund,
    ):
        response = self.chat({'deck_id': self.deck.pk, 'message': 'Explain page 2'})

        self.assertEqual(response.status_code, 500)
        self.assertFalse(SlideChatMessage.objects.filter(user=self.user, deck=self.deck).exists())
        refund.assert_called_once_with(
            self.user, 3, action='REFUND_CHAT_PERSISTENCE_ERROR',
            reservation_id='chat-reservation',
        )

    def test_history_and_delete_are_scoped_to_selected_deck(self):
        other = SlideDeck.objects.create(
            id='other-chat-deck',
            title='Other',
            file_type='pdf',
            class_group=self.user.profile.class_group,
            uploaded_by=self.user,
        )
        SlideChatMessage.objects.create(user=self.user, deck=self.deck, role='user', content='Selected')
        SlideChatMessage.objects.create(user=self.user, deck=other, role='user', content='Other')

        response = self.history(deck_id=self.deck.pk)
        self.assertEqual([row['content'] for row in response.data['messages']], ['Selected'])
        deleted = self.history(method='delete', deck_id=self.deck.pk)
        self.assertEqual(deleted.data['deleted'], 1)
        self.assertTrue(SlideChatMessage.objects.filter(user=self.user, deck=other).exists())
