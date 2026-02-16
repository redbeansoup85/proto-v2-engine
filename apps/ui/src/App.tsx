import { useEffect, useMemo, useState } from "react";

type IntentItem = {
  symbol?: string;
};

type IntentPayload = {
  event_id?: string;
  ts_iso?: string;
  intent?: {
    execution_mode?: string;
    dry_run?: boolean;
    items?: IntentItem[];
  };
  error?: string;
};

type ChainEntry = {
  lines: string | number;
  last_hash: string;
};

type ChainStatus = {
  execution_intent: ChainEntry;
  paper_orders: ChainEntry;
  paper_fills: ChainEntry;
};

type ExecutorStatus = {
  fail_streak: number | string;
  last_http_code: string | number;
  last_event_id: string;
};

type CardLoading = {
  intent: boolean;
  chain: boolean;
  executor: boolean;
};

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8787";

const defaultChain: ChainStatus = {
  execution_intent: { lines: "n/a", last_hash: "n/a" },
  paper_orders: { lines: "n/a", last_hash: "n/a" },
  paper_fills: { lines: "n/a", last_hash: "n/a" }
};

const defaultExecutor: ExecutorStatus = {
  fail_streak: 0,
  last_http_code: "n/a",
  last_event_id: "n/a"
};

function safeText(value: unknown): string {
  if (value === null || value === undefined) {
    return "n/a";
  }
  if (typeof value === "string" && value.trim() === "") {
    return "n/a";
  }
  return String(value);
}

function statusChip(kind: "intent" | "chain" | "executor", data: unknown): "OK" | "WARN" | "NA" {
  if (!data) {
    return "NA";
  }
  if (kind === "intent") {
    const intent = data as IntentPayload;
    if (intent.error) {
      return "NA";
    }
    return intent.event_id ? "OK" : "NA";
  }
  if (kind === "chain") {
    const chain = data as ChainStatus;
    const hasValid = [chain.execution_intent, chain.paper_orders, chain.paper_fills].some(
      (x) => x.lines !== "n/a" || x.last_hash !== "n/a"
    );
    return hasValid ? "OK" : "NA";
  }
  const ex = data as ExecutorStatus;
  if (safeText(ex.last_http_code) === "n/a" && safeText(ex.last_event_id) === "n/a") {
    return "NA";
  }
  if (typeof ex.fail_streak === "number" && ex.fail_streak > 0) {
    return "WARN";
  }
  return "OK";
}

async function fetchJson<T>(url: string, fallback: T): Promise<T> {
  try {
    const res = await fetch(url, { method: "GET" });
    const text = await res.text();
    if (!text) {
      return fallback;
    }
    try {
      const parsed = JSON.parse(text) as T;
      return parsed;
    } catch {
      return fallback;
    }
  } catch {
    return fallback;
  }
}

export default function App() {
  const [intent, setIntent] = useState<IntentPayload | null>(null);
  const [chain, setChain] = useState<ChainStatus>(defaultChain);
  const [executor, setExecutor] = useState<ExecutorStatus>(defaultExecutor);
  const [lastRefresh, setLastRefresh] = useState<string>("n/a");
  const [showRaw, setShowRaw] = useState(false);
  const [loading, setLoading] = useState<CardLoading>({ intent: false, chain: false, executor: false });

  const intentCount = useMemo(() => {
    const items = intent?.intent?.items;
    return Array.isArray(items) ? items.length : "n/a";
  }, [intent]);

  const refreshAll = async () => {
    setLoading((prev) => ({ ...prev, intent: true, chain: true, executor: true }));

    const p1 = fetchJson<IntentPayload>(`${API_BASE}/api/intent/latest`, { error: "n/a" })
      .then((intentResp) => setIntent(intentResp))
      .finally(() => setLoading((prev) => ({ ...prev, intent: false })));

    const p2 = fetchJson<ChainStatus>(`${API_BASE}/api/audit/chain/status`, defaultChain)
      .then((chainResp) =>
        setChain({
          execution_intent: chainResp.execution_intent || { lines: "n/a", last_hash: "n/a" },
          paper_orders: chainResp.paper_orders || { lines: "n/a", last_hash: "n/a" },
          paper_fills: chainResp.paper_fills || { lines: "n/a", last_hash: "n/a" }
        })
      )
      .finally(() => setLoading((prev) => ({ ...prev, chain: false })));

    const p3 = fetchJson<ExecutorStatus>(`${API_BASE}/api/executor/status`, defaultExecutor)
      .then((executorResp) =>
        setExecutor({
          fail_streak: executorResp.fail_streak ?? 0,
          last_http_code: executorResp.last_http_code ?? "n/a",
          last_event_id: safeText(executorResp.last_event_id)
        })
      )
      .finally(() => setLoading((prev) => ({ ...prev, executor: false })));

    await Promise.allSettled([p1, p2, p3]);
    setLastRefresh(new Date().toLocaleTimeString());
  };

  useEffect(() => {
    refreshAll();
    const timer = window.setInterval(refreshAll, 5000);
    return () => window.clearInterval(timer);
  }, []);

  const intentStatus = statusChip("intent", intent);
  const chainStatus = statusChip("chain", chain);
  const executorStatus = statusChip("executor", executor);

  return (
    <div className="page">
      <header className="topbar">
        <div>
          <h1>Sentinel Observer Hub</h1>
          <p className="sub">Read-only control plane dashboard</p>
        </div>
        <div className="badges">
          <span className="badge">API: {API_BASE}</span>
          <span className="badge">Last refresh: {lastRefresh}</span>
          <button className="refresh" onClick={refreshAll}>Refresh</button>
        </div>
      </header>

      <main className="grid">
        <section className="card">
          <div className="cardHead">
            <h2>Intent (Latest)</h2>
            <div className="headRight">
              {loading.intent && <span className="spinner" aria-label="loading" />}
              <span className={`chip ${intentStatus.toLowerCase()}`}>{intentStatus}</span>
            </div>
          </div>

          {intent?.error || !intent?.event_id ? (
            <p className="na">no intent found / n/a</p>
          ) : (
            <dl className="kv">
              <div><dt>event_id</dt><dd>{safeText(intent.event_id)}</dd></div>
              <div><dt>ts</dt><dd>{safeText(intent.ts_iso)}</dd></div>
              <div><dt>execution_mode</dt><dd>{safeText(intent.intent?.execution_mode)}</dd></div>
              <div><dt>dry_run</dt><dd>{safeText(intent.intent?.dry_run)}</dd></div>
              <div><dt>items_count</dt><dd>{safeText(intentCount)}</dd></div>
            </dl>
          )}

          <button className="rawToggle" onClick={() => setShowRaw((prev) => !prev)}>
            {showRaw ? "hide raw" : "show raw"}
          </button>
          {showRaw && <pre className="raw">{JSON.stringify(intent ?? { error: "n/a" }, null, 2)}</pre>}
        </section>

        <section className="card">
          <div className="cardHead">
            <h2>Audit Chain Status</h2>
            <div className="headRight">
              {loading.chain && <span className="spinner" aria-label="loading" />}
              <span className={`chip ${chainStatus.toLowerCase()}`}>{chainStatus}</span>
            </div>
          </div>

          <table className="table">
            <thead>
              <tr>
                <th>chain</th>
                <th>lines</th>
                <th>last_hash</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>execution_intent.jsonl</td>
                <td>{safeText(chain.execution_intent.lines)}</td>
                <td><code>{safeText(chain.execution_intent.last_hash)}</code></td>
              </tr>
              <tr>
                <td>paper_orders.jsonl</td>
                <td>{safeText(chain.paper_orders.lines)}</td>
                <td><code>{safeText(chain.paper_orders.last_hash)}</code></td>
              </tr>
              <tr>
                <td>paper_fills.jsonl</td>
                <td>{safeText(chain.paper_fills.lines)}</td>
                <td><code>{safeText(chain.paper_fills.last_hash)}</code></td>
              </tr>
            </tbody>
          </table>
        </section>

        <section className="card">
          <div className="cardHead">
            <h2>Executor Status</h2>
            <div className="headRight">
              {loading.executor && <span className="spinner" aria-label="loading" />}
              <span className={`chip ${executorStatus.toLowerCase()}`}>{executorStatus}</span>
            </div>
          </div>

          <dl className="kv">
            <div><dt>fail_streak</dt><dd>{safeText(executor.fail_streak)}</dd></div>
            <div><dt>last_http_code</dt><dd>{safeText(executor.last_http_code)}</dd></div>
            <div><dt>last_event_id</dt><dd>{safeText(executor.last_event_id)}</dd></div>
          </dl>
        </section>
      </main>
    </div>
  );
}
