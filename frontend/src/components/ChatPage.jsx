import { useCallback, useEffect, useRef, useState } from "react";
import { Download, Moon, Send, Square, Sun } from "lucide-react";
import ItineraryCards from "./chat/ItineraryCards";
import TripMap from "./chat/TripMap";
import RefinementChips from "./chat/RefinementChips";
import TypingIndicator from "./chat/TypingIndicator";
import { usePlanStream } from "../hooks/usePlanStream";
import { exportItinerary, refineTrip } from "../services/api";

const NODE_LABELS = {
  parse_preferences: "Parsing your request",
  allocate_budget: "Allocating budget",
  search_flights: "Searching flights",
  search_hotels: "Finding hotels",
  find_attractions: "Discovering attractions",
  find_restaurants: "Finding restaurants",
  check_weather: "Checking weather",
  track_budget: "Tracking budget",
  build_geo_clusters: "Clustering locations",
  build_itinerary: "Building itinerary",
  optimize_routes: "Optimizing routes",
  evaluate_budget: "Evaluating budget",
  assemble_output: "Assembling final plan",
};

function StreamingBubble({ steps }) {
  return (
    <div className="bubble bubble--assistant">
      <div className="stream-steps">
        {steps.map((s, i) => {
          const isLast = i === steps.length - 1;
          return (
            <div key={i} className={`stream-step${isLast ? " stream-step--active" : " stream-step--done"}`}>
              <span className="stream-step__icon">{isLast ? "⟳" : "✓"}</span>
              <span>{s.text}</span>
            </div>
          );
        })}
      </div>
      <TypingIndicator />
    </div>
  );
}

function AssistantBubble({ msg }) {
  return (
    <div className="bubble bubble--assistant">
      <p className="bubble__intro">Here's your itinerary! 🗺️</p>
      {msg.itinerary && Object.keys(msg.itinerary).length > 0 ? (
        <>
          <ItineraryCards itinerary={msg.itinerary} />
          <TripMap itinerary={msg.itinerary} />
        </>
      ) : (
        <p className="bubble__empty">Planning complete — no itinerary data returned.</p>
      )}
    </div>
  );
}

function UserBubble({ text }) {
  return <div className="bubble bubble--user">{text}</div>;
}

function ErrorBubble({ text }) {
  return <div className="bubble bubble--error">⚠ {text}</div>;
}

export default function ChatPage() {
  const [dark, setDark] = useState(() => localStorage.getItem("theme") === "dark");
  const [input, setInput] = useState("");
  const [chatLog, setChatLog] = useState([]); // [{type: "user"|"assistant"|"error", ...}]
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  const { messages, streaming, sessionId, startPlan, cancel, addMsg } = usePlanStream();

  const progressSteps = messages.filter((m) => m.role === "progress");
  const lastItinerary = [...messages].reverse().find((m) => m.itinerary)?.itinerary || null;

  // when streaming finishes and we have a result, add to chatLog
  useEffect(() => {
    if (!streaming && messages.length > 0) {
      const done = messages.find((m) => m.role === "assistant");
      const err = messages.find((m) => m.role === "error");
      if (done) {
        setChatLog((prev) => {
          // avoid duplicates
          const last = prev[prev.length - 1];
          if (last?.type === "assistant" && last?.itinerary === done.itinerary) return prev;
          return [...prev, { type: "assistant", itinerary: done.itinerary }];
        });
      } else if (err) {
        setChatLog((prev) => [...prev, { type: "error", text: err.text }]);
      }
    }
  }, [streaming, messages]);

  // dark mode
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);

  // auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatLog, streaming, progressSteps.length]);

  // keyboard shortcuts
  useEffect(() => {
    const handler = (e) => {
      if (e.key === "Escape") cancel();
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [cancel]);

  const parseInput = (text) => {
    const daysMatch = text.match(/(\d+)\s*day/i);
    const budgetMatch = text.match(/\$(\d+)/);
    const days = daysMatch ? parseInt(daysMatch[1]) : 5;
    const budget = budgetMatch ? parseInt(budgetMatch[1]) : 1500;
    const destMatch = text.match(/^([A-Za-z\s]+?)(?:\s+\d|\s*$)/);
    const destination = destMatch ? destMatch[1].trim() : text.split(" ")[0];
    return { destination, days, budget, extra: text };
  };

  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text || streaming) return;
    setChatLog((prev) => [...prev, { type: "user", text }]);
    setInput("");
    const { destination, days, budget, extra } = parseInput(text);
    startPlan(destination, days, budget, extra);
  }, [input, streaming, startPlan]);

  const handleRefine = useCallback(
    async (instruction) => {
      if (!sessionId || streaming) return;
      setChatLog((prev) => [...prev, { type: "user", text: instruction }]);
      try {
        await refineTrip(sessionId, instruction);
        startPlan(instruction, 5, 1500, instruction);
      } catch {
        setChatLog((prev) => [...prev, { type: "error", text: "Refinement failed. Try again." }]);
      }
    },
    [sessionId, streaming, startPlan]
  );

  const handleExport = useCallback(
    async (fmt) => {
      if (!sessionId) return;
      try {
        if (fmt === "json") {
          const data = await exportItinerary(sessionId, "json");
          const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
          const url = URL.createObjectURL(blob);
          Object.assign(document.createElement("a"), { href: url, download: "itinerary.json" }).click();
        } else {
          const blob = await exportItinerary(sessionId, fmt);
          const url = URL.createObjectURL(blob);
          Object.assign(document.createElement("a"), { href: url, download: `itinerary.${fmt}` }).click();
        }
      } catch {
        setChatLog((prev) => [...prev, { type: "error", text: "Export failed." }]);
      }
    },
    [sessionId]
  );

  return (
    <div className="chat-page">
      {/* ── header ── */}
      <header className="chat-header">
        <div className="chat-header__brand">✈ AI Travel Planner</div>
        <div className="chat-header__actions">
          {sessionId && (
            <div className="export-group">
              <button className="icon-btn" onClick={() => handleExport("json")}><Download size={14} /> JSON</button>
              <button className="icon-btn" onClick={() => handleExport("markdown")}><Download size={14} /> MD</button>
              <button className="icon-btn" onClick={() => handleExport("pdf")}><Download size={14} /> PDF</button>
            </div>
          )}
          <button className="icon-btn icon-btn--round" onClick={() => setDark((d) => !d)}>
            {dark ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>
      </header>

      {/* ── messages ── */}
      <main className="chat-messages">
        {chatLog.length === 0 && !streaming && (
          <div className="chat-empty">
            <div className="chat-empty__icon">✈</div>
            <h2>Plan your perfect trip</h2>
            <p>Tell me where you want to go and I'll build a full itinerary for you.</p>
            <div className="chat-empty__examples">
              {["Paris 5 days $2000", "Tokyo family trip 7 days $3000", "Bali beach holiday 10 days $1500"].map((ex) => (
                <button key={ex} className="example-chip" onClick={() => { setInput(ex); inputRef.current?.focus(); }}>
                  {ex}
                </button>
              ))}
            </div>
            <p className="chat-empty__shortcuts">
              <kbd>Enter</kbd> send &nbsp;·&nbsp; <kbd>Shift+Enter</kbd> new line &nbsp;·&nbsp; <kbd>Ctrl+K</kbd> focus &nbsp;·&nbsp; <kbd>Esc</kbd> cancel
            </p>
          </div>
        )}

        {chatLog.map((entry, i) => {
          if (entry.type === "user") return <UserBubble key={i} text={entry.text} />;
          if (entry.type === "error") return <ErrorBubble key={i} text={entry.text} />;
          if (entry.type === "assistant") return <AssistantBubble key={i} msg={entry} />;
          return null;
        })}

        {/* live streaming bubble */}
        {streaming && progressSteps.length > 0 && (
          <StreamingBubble steps={progressSteps} />
        )}

        <div ref={bottomRef} />
      </main>

      {/* ── refinement chips ── */}
      {lastItinerary && !streaming && (
        <RefinementChips onChip={handleRefine} disabled={streaming} />
      )}

      {/* ── input bar ── */}
      <footer className="chat-input-bar">
        <textarea
          ref={inputRef}
          className="chat-input"
          rows={1}
          placeholder="Where do you want to go?"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
          }}
          disabled={streaming}
        />
        {streaming ? (
          <button className="send-btn send-btn--cancel" onClick={cancel} title="Cancel (Esc)">
            <Square size={18} />
          </button>
        ) : (
          <button className="send-btn" onClick={handleSend} disabled={!input.trim()}>
            <Send size={18} />
          </button>
        )}
      </footer>
    </div>
  );
}
