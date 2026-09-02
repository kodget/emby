from django.core.management.base import BaseCommand
from learning.gamification import seed_achievements

class Command(BaseCommand):
    help = 'Seeds the gamification database with achievements and badges.'

    def handle(self, *args, **kwargs):
        seed_achievements()
        self.stdout.write(self.style.SUCCESS('Successfully seeded achievements.'))
