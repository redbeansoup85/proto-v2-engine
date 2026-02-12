from fastapi import FastAPI, HTTPException
from pathlib import Path
import json

from apps.phone_ingest.schemas import PhoneSensorIn, normalize_phone_sensor

app = FastAPI(title="Meta OS Phone Ingest", version="0.1.0")

BASE_DIR = Path(__file__).resolve().parent
HUB_EVENTS = BASE_DIR / "observer_hub_events.ndjson"


def append_event_to_audit_chain(evt: dict) -> dict:
    from auralis_v1.core.audit_chain import append_audit

    payload_text = json.dumps(evt, ensure_ascii=False, sort_keys=True)
    gate = {
        "source": "apps.phone_ingest",
        "schema": evt.get("schema"),
        "kind": evt.get("kind"),
        "device_id": evt.get("source", {}).get("device_id"),
    }

    rec = append_audit({"kind": "SENSOR_EVENT", "text": payload_text, "gate": gate})
    if isinstance(rec, dict):
        return rec
    return {"result": str(rec)}


def ingest_to_observer_hub(evt: dict) -> None:
    with HUB_EVENTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(evt, ensure_ascii=False) + "\n")


def run_interpreter_dry_run(evt: dict) -> dict:
    sensor = evt["payload"]["sensor"]
    value = float(evt["payload"]["value"])
    reasons = []
    decision = "neutral"

    if sensor == "sound_level" and value >= 70:
        decision = "alert_candidate"
        reasons.append("sound_level>=70dB")
    if sensor == "motion_flag" and value >= 1:
        decision = "motion_detected"
        reasons.append("motion_flag=1")

    return {
        "schema": "auralis_intent.dry_run.v1",
        "decision": decision,
        "reasons": reasons,
        "ref_event_id": evt["event_id"],
    }


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/v1/ingest/phone-sensor")
def ingest_phone_sensor(inp: PhoneSensorIn):
    evt = normalize_phone_sensor(inp).model_dump()
    try:
        ingest_to_observer_hub(evt)
        intent = run_interpreter_dry_run(evt)
        record = append_event_to_audit_chain(evt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ingest failed: {type(e).__name__}: {e}")

    return {"ok": True, "event_id": evt["event_id"], "record": record, "intent": intent}
