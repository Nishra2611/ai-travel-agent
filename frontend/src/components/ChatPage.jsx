import { useCallback, useEffect, useRef, useState } from "react";
import { Download, Moon, Send, Square, Sun } from "lucide-react";
import ItineraryCards from "./chat/ItineraryCards";
import TripMap from "./chat/TripMap";
import RefinementChips from "./chat/RefinementChips";
import TypingIndicator from "./chat/TypingIndicator";
import { usePlanStream } from "../hooks/usePlanStream";
import { exportItinerary, refineTrip } from "../services/api";

/* ── streaming bubble (live progress) ─────────────────────────────────────── */
function StreamingBubble({ steps }) {
  return (
    <div className="bubble bubble--assistant">
      <div className="stream-steps">
        {steps.map((s, i) => {
          const isLast = i === steps.length - 1;
          return (
            <div key={i} className={`stream-step ${isLast ? "stream-step--active" : "stream-step--done"}`}>
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

/* ── assistant result bubble ───────────────────────────────────────────────── */
function AssistantBubble({ msg }) {
  const hasItinerary = msg.itinerary && Object.keys(msg.itinerary).length > 0;
  const hasFlights = msg.flights && msg.flights.length > 0;
  const hasHotels = msg.hotels && msg.hotels.length > 0;
  const hasWeather = msg.weather && msg.weather.length > 0;
  const hasBudget = msg.budget && Object.keys(msg.budget).length > 0;

  return (
    <div className="bubble bubble--assistant">
      <p className="bubble__intro">✈ Here's your {msg.destination} trip plan!</p>

      {/* itinerary days */}
      {hasItinerary ? (
        <ItineraryCards itinerary={msg.itinerary} />
      ) : (
        <p className="bubble__empty">No itinerary data returned — check backend logs.</p>
      )}

      {/* map */}
      {hasItinerary && <TripMap itinerary={msg.itinerary} />}

      {/* flights */}
      {hasFlights && (
        <div className="result-section">
          <h4 className="result-section__title">✈ Flights</h4>
          {msg.flights.map((f, i) => (
            <div key={i} className="result-card">
              <span className="result-card__name">{f.airline || f.segments?.[0]?.airline || "Flight"}</span>
              <span className="result-card__detail">{f.segments?.[0]?.departure_airport} → {f.segments?.[0]?.arrival_airport}</span>
              <span className="result-card__price">${f.total_price_usd?.toFixed(0)}</span>
            </div>
          ))}
        </div>
      )}

      {/* hotels */}
      {hasHotels && (
        <div className="result-section">
          <h4 className="result-section__title">🏨 Hotels</h4>
          {msg.hotels.map((h, i) => (
            <div key={i} className="result-card">
              <span className="result-card__name">{h.name}</span>
              <span className="result-card__detail">{"⭐".repeat(Math.round(h.star_rating || 0))} · {h.review_score?.toFixed(1) || "N/A"}/5</span>
              <span className="result-card__price">${h.price_per_night_usd?.toFixed(0)}/night</span>
            </div>
          ))}
        </div>
      )}

      {/* weather */}
      {hasWeather && (
        <div className="result-section">
          <h4 className="result-section__title">🌤 Weather Forecast</h4>
          <div className="weather-row">
            {msg.weather.map((w, i) => (
              <div key={i} className="weather-card">
                <span className="weather-card__date">{w.date || `Day ${i + 1}`}</span>
                <span className="weather-card__desc">{w.description || w.condition || "—"}</span>
                <span className="weather-card__temp">{w.temp_max ?? w.temperature ?? "—"}°C</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* budget */}
      {hasBudget && (
        <div className="result-section">
          <h4 className="result-section__title">💰 Budget Summary</h4>
          <div className="budget-row">
            {msg.budget.total_budget != null && (
              <span className="budget-pill">Total: ${msg.budget.total_budget?.toFixed(0)}</span>
            )}
            {msg.budget.total_spent != null && (
              <span className="budget-pill">Spent: ${msg.budget.total_spent?.toFixed(0)}</span>
            )}
            {msg.budget.remaining != null && (
              <span className="budget-pill budget-pill--green">Remaining: ${msg.budget.remaining?.toFixed(0)}</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── main chat page ────────────────────────────────────────────────────────── */
export default function ChatPage() {
  const [dark, setDark] = useState(() => localStorage.getItem("theme") === "dark");
  const [input, setInput] = useState("");
  const [chatLog, setChatLog] = useState([]);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  const { messages, streaming, sessionId, startPlan, cancel, addMsg } = usePlanStream();

  const progressSteps = messages.filter((m) => m.role === "progress");
  const lastItinerary = [...messages].reverse().find((m) => m.itinerary)?.itinerary || null;

  // when streaming finishes, move result into chatLog
  useEffect(() => {
    if (!streaming && messages.length > 0) {
      const done = messages.find((m) => m.role === "assistant");
      const err = messages.find((m) => m.role === "error");
      if (done) {
        setChatLog((prev) => {
          const last = prev[prev.length - 1];
          if (last?.type === "assistant" && last?.itinerary === done.itinerary) return prev;
          return [...prev, { type: "assistant", ...done }];
        });
      } else if (err) {
        setChatLog((prev) => [...prev, { type: "error", text: err.text }]);
      }
    }
  }, [streaming, messages]);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatLog, streaming, progressSteps.length]);

  useEffect(() => {
    const handler = (e) => {
      if (e.key === "Escape") cancel();
      if ((e.ctrlKey || e.metaKey) && e.key === "k") { e.preventDefault(); inputRef.current?.focus(); }
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

  const handleRefine = useCallback(async (instruction) => {
    if (!sessionId || streaming) return;
    setChatLog((prev) => [...prev, { type: "user", text: instruction }]);
    try {
      await refineTrip(sessionId, instruction);
      startPlan(instruction, 5, 1500, instruction);
    } catch {
      setChatLog((prev) => [...prev, { type: "error", text: "Refinement failed." }]);
    }
  }, [sessionId, streaming, startPlan]);

  const handleExport = useCallback(async (fmt) => {
    if (!sessionId) return;
    try {
      const data = await exportItinerary(sessionId, fmt);
      const isBlob = data instanceof Blob;
      const blob = isBlob ? data : new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const ext = fmt === "markdown" ? "md" : fmt;
      Object.assign(document.createElement("a"), { href: url, download: `itinerary.${ext}` }).click();
    } catch {
      setChatLog((prev) => [...prev, { type: "error", text: "Export failed." }]);
    }
  }, [sessionId]);

  return (
    <div className="chat-page">
      {/* header */}
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

      {/* messages */}
      <main className="chat-messages">
        {chatLog.length === 0 && !streaming && (
          <div className="chat-empty">
            <div className="chat-empty__icon">✈</div>
            <h2>Plan your perfect trip</h2>
            <p>Tell me where you want to go and I'll build a full itinerary with flights, hotels, weather and budget.</p>
            <div className="chat-empty__examples">
              {["Paris 5 days $2000", "Tokyo 7 days $3000", "Bali 10 days $1500"].map((ex) => (
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
          if (entry.type === "user") return <div key={i} className="bubble bubble--user">{entry.text}</div>;
          if (entry.type === "error") return <div key={i} className="bubble bubble--error">⚠ {entry.text}</div>;
          if (entry.type === "assistant") return <AssistantBubble key={i} msg={entry} />;
          return null;
        })}

        {streaming && progressSteps.length > 0 && <StreamingBubble steps={progressSteps} />}

        <div ref={bottomRef} />
      </main>

      {lastItinerary && !streaming && <RefinementChips onChip={handleRefine} disabled={streaming} />}

      {/* input */}
      <footer className="chat-input-bar">
        <textarea
          ref={inputRef}
          className="chat-input"
          rows={1}
          placeholder="Where do you want to go?"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
          disabled={streaming}
        />
        {streaming
          ? <button className="send-btn send-btn--cancel" onClick={cancel}><Square size={18} /></button>
          : <button className="send-btn" onClick={handleSend} disabled={!input.trim()}><Send size={18} /></button>
        }
      </footer>
    </div>
  );
}
