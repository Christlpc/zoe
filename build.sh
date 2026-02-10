#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python3 manage.py collectstatic --no-input
# On lance les migrations pour créer les tables de la base PostgreSQL Render
python3 manage.py migrate
