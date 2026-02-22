// 터미널에서 바로 덮어쓰기되는 완전 UI 버전
import { useEffect, useState } from "react";

const BASE_URL = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8787";

type CardData = {
  loading: boolean;
  error: boolean;
  data: any;
  showRaw: boolean;
};

function App() {
  const [intent, setIntent] = useState<CardData>({ loading: true, error: false, data: null, showRaw: false });
  const [audit, setAudit] = useState<CardData>({ loading: true, error: false, data: null, showRaw: false });
  const [executor, setExecutor] = useState<CardData>({ loading: true, error: false, data: null, showRaw: false });
  const [riskRegime, setRiskRegime] = useState<CardData>({ loading: true, error: false, data: null, showRaw: false });

  const [showKillConfirm, setShowKillConfirm] = useState(false);
  
  const [executorLastHttpCode, setExecutorLastHttpCode] = useState<number | null>(null);
const [killBusy, setKillBusy] = useState(false);
  const [killResult, setKillResult] = useState<string | null>(null);

  const fetchCard = async (url: string, setState: any, setLastHttpCode?: (code: number) => void) => {
    setState((prev: any) => ({ ...prev, loading: true, error: false }));
    try {
      const res = await fetch(url);
      
    setLastHttpCode?.(res.status);
if (!res.ok) throw new Error("Fetch error");
      const json = await res.json();
      setState({ loading: false, error: false, data: json, showRaw: false });
    } catch (e) {
    setLastHttpCode?.(0);
      setState({ loading: false, error: true, data: null, showRaw: false });
    }
  };

  const refreshAll = () => {
    fetchCard(`${BASE_URL}/api/intent/latest`, setIntent);
    fetchCard(`${BASE_URL}/api/audit/chain/status`, setAudit);
    fetchCard(`${BASE_URL}/api/executor/status`, setExecutor, setExecutorLastHttpCode);
    fetchCard(`${BASE_URL}/api/risk/regime`, setRiskRegime);
  };

  useEffect(() => {
    refreshAll();
    const timer = setInterval(refreshAll, 5000);
    return () => clearInterval(timer);
  }, []);

  const Card = ({ title, cardState, toggleRaw }: any) => (
    <div style={{ border: "1px solid #ccc", padding: "1rem", margin: "1rem", borderRadius: "8px" }}>
      <h2>{title}</h2>
      {cardState.loading && <p>Loading...</p>}
      {cardState.error && <p>n/a</p>}
      {!cardState.loading && !cardState.error && (
        <>
          {cardState.showRaw ? <pre>{JSON.stringify(cardState.data, null, 2)}</pre> : <p>{JSON.stringify(cardState.data)}</p>}
          <button onClick={toggleRaw} style={{ marginTop: "0.5rem" }}>Toggle JSON</button>
        </>
      )}
    </div>
  );

  // ---- executor status (normalized) + fail-closed banner ----
  const executorData: any = (executor as any)?.data ?? null;
  const intentData: any = (intent as any)?.data ?? null;

  // Normalize executor payload: some cards wrap data as { data: ... }
  const executorPayload: any =
    executorData && (executorData as any).data ? (executorData as any).data : executorData;

  const intentItems: any[] =
    intentData?.payload?.intent?.items ??
    intentData?.data?.payload?.intent?.items ??
    [];

  const denyCount = intentItems.filter((it: any) => it?.quality?.effects?.deny === true).length;
  const evidenceBadCount = intentItems.filter((it: any) => it?.quality?.evidence_ok === false).length;

  const killSwitch = executorPayload?.kill_switch === true;
  const failStreak = typeof executorPayload?.fail_streak === "number" ? executorPayload.fail_streak : 0;
  const observedHttpCode = executorLastHttpCode ?? null;

  // Fail-closed banner state (priority: kill_switch > transport > fail_streak)
  const executorBanner =
    killSwitch
      ? { level: "HALTED" as const, message: "EXECUTOR HALTED — kill switch ON (fail-closed)" }
      : (observedHttpCode === 0)
          ? { level: "DEGRADED" as const, message: "EXECUTOR DEGRADED — API unreachable (automation locked)" }
          : (observedHttpCode !== null && observedHttpCode >= 500)
              ? { level: "DEGRADED" as const, message: `EXECUTOR DEGRADED — API ${observedHttpCode} (automation locked)` }
              : (failStreak >= 2)
                  ? { level: "DEGRADED" as const, message: `EXECUTOR DEGRADED — fail_streak=${failStreak} (automation locked)` }
                  : { level: "OK" as const, message: "" };

  const automationLocked = executorBanner.level !== "OK";
  const riskPayload: any = (riskRegime as any)?.data ?? null;
  const riskCurrent = typeof riskPayload?.current_regime === "string" ? riskPayload.current_regime : "n/a";
  const riskCooldownMs = typeof riskPayload?.cooldown_remaining_ms === "number" ? riskPayload.cooldown_remaining_ms : 0;
  const riskReasons = Array.isArray(riskPayload?.reasons) ? riskPayload.reasons.join(", ") : "n/a";
  const riskMissing = Array.isArray(riskPayload?.missing) ? riskPayload.missing.join(", ") : "n/a";

  const formatCooldown = (ms: number) => {
    if (!Number.isFinite(ms) || ms <= 0) return "0m";
    const totalMin = Math.floor(ms / 60000);
    const h = Math.floor(totalMin / 60);
    const m = totalMin % 60;
    return h > 0 ? `${h}h${m}m` : `${m}m`;
  };

  // ---- kill-switch recommendation (UI fail-closed hint) ----


  const lockRecommended =
    (failStreak >= 2) ||
    denyCount > 0 ||
    evidenceBadCount > 0;

  // __LOCK_TEST_OVERRIDE__
  // const lockRecommended = true; // TEMP: force banner on
  // ---------------------------------------------------------
  const postJson = async (url: string, body: any = {}) => {
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body ?? {}),
    });
    const text = await res.text();
    let json: any = null;
    try { json = text ? JSON.parse(text) : null; } catch {}
    return { ok: res.ok, status: res.status, text, json };
  };

  const requestKillSwitch = async () => {
    if (automationLocked) {
      setKillResult("automation locked (fail-closed)");
      setShowKillConfirm(false);
      return;
    }
    setKillBusy(true);
    setKillResult(null);
    try {
      // 1st try: /api/executor/kill
      let r = await postJson(`${BASE_URL}/api/executor/kill`, {});
      if (!r.ok && r.status === 404) {
        // fallback: /api/executor/lock
        r = await postJson(`${BASE_URL}/api/executor/lock`, {});
      }

      if (r.ok) {
        setKillResult(`OK (${r.status})`);
      } else {
        const msg = r.json?.detail ?? r.text ?? "request failed";
        setKillResult(`FAIL (${r.status}): ${String(msg).slice(0, 200)}`);
      }

      // refresh executor card after action
      await fetchCard(`${BASE_URL}/api/executor/status`, setExecutor, setExecutorLastHttpCode);
    } catch (e: any) {
      setKillResult(`ERROR: ${e?.message ?? String(e)}`);
    } finally {
      setKillBusy(false);
      setShowKillConfirm(false);
    }
  };
  return (
    <div style={{ fontFamily: "sans-serif", maxWidth: "900px", margin: "0 auto" }}>
      <div style={{
        margin: "8px 0",
        padding: "10px 12px",
        borderRadius: 10,
        border: "1px solid rgba(60,120,255,0.45)",
        background: "rgba(60,120,255,0.12)",
        fontSize: 13,
        fontWeight: 700,
      }}>
        REGIME={riskCurrent} · cooldown={formatCooldown(riskCooldownMs)} · missing={riskMissing} · reasons={riskReasons}
      </div>

        {executorBanner.level !== "OK" && (
          <div style={{
            margin: "8px 0",
            padding: "10px 12px",
            borderRadius: 10,
            border: executorBanner.level === "HALTED"
              ? "1px solid rgba(255,60,60,0.55)"
              : "1px solid rgba(255,180,60,0.55)",
            background: executorBanner.level === "HALTED"
              ? "rgba(255,60,60,0.18)"
              : "rgba(255,180,60,0.14)",
            fontSize: 13,
            fontWeight: 700,
          }}>
            {executorBanner.message}
            <div style={{ marginTop: 6, fontSize: 12, fontWeight: 600, opacity: 0.9 }}>
              kill_switch={String(killSwitch)} · fail_streak={String(failStreak)} · ui_http={String(observedHttpCode ?? "n/a")} · base={String(BASE_URL)}
            </div>
          </div>
        )}

      {lockRecommended && (
        <div
          onClick={() => setShowKillConfirm(true)}
          style={{
            margin: "8px 0",
            padding: "10px 12px",
            borderRadius: 10,
            border: "1px solid rgba(255,60,60,0.55)",
            background: "rgba(255,60,60,0.18)",
            fontSize: 13,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          EXECUTION LOCK RECOMMENDED
        </div>
      )}

      {showKillConfirm && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.55)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 9999,
          }}
          onClick={() => !killBusy && setShowKillConfirm(false)}
        >
          <div
            style={{
              width: "min(520px, 92vw)",
              background: "#111",
              border: "1px solid rgba(255,255,255,0.15)",
              borderRadius: 14,
              padding: 14,
              boxShadow: "0 10px 30px rgba(0,0,0,0.35)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 10 }}>
              Confirm kill-switch request
            </div>

            <div style={{ fontSize: 13, opacity: 0.85, marginBottom: 12, lineHeight: 1.35 }}>
              This will request the executor to stop / lock execution. Use only when the system recommends LOCK.
            </div>

            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button
                disabled={killBusy}
                onClick={() => setShowKillConfirm(false)}
                style={{ padding: "8px 10px", borderRadius: 10, border: "1px solid rgba(255,255,255,0.15)", background: "transparent", color: "white" }}
              >
                Cancel
              </button>
              <button
                disabled={killBusy || automationLocked}
                title={automationLocked ? "automation locked (fail-closed)" : undefined}
                onClick={requestKillSwitch}
                style={{ padding: "8px 10px", borderRadius: 10, border: "1px solid rgba(255,60,60,0.45)", background: "rgba(255,60,60,0.25)", color: "white", fontWeight: 700 }}
              >
                {killBusy ? "Sending..." : "Confirm"}
              </button>
            </div>

            {killResult && (
              <div style={{ marginTop: 10, fontSize: 12, opacity: 0.9 }}>
                {killResult}
              </div>
            )}
          </div>
        </div>
      )}
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", margin: "1rem 0" }}>
        <h1>UI Dashboard</h1>
        <button onClick={refreshAll}>Refresh</button>
      </header>
      <Card title="Intent" cardState={intent} toggleRaw={() => setIntent((prev) => ({ ...prev, showRaw: !prev.showRaw }))} />
      <Card title="Audit Chain" cardState={audit} toggleRaw={() => setAudit((prev) => ({ ...prev, showRaw: !prev.showRaw }))} />
      <Card title="Executor" cardState={executor} toggleRaw={() => setExecutor((prev) => ({ ...prev, showRaw: !prev.showRaw }))} />
      <Card title="Risk Regime (SSOT)" cardState={riskRegime} toggleRaw={() => setRiskRegime((prev) => ({ ...prev, showRaw: !prev.showRaw }))} />
    </div>
  );
}

export default App;
