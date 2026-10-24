import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from curriculum.media_inventory import reconcile


class Command(BaseCommand):
    help = 'Read-only comparison of an explicit provider inventory export and Emby media references.'

    def add_arguments(self, parser):
        parser.add_argument('--inventory', required=True)
        parser.add_argument('--older-than-hours', type=int, default=24)

    def handle(self, *args, **options):
        try:
            document = json.loads(Path(options['inventory']).read_text(encoding='utf-8'))
            result = reconcile(document, older_than_hours=options['older_than_hours'])
        except (OSError, ValueError, TypeError) as exc:
            raise CommandError(f'Inventory could not be reconciled: {exc}') from None
        self.stdout.write(json.dumps(result, sort_keys=True, indent=2))
