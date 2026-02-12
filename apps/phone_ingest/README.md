# Phone Ingest (Meta OS)

## Purpose
Receive phone sensor events → normalize → append to Observer Hub → append to Audit Chain → run DRY_RUN interpretation.

## Run
./scripts/run_phone_ingest.sh

## Health Check
curl http://localhost:8787/health

## Test Event
curl -X POST http://localhost:8787/v1/ingest/phone-sensor ...

## Data Locations
Observer Hub: apps/phone_ingest/observer_hub_events.ndjson
Audit Chain: var/logs/audit.jsonl
