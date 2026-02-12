from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, Literal
from datetime import datetime, timezone
import uuid

class PhoneSensorIn(BaseModel):
    device_id: str
    sensor: str
    value: float
    unit: Optional[str] = None
    timestamp: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)

class NormalizedEvent(BaseModel):
    schema: Literal["observer_event.v1"] = "observer_event.v1"
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: Dict[str, Any]
    kind: Literal["sensor.snapshot"] = "sensor.snapshot"
    payload: Dict[str, Any]

def normalize_phone_sensor(inp: PhoneSensorIn) -> NormalizedEvent:
    ts = inp.timestamp or datetime.now(timezone.utc).isoformat()
    return NormalizedEvent(
        ts=ts,
        source={"source_type": "phone", "device_id": inp.device_id},
        payload={"sensor": inp.sensor, "value": inp.value, "unit": inp.unit, "meta": inp.meta},
    )
