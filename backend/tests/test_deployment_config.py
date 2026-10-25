import unittest
from django.core.exceptions import ImproperlyConfigured
from backend.deployment_config import validate_deployment


class DeploymentConfigTests(unittest.TestCase):
    def test_render_fails_closed_without_revealing_credentials(self):
        env = {'RENDER': 'true', 'DEBUG': 'true', 'SECRET_KEY': 'dont-print-me',
               'CELERY_TASK_ALWAYS_EAGER': 'true'}
        with self.assertRaises(ImproperlyConfigured) as error:
            validate_deployment(env)
        self.assertNotIn('dont-print-me', str(error.exception))
        for name in ('DEBUG', 'SECRET_KEY', 'REDIS_URL', 'CELERY_TASK_ALWAYS_EAGER'):
            self.assertIn(name, str(error.exception))

    def test_valid_configuration_and_local_development(self):
        validate_deployment({'RENDER': 'true', 'DEBUG': 'False',
                             'SECRET_KEY': 'a' * 50, 'REDIS_URL': 'redis://example.test'})
        validate_deployment({'DEBUG': 'true'})
