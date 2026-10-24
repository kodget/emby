import json

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from rest_framework.exceptions import ValidationError

from learning.activity_reconciliation import plan, apply


class Command(BaseCommand):
    help = 'Preview a selected account time/streak cache repair; applying requires its reviewed fingerprint.'

    def add_arguments(self, parser):
        parser.add_argument('--user-id', type=int, required=True)
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--expected-fingerprint')

    def handle(self, *args, **options):
        try:
            user = User.objects.get(pk=options['user_id'])
        except User.DoesNotExist as exc:
            raise CommandError('The selected account does not exist; nothing was changed.') from exc
        if not options['apply'] and options['expected_fingerprint']:
            raise CommandError('A fingerprint is used only with --apply.')
        try:
            result = apply(user, options['expected_fingerprint']) if options['apply'] else plan(user)
        except ValidationError as exc:
            raise CommandError(str(exc.detail)) from exc
        self.stdout.write(json.dumps(result, indent=2))
