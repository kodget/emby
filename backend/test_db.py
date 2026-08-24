import os
import django
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import BrainBattle
from accounts.models import User, ClassGroup

u = User.objects.filter(class_group__isnull=False).first()
if not u:
    print("No user with class group found")
else:
    print(f"Testing with user: {u.email}, ClassGroup: {u.class_group}")
    try:
        b = BrainBattle.objects.create(title="Test Battle", host=u, class_group=u.class_group)
        print("Success:", b.id)
    except Exception as e:
        print("Error during creation:")
        traceback.print_exc()
