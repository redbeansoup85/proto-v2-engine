import os, requests
from fastapi import FastAPI
from pydantic import BaseModel
from audit_chain import append_audit
from lock4_gate import load_policy, gate

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
POLICY_PATH = os.getenv("LOCK4_POLICY_PATH", "/app/policies/LOCK4.yaml")
MODEL_MAIN = os.getenv("MODEL_MAIN", "mistral")

policy = load_policy(POLICY_PATH)
app = FastAPI(title="Auralis v1.0")

class AskReq(BaseModel):
    text: str

@app.post("/ask")
def ask(req: AskReq):
    ok, meta = gate(policy, req.text, "LOG_ONLY")
    audit_in = append_audit({"kind": "INPUT", "text": req.text, "gate": meta})
    if not ok:
        return {"blocked": True, "audit": audit_in}

    r = requests.post(f"{OLLAMA_URL}/api/generate", json={
        "model": MODEL_MAIN,
        "prompt": req.text,
        "stream": False
    })
    out = r.json().get("response", "")

    ok2, meta2 = gate(policy, out, "LOG_ONLY")
    audit_out = append_audit({"kind": "OUTPUT", "text": out, "gate": meta2})
    if not ok2:
        return {"blocked": True, "audit": audit_out}

    return {"response": out}
