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

  const fetchCard = async (url: string, setState: any) => {
    setState((prev: any) => ({ ...prev, loading: true, error: false }));
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error("Fetch error");
      const json = await res.json();
      setState({ loading: false, error: false, data: json, showRaw: false });
    } catch (e) {
      setState({ loading: false, error: true, data: null, showRaw: false });
    }
  };

  const refreshAll = () => {
    fetchCard(`${BASE_URL}/api/intent/latest`, setIntent);
    fetchCard(`${BASE_URL}/api/audit/chain/status`, setAudit);
    fetchCard(`${BASE_URL}/api/executor/status`, setExecutor);
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

  return (
    <div style={{ fontFamily: "sans-serif", maxWidth: "900px", margin: "0 auto" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", margin: "1rem 0" }}>
        <h1>UI Dashboard</h1>
        <button onClick={refreshAll}>Refresh</button>
      </header>
      <Card title="Intent" cardState={intent} toggleRaw={() => setIntent((prev) => ({ ...prev, showRaw: !prev.showRaw }))} />
      <Card title="Audit Chain" cardState={audit} toggleRaw={() => setAudit((prev) => ({ ...prev, showRaw: !prev.showRaw }))} />
      <Card title="Executor" cardState={executor} toggleRaw={() => setExecutor((prev) => ({ ...prev, showRaw: !prev.showRaw }))} />
    </div>
  );
}

export default App;
