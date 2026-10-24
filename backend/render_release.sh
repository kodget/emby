#!/usr/bin/env bash
# Run once for the web service, after a successful build and before deployment.
# Do not run from the worker or from the build script.
set -euo pipefail

python manage.py check_persistence_migrations --require-existing-database
python manage.py migrate --noinput
python manage.py migrate --check
python manage.py check_private_media

# Account creation and catalogue seeding are explicit maintenance operations.
# They must never overwrite live records as a side effect of deploying code.
