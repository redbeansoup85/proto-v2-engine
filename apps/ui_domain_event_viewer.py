#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st


DEFAULT_ROOT = "/tmp/metaos_domain_events"
FILE_GLOB = "domain_event_*.json"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _fmt_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")


def _load_event(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        raw = path.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return None, "JSON root is not an object"
        return parsed, None
    except Exception as exc:
        return None, str(exc)


def _discover_events(
    root: str, symbol_contains: str, risk_filter: str, kind_filter: str
) -> tuple[list[dict[str, Any]], list[str]]:
    base = Path(root)
    if not base.exists():
        return [], [f"Root path does not exist: {root}"]

    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    for path in base.rglob(FILE_GLOB):
        event, err = _load_event(path)
        if err:
            warnings.append(f"{path}: {err}")
            continue

        signal = event.get("signal", {}) if isinstance(event.get("signal"), dict) else {}
        symbol = str(signal.get("symbol", ""))
        risk_level = str(signal.get("risk_level", ""))
        kind = str(event.get("kind", ""))

        if symbol_contains and symbol_contains.lower() not in symbol.lower():
            continue
        if risk_filter != "ALL" and risk_level != risk_filter:
            continue
        if kind_filter != "ALL" and kind != kind_filter:
            continue

        row = {
            "mtime": _fmt_mtime(path),
            "symbol": symbol,
            "type": str(signal.get("type", "")),
            "timeframe": str(signal.get("timeframe", "")),
            "score": signal.get("score"),
            "confidence": signal.get("confidence"),
            "risk_level": risk_level,
            "filepath": str(path),
            "_event": event,
        }
        rows.append(row)

    rows.sort(key=lambda x: Path(x["filepath"]).stat().st_mtime, reverse=True)
    return rows, warnings


def _run_validator(event_path: str) -> tuple[int, str, str]:
    repo = _repo_root()
    proc = subprocess.run(
        [sys.executable, str(repo / "sdk" / "validate_domain_event.py"), event_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def main() -> None:
    st.set_page_config(page_title="domain_event.v1 Viewer", layout="wide")
    st.title("domain_event.v1 Viewer (Read-Only)")

    with st.sidebar:
        st.header("Scan")
        root = st.text_input("Root Path", value=DEFAULT_ROOT)
        refresh = st.button("Refresh")
        symbol_contains = st.text_input("Symbol Contains", value="")
        risk_filter = st.selectbox("risk_level", ["ALL", "low", "medium", "high"], index=0)
        kind_filter = st.selectbox("kind", ["ALL", "SIGNAL", "EMIT", "OBSERVATION"], index=0)
        if refresh:
            st.rerun()

    rows, warnings = _discover_events(root, symbol_contains, risk_filter, kind_filter)
    for warning in warnings:
        st.warning(warning)

    st.subheader("Discovered Events")
    if not rows:
        st.info("No matching domain_event files found.")
        return

    st.dataframe(
        [
            {
                "mtime": r["mtime"],
                "symbol": r["symbol"],
                "type": r["type"],
                "timeframe": r["timeframe"],
                "score": r["score"],
                "confidence": r["confidence"],
                "risk_level": r["risk_level"],
                "filepath": r["filepath"],
            }
            for r in rows
        ],
        use_container_width=True,
    )

    options = [
        f"{r['mtime']} | {r['symbol'] or 'n/a'} | {r['filepath']}"
        for r in rows
    ]
    selected = st.selectbox("Select Event", options=options, index=0)
    selected_row = rows[options.index(selected)]
    event = selected_row["_event"]

    st.subheader("Event Detail")
    st.write(
        {
            "domain": event.get("domain"),
            "kind": event.get("kind"),
            "event_id": event.get("event_id"),
            "ts_iso": event.get("ts_iso"),
        }
    )
    st.json(event)

    if st.button("Validate Selected Event"):
        rc, stdout, stderr = _run_validator(selected_row["filepath"])
        if rc == 0:
            st.success("PASS: domain_event.v1 valid")
        else:
            st.error(f"FAIL: validator exit code {rc}")
        if stdout.strip():
            st.code(stdout.strip(), language="text")
        if stderr.strip():
            st.code(stderr.strip(), language="text")


if __name__ == "__main__":
    main()
