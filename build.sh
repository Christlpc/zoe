#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
# On lance les migrations pour créer les tables de sessions et messages
python manage.py migrate
