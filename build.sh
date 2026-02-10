#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
# On ne lance pas de migrations ici car on utilise la base NSIA distante gérée par l'autre projet
# python manage.py migrate
