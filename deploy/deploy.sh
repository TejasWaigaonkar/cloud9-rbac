#!/bin/sh
set -eu
cd /opt/cloud9
. ./host.env
export APP_IMAGE="$1"
docker compose -f compose.prod.yml pull
docker compose -f compose.prod.yml run --rm web python manage.py check --deploy --fail-level WARNING
docker compose -f compose.prod.yml run --rm web python manage.py migrate --noinput
docker compose -f compose.prod.yml up -d --wait --wait-timeout 120
curl --fail --retry 5 --retry-delay 3 -H "Host: $APP_HOST" http://127.0.0.1:8000/ready/
printf '%s\n' "$APP_IMAGE" > deployed-image.txt
