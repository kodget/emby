#!/usr/bin/env bash
# Run every browser check against a live stack.
#
# Mints a fresh JWT each run — access tokens are short-lived, and a stale one sends the
# suites to /signin where every assertion fails for the wrong reason.
#
#   bash scripts/run_checks.sh [baseUrl]
set -u
BASE="${1:-http://127.0.0.1:3000}"
cd "$(dirname "$0")/.."

TOK=$(cd backend && USE_SQLITE=True PYTHONIOENCODING=utf-8 ./.venv/Scripts/python.exe -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','backend.settings')
django.setup()
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
print(RefreshToken.for_user(User.objects.get(username='demo')).access_token)" 2>/dev/null | tail -1)

# The practice suites spend a real round each run, and a free account only gets five a
# month — after that verify_practice meets the paywall and fails for a reason that has
# nothing to do with the code under test. Give the demo account a clean slate first.
(cd backend && USE_SQLITE=True PYTHONIOENCODING=utf-8 ./.venv/Scripts/python.exe -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','backend.settings')
django.setup()
from django.contrib.auth.models import User
from learning.models import PracticeRoundUsage
PracticeRoundUsage.objects.filter(user=User.objects.get(username='demo')).update(rounds_used=0)" >/dev/null 2>&1)

CODE=$(cd backend && USE_SQLITE=True PYTHONIOENCODING=utf-8 ./.venv/Scripts/python.exe -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','backend.settings')
django.setup()
from curriculum.models import BrainBattle
b = BrainBattle.objects.filter(status='scheduled').order_by('-created_at').first()
print(b.code if b else '')" 2>/dev/null | tail -1)

total_pass=0; total_fail=0; crashed=0
for s in verify_ui verify_practice verify_battles verify_planner; do
  out=$(EMBY_TOKEN="$TOK" BATTLE_CODE="$CODE" timeout 300 node "scripts/$s.mjs" "$BASE" 2>&1)
  line=$(echo "$out" | grep -E "^[0-9]+ passed" | tail -1)
  [ -z "$line" ] && line="CRASHED: $(echo "$out" | tail -2 | head -1)"
  printf "  %-18s %s\n" "$s" "$line"
  if [ "${line#CRASHED}" != "$line" ]; then
    # The runner died, so its assertions never ran. Count that as a failure rather than
    # letting an absent result read as a clean sheet.
    crashed=$((crashed + 1))
  else
    p=$(echo "$line" | grep -oE "^[0-9]+" || echo 0); f=$(echo "$line" | grep -oE "[0-9]+ failed" | grep -oE "^[0-9]+" || echo 0)
    total_pass=$((total_pass + p)); total_fail=$((total_fail + f))
  fi
done
echo
echo "  TOTAL: $total_pass passed, $total_fail failed, $crashed crashed"
[ "$total_fail" -eq 0 ] && [ "$crashed" -eq 0 ]
