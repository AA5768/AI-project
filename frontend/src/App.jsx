import { useEffect, useState } from "react";
import { BASE_URL, api } from "./api/client";
import AskPage from "./pages/AskPage";
import MeasurementPage from "./pages/MeasurementPage";
import ReviewQueuePage from "./pages/ReviewQueuePage";
import "./App.css";

const TABS = [
  { id: "ask", label: "Ask", Page: AskPage },
  { id: "review", label: "Review queue", Page: ReviewQueuePage },
  { id: "measurement", label: "Measurement", Page: MeasurementPage },
];

export default function App() {
  const [tab, setTab] = useState("ask");
  const { Page } = TABS.find((t) => t.id === tab);

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand">
            <span className="brand-mark" aria-hidden="true" />
            <div>
              <h1>Meridian Microsystems</h1>
              <p className="brand-sub">Knowledge system</p>
            </div>
          </div>

          <nav className="tabs">
            {TABS.map((t) => (
              <button
                key={t.id}
                className={t.id === tab ? "tab active" : "tab"}
                onClick={() => setTab(t.id)}
                aria-current={t.id === tab ? "page" : undefined}
              >
                {t.label}
              </button>
            ))}
          </nav>

          <ApiStatus />
        </div>
      </header>

      <main className="main">
        <Page />
      </main>
    </div>
  );
}

/** A dead API is the failure a reviewer hits first, and it looks identical to
 *  an empty corpus from inside a page. Say which it is, in the header. */
function ApiStatus() {
  const [state, setState] = useState("checking");

  useEffect(() => {
    let cancelled = false;
    const ping = () =>
      api
        .health()
        .then(() => !cancelled && setState("up"))
        .catch(() => !cancelled && setState("down"));
    ping();
    const timer = setInterval(ping, 15000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  const label = { checking: "checking API…", up: "API connected", down: "API unreachable" }[state];
  return (
    <p className={`api-status api-${state}`} title={BASE_URL}>
      <span className="status-dot" aria-hidden="true" />
      {label}
    </p>
  );
}
