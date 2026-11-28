#!/usr/bin/env bash
set -euo pipefail
stamp() { date -u +%FT%TZ; }
for i in {1..90}; do
  if curl -fsS http://localhost:8080/health >/dev/null && curl -fsS http://localhost:9090/-/ready >/dev/null; then break; fi
  sleep 2
done
curl -fsS http://localhost:8080/health
incident_password=$(openssl rand -hex 24)
echo "::add-mask::$incident_password"
listing=$(docker compose exec -T -e INCIDENT_PASSWORD="$incident_password" api python manage.py shell -c "import os; from django.contrib.auth.models import User; from tutberry.models import ListingRecord; from uuid import uuid4; User.objects.create_user(username='incident',password=os.environ['INCIDENT_PASSWORD'],email='incident@example.test'); print(ListingRecord.objects.create(owner_id=uuid4(),title='Incident drill',daily_rate=500,deposit=100,status='active').id)" | tail -1)
docker compose stop worker
echo "outage_start $(stamp)"
curl -fsS 'http://localhost:8080/api/listings?start_date=2035-01-01&end_date=2035-01-02' >/dev/null
curl -fsS -u "incident:$incident_password" -H 'Content-Type: application/json' -d "{\"listing_id\":\"$listing\",\"start_date\":\"2035-01-01\",\"end_date\":\"2035-01-02\"}" http://localhost:8080/api/bookings
echo
alert_count() {
  curl -fsSG http://localhost:9090/api/v1/query --data-urlencode 'query=ALERTS{alertname="OutboxDelayed",alertstate="firing"}' | jq '.data.result | length'
}
for i in {1..80}; do
  if [[ $(alert_count) -gt 0 ]]; then break; fi
  sleep 5
done
[[ $(alert_count) -gt 0 ]]
echo "alert_detected $(stamp)"
docker compose start worker
echo "worker_restart $(stamp)"
for i in {1..60}; do
  if curl -fsS http://localhost:8080/metrics | grep -q '^outbox_pending 0.0$'; then break; fi
  sleep 3
done
curl -fsS http://localhost:8080/metrics | grep '^outbox_pending 0.0$'
echo "outbox_drained $(stamp)"
for i in {1..30}; do
  if [[ $(alert_count) -eq 0 ]]; then break; fi
  sleep 5
done
[[ $(alert_count) -eq 0 ]]
echo "alert_cleared $(stamp)"
