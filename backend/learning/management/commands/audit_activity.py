import json

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from learning.activity_audit import report


class Command(BaseCommand):
    help = 'Read-only activity/cache audit for explicitly selected user IDs. Never repairs or re-awards history.'

    def add_arguments(self, parser):
        parser.add_argument('--user-id', type=int, action='append', required=True, dest='user_ids')

    def handle(self, *args, **options):
        ids = set(options['user_ids'])
        users = list(User.objects.filter(pk__in=ids).order_by('pk'))
        if len(users) != len(ids):
            raise CommandError('One or more selected user IDs do not exist; no audit was run.')
        self.stdout.write(json.dumps({'dry_run': True, 'reports': [report(user) for user in users]}, indent=2))
