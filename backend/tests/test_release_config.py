"""Exercise release ordering/failure behavior using a fake Python command."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
GIT_BASH = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe"
BASH = str(GIT_BASH) if GIT_BASH.is_file() else shutil.which("bash")


class ReleaseConfigurationTests(unittest.TestCase):
    def test_only_web_owns_release_and_services_disable_sqlite(self):
        blueprint = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
        services = [service for service in blueprint["services"] if service["type"] in ("web", "worker")]
        owners = [service for service in services if "preDeployCommand" in service]
        self.assertEqual(len(owners), 1)
        self.assertEqual(owners[0]["type"], "web")
        self.assertEqual(owners[0]["preDeployCommand"], "bash render_release.sh")
        for service in services:
            environment = {item["key"]: item.get("value") for item in service["envVars"] if "key" in item}
            self.assertEqual(environment["DEBUG"], "False")
            self.assertEqual(environment["USE_SQLITE"], "False")
            self.assertEqual(environment["CELERY_TASK_ALWAYS_EAGER"], "False")
            self.assertEqual(service['runtime'], 'docker')
            self.assertIn({'fromGroup': 'emby-production'}, service['envVars'])
        self.assertEqual([s['dockerCommand'] for s in services], [
            'bash render_start.sh web', 'bash render_start.sh worker', 'bash render_start.sh scheduler'])

    @unittest.skipUnless(BASH, "Bash is required to exercise deployment shell behavior")
    def test_release_stops_before_migrating_when_preflight_fails(self):
        code, commands = self.run_script("render_release.sh", fail_on="check_persistence_migrations")
        self.assertNotEqual(code, 0)
        self.assertEqual(commands, ["manage.py check_persistence_migrations --require-existing-database"])

    @unittest.skipUnless(BASH, "Bash is required to exercise deployment shell behavior")
    def test_release_stops_on_migration_failure(self):
        code, commands = self.run_script("render_release.sh", fail_on="migrate")
        self.assertNotEqual(code, 0)
        self.assertEqual(commands[-1], "manage.py migrate --noinput")
        self.assertEqual(len(commands), 2)

    @unittest.skipUnless(BASH, "Bash is required to exercise deployment shell behavior")
    def test_release_fails_when_private_media_adoption_is_incomplete(self):
        code, commands = self.run_script('render_release.sh', fail_on='check_private_media')
        self.assertNotEqual(code, 0)
        self.assertEqual(commands[-1], 'manage.py check_private_media')

    @unittest.skipUnless(BASH, "Bash is required to exercise deployment shell behavior")
    def test_release_checks_then_migrates_without_seeding(self):
        code, commands = self.run_script("render_release.sh")
        self.assertEqual(code, 0)
        self.assertEqual(commands, [
            "manage.py check_persistence_migrations --require-existing-database",
            "manage.py migrate --noinput", "manage.py migrate --check", "manage.py check_private_media",
        ])

    @unittest.skipUnless(BASH, "Bash is required to exercise deployment shell behavior")
    def test_build_has_no_database_mutations(self):
        code, commands = self.run_script("render_build.sh")
        self.assertEqual(code, 0)
        self.assertEqual(commands, ["manage.py collectstatic --noinput"])

    def run_script(self, filename, fail_on=""):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "commands.txt"
            environment = os.environ.copy()
            environment.update({
                "RELEASE_TEST_LOG": output.as_posix(), "RELEASE_TEST_FAIL_ON": fail_on,
                "RELEASE_TEST_SCRIPT": (ROOT / "backend" / filename).as_posix(),
            })
            # All subprocess entry points are shell functions. No package install,
            # Django command, credentials, database or provider is touched.
            harness = r'''
python() {
    printf '%s\n' "$*" >> "$RELEASE_TEST_LOG"
    if [ -n "$RELEASE_TEST_FAIL_ON" ] && [ "$2" = "$RELEASE_TEST_FAIL_ON" ]; then
        return 19
    fi
}
apt-get() { return 0; }
pip() { return 0; }
soffice() { printf 'test converter\n'; }
export -f python apt-get pip soffice
bash "$RELEASE_TEST_SCRIPT"
'''
            result = subprocess.run([BASH, "-c", harness], env=environment,
                                    capture_output=True, text=True, timeout=30)
            self.assertTrue(output.exists(), result.stderr)
            return result.returncode, output.read_text(encoding="utf-8").splitlines()
