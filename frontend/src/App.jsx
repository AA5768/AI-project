import { useState } from "react";
import AskPage from "./pages/AskPage";
import ReviewQueuePage from "./pages/ReviewQueuePage";
import "./App.css";

const TABS = {
  ask: AskPage,
  review: ReviewQueuePage,
};

function App() {
  const [tab, setTab] = useState("ask");
  const ActivePage = TABS[tab];

  return (
    <div>
      <header>
        <h1>Meridian Robotics Knowledge System</h1>
        <nav>
          <button onClick={() => setTab("ask")} disabled={tab === "ask"}>
            Ask
          </button>
          <button onClick={() => setTab("review")} disabled={tab === "review"}>
            Review Queue
          </button>
        </nav>
      </header>
      <main>
        <ActivePage />
      </main>
    </div>
  );
}

export default App;
