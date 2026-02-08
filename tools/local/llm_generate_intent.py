#!/usr/bin/env python3
"""
Local LLM Intent Generator (Thin Slice v1, Fail-Closed)

- Reads user text from stdin
- Loads prompt template from contracts/prompts/...
- Calls local LLM backend (Ollama / LM Studio) OR mock (for tests)
- Outputs a single JSON object: sentinel_trade_intent.v1

Backends:
- ollama  : http://localhost:11434/api/generate
- lmstudio: OpenAI-compatible: http://localhost:1234/v1/chat/completions
- mock    : deterministic output for tests/CI without a running LLM
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


PROMPT_DEFAULT = "contracts/prompts/SENTINEL_TRADE_INTENT_PROMPT_v1.md"

ALLOWED_SIDE = {"LONG", "SHORT", "FLAT"}
RE_ASSET = re.compile(r"^[A-Z0-9]{3,12}$")
RE_INTENT_ID = re.compile(r"^INTENT-[A-Za-z0-9_-]{8,}$")


@dataclass
class LLMConfig:
    backend: str
    model: str
    endpoint: str
    timeout_s: int


def _fail(code: str, detail: str = "") -> None:
    msg = {"error": code, "detail": detail}
    print(json.dumps(msg, sort_keys=True), file=sys.stderr)
    raise SystemExit(2)


def _read_stdin_text() -> str:
    txt = sys.stdin.read()
    if txt is None:
        return ""
    txt = txt.strip()
    if not txt:
        _fail("EMPTY_INPUT")
    return txt


def _load_prompt(path: Path, user_text: str) -> str:
    if not path.exists():
        _fail("PROMPT_MISSING", str(path))
    template = path.read_text(encoding="utf-8")
    return template.replace("{{USER_TEXT}}", user_text)


def _http_json(url: str, payload: Dict[str, Any], timeout_s: int) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        _fail("HTTP_ERROR", f"{e.code} {e.reason}")
    except URLError as e:
        _fail("URL_ERROR", str(e.reason))
    except Exception as e:
        _fail("HTTP_UNKNOWN", str(e))

    try:
        return json.loads(raw)
    except Exception:
        _fail("LLM_BAD_JSON", raw[:2000])


def _extract_json_object(text: str) -> Dict[str, Any]:
    """
    Fail-closed JSON extraction:
    - Prefer parsing full text as JSON
    - Else find the first {...} block that parses as JSON object
    """
    t = text.strip()
    try:
        obj = json.loads(t)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # Find candidate JSON object substring
    # Minimal but robust: scan for first '{' then attempt progressive matching by counting braces.
    start = t.find("{")
    if start == -1:
        _fail("NO_JSON_OBJECT", t[:400])

    brace = 0
    in_str = False
    esc = False
    for i in range(start, len(t)):
        ch = t[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                brace += 1
            elif ch == "}":
                brace -= 1
                if brace == 0:
                    cand = t[start : i + 1]
                    try:
                        obj = json.loads(cand)
                        if isinstance(obj, dict):
                            return obj
                    except Exception:
                        _fail("JSON_OBJECT_PARSE_FAIL", cand[:800])
                    break

    _fail("JSON_OBJECT_NOT_FOUND", t[:400])
    return {}  # unreachable


def _validate_intent(obj: Dict[str, Any]) -> None:
    required = ["schema", "domain_id", "intent_id", "asset", "side", "mode", "notes"]
    for k in required:
        if k not in obj:
            _fail("INTENT_MISSING_KEY", k)

    if obj["schema"] != "sentinel_trade_intent.v1":
        _fail("INTENT_SCHEMA_MISMATCH", str(obj.get("schema")))
    if obj["domain_id"] != "sentinel.trade":
        _fail("INTENT_DOMAIN_MISMATCH", str(obj.get("domain_id")))
    if obj["mode"] != "DRY_RUN":
        _fail("INTENT_MODE_NOT_DRY_RUN", str(obj.get("mode")))

    if not isinstance(obj["intent_id"], str) or not RE_INTENT_ID.match(obj["intent_id"]):
        _fail("INTENT_BAD_INTENT_ID", str(obj.get("intent_id")))
    if not isinstance(obj["asset"], str) or not RE_ASSET.match(obj["asset"]):
        _fail("INTENT_BAD_ASSET", str(obj.get("asset")))
    if obj["side"] not in ALLOWED_SIDE:
        _fail("INTENT_BAD_SIDE", str(obj.get("side")))
    if not isinstance(obj["notes"], str) or len(obj["notes"].strip()) < 1:
        _fail("INTENT_BAD_NOTES", str(obj.get("notes")))


def _mk_intent_id() -> str:
    # deterministic-ish but unique; ok for thin slice
    return "INTENT-" + uuid.uuid4().hex[:10].upper()


def _backend_mock(user_text: str) -> Dict[str, Any]:
    # deterministic, fail-closed defaults
    u = user_text.upper()
    asset = "BTCUSDT"
    for tok in re.findall(r"[A-Z0-9]{3,12}", u):
        if tok.endswith("USDT") and 6 <= len(tok) <= 12:
            asset = tok
            break

    side = "FLAT"
    if "LONG" in u or "롱" in user_text:
        side = "LONG"
    elif "SHORT" in u or "숏" in user_text:
        side = "SHORT"

    return {
        "schema": "sentinel_trade_intent.v1",
        "domain_id": "sentinel.trade",
        "intent_id": _mk_intent_id(),
        "asset": asset,
        "side": side,
        "mode": "DRY_RUN",
        "notes": "mock intent (tests/ci)",
    }


def _backend_ollama(cfg: LLMConfig, prompt: str) -> Dict[str, Any]:
    # Ollama generate API
    payload = {
        "model": cfg.model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.0},
    }
    r = _http_json(cfg.endpoint, payload, cfg.timeout_s)
    # Typical: {"response":"...","done":true,...}
    txt = str(r.get("response", "")).strip()
    if not txt:
        _fail("OLLAMA_EMPTY_RESPONSE")
    return _extract_json_object(txt)


def _backend_lmstudio(cfg: LLMConfig, prompt: str) -> Dict[str, Any]:
    # OpenAI-compatible chat completions
    payload = {
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": "You output ONLY one JSON object. No prose."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
    }
    r = _http_json(cfg.endpoint, payload, cfg.timeout_s)
    try:
        txt = r["choices"][0]["message"]["content"]
    except Exception:
        _fail("LMSTUDIO_BAD_RESPONSE", json.dumps(r)[:1200])
    txt = str(txt).strip()
    if not txt:
        _fail("LMSTUDIO_EMPTY_RESPONSE")
    return _extract_json_object(txt)


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate sentinel_trade_intent.v1 JSON using local LLM (fail-closed).")
    ap.add_argument("--prompt-path", default=PROMPT_DEFAULT, help="Prompt template markdown path")
    ap.add_argument("--backend", default=os.getenv("LLM_BACKEND", "ollama"), choices=["ollama", "lmstudio", "mock"])
    ap.add_argument("--timeout", type=int, default=int(os.getenv("LLM_TIMEOUT_S", "30")))
    ap.add_argument("--model", default=os.getenv("LLM_MODEL", "").strip())
    ap.add_argument("--ollama-endpoint", default=os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434/api/generate"))
    ap.add_argument("--lmstudio-endpoint", default=os.getenv("LMSTUDIO_ENDPOINT", "http://localhost:1234/v1/chat/completions"))
    args = ap.parse_args()

    user_text = _read_stdin_text()
    prompt = _load_prompt(Path(args.prompt_path), user_text)

    backend = args.backend
    if backend == "mock":
        obj = _backend_mock(user_text)
    else:
        model = args.model
        if not model:
            # backend-specific defaults
            model = os.getenv("OLLAMA_MODEL", "llama3.1") if backend == "ollama" else os.getenv("LMSTUDIO_MODEL", "local-model")
        endpoint = args.ollama_endpoint if backend == "ollama" else args.lmstudio_endpoint
        cfg = LLMConfig(backend=backend, model=model, endpoint=endpoint, timeout_s=args.timeout)

        if backend == "ollama":
            obj = _backend_ollama(cfg, prompt)
        elif backend == "lmstudio":
            obj = _backend_lmstudio(cfg, prompt)
        else:
            _fail("BAD_BACKEND", backend)

    # Enforce deterministic safety defaults at the tool boundary
    obj["schema"] = "sentinel_trade_intent.v1"
    obj["domain_id"] = "sentinel.trade"
    obj["mode"] = "DRY_RUN"
    obj["intent_id"] = _mk_intent_id()

    _validate_intent(obj)

    sys.stdout.write(json.dumps(obj, sort_keys=True))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
