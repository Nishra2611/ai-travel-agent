import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  BedDouble,
  CloudSun,
  Download,
  Landmark,
  Moon,
  Plane,
  Send,
  Square,
  Sun,
  WalletCards,
} from "lucide-react";
import ItineraryCards from "./chat/ItineraryCards";
import TripMap from "./chat/TripMap";
import RefinementChips from "./chat/RefinementChips";
import TypingIndicator from "./chat/TypingIndicator";
import { HotelCard } from "./shared/HotelCard";
import { usePlanStream } from "../hooks/usePlanStream";
import { useGlobalState } from "../context/GlobalState";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import "./ChatPage.css";

function StreamingBubble({ steps }) {
  return (
    <div className="bubble bubble--assistant">
      <div className="stream-steps">
        {steps.map((s, i) => {
          const isLast = i === steps.length - 1;
          return (
            <div key={`${s.node}-${i}`} className={`stream-step ${isLast ? "stream-step--active" : "stream-step--done"}`}>
              <span className="stream-step__icon">{isLast ? <TypingIndicator compact /> : "OK"}</span>
              <span>{typeof s.text === 'object' ? JSON.stringify(s.text) : s.text}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function AssistantBubble({ msg, onExport }) {
  const hasItinerary = msg.itinerary && Object.keys(msg.itinerary).length > 0;
  const hasFlights = msg.flights && msg.flights.length > 0;
  const hasHotels = msg.hotels && msg.hotels.length > 0;
  const hasWeather = msg.weather && msg.weather.length > 0;
  const hasBudget = msg.budget && Object.keys(msg.budget).length > 0;

  return (
    <div className="bubble bubble--assistant">
      <p className="bubble__intro">
        <Plane size={17} /> Here is your {msg.destination} trip plan.
      </p>

      {hasItinerary ? <ItineraryCards itinerary={msg.itinerary} /> : <p className="bubble__empty">No itinerary data returned. Check backend logs.</p>}

      {hasItinerary && <TripMap itinerary={msg.itinerary} destination={msg.destination} />}

      {hasFlights && (
        <div className="result-section">
          <h4 className="result-section__title"><Plane size={15} /> Flights</h4>
          {msg.flights.map((f, i) => (
            <div key={`${f.airline}-${i}`} className="mini-result-card">
              <span className="result-card__name">{f.airline || "Flight"}</span>
              <span className="result-card__detail">{f.from} to {f.to} - {f.stops === 0 ? "Direct" : `${f.stops} stop`}</span>
              <span className="result-card__price">${Number(f.price || 0).toFixed(0)}</span>
            </div>
          ))}
        </div>
      )}

      {hasHotels && (
        <div className="result-section">
          <h4 className="result-section__title"><BedDouble size={15} /> Hotels</h4>
          <div className="results-grid">
            {msg.hotels.map((h, i) => (
              <HotelCard key={h.id || `${h.name}-${i}`} hotel={h} index={i} standalone />
            ))}
          </div>
        </div>
      )}

      {hasWeather && (
        <div className="result-section">
          <h4 className="result-section__title"><CloudSun size={15} /> Weather Forecast</h4>
          <div className="chat-weather-row">
            {msg.weather.map((w, i) => (
              <div key={`${w.date}-${i}`} className="chat-weather-card">
                <span className="weather-card__date">{w.date || `Day ${i + 1}`}</span>
                <span className="weather-card__desc">{w.description || w.condition || "Forecast"}</span>
                <span className="weather-card__temp">{w.temp_max ?? w.temperature ?? "--"} deg</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {hasBudget && (
        <div className="result-section">
          <h4 className="result-section__title"><WalletCards size={15} /> Budget Summary</h4>
          <div className="budget-row">
            {msg.budget.total != null && <span className="budget-pill">Total: ${Number(msg.budget.total).toFixed(0)}</span>}
            {msg.budget.spent != null && <span className="budget-pill">Spent: ${Number(msg.budget.spent).toFixed(0)}</span>}
            {msg.budget.remaining != null && <span className="budget-pill budget-pill--green">Remaining: ${Number(msg.budget.remaining).toFixed(0)}</span>}
            {msg.budget.by_category && Object.entries(msg.budget.by_category).map(([cat, amt]) => (
              <span key={cat} className="budget-pill">{cat}: ${Number(amt).toFixed(0)}</span>
            ))}
          </div>
        </div>
      )}

      {hasItinerary && onExport && (
        <div className="bubble-actions">
          <button className="icon-btn" type="button" onClick={() => onExport("pdf")} title="Download PDF itinerary">
            <Download size={15} /> PDF Itinerary
          </button>
        </div>
      )}
    </div>
  );
}

function parseInput(text) {
  const daysMatch = text.match(/(\d+)\s*day/i);
  const budgetMatch = text.match(/\$\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:\$|usd|dollars?)/i);
  const days = daysMatch ? parseInt(daysMatch[1], 10) : 5;
  const budget = budgetMatch ? parseFloat(budgetMatch[1] || budgetMatch[2]) : null;
  const destMatch = text.match(/^([A-Za-z][A-Za-z\s,.-]+?)(?:\s+\d|\s+under|\s+for|\s+\$|$)/i);
  const destination = destMatch ? destMatch[1].replace(/[,.]$/, "").trim() : text.split(" ")[0];
  return { destination, days, budget, extra: text };
}

function looksLikeNewTrip(text) {
  return /(\d+)\s*day/i.test(text) || /\$\s*\d+|\d+\s*(?:\$|usd|dollars?)/i.test(text);
}

export default function ChatPage() {
  const [dark, setDark] = useState(() => localStorage.getItem("theme") === "dark");
  const [input, setInput] = useState("");
  const [chatLog, setChatLog] = useState([]);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);
  const lastAssistantRef = useRef(null);
  const { setGlobalCity, setCurrentTrip, pendingRefinement, setPendingRefinement } = useGlobalState();

  const { messages, streaming, sessionId, startPlan, refinePlan, cancel } = usePlanStream();

  const progressSteps = messages.filter((m) => m.role === "progress");
  const latestAssistant = useMemo(() => messages.find((m) => m.role === "assistant"), [messages]);
  
  const lastCompletedAssistant = useMemo(() => [...chatLog].reverse().find(m => m.type === "assistant"), [chatLog]);
  const latestItinerary = latestAssistant?.itinerary || lastCompletedAssistant?.data?.itinerary || null;
  
  const canRefine = Boolean(sessionId && latestItinerary && !streaming);

  useEffect(() => {
    if (!streaming && messages.length > 0) {
      const done = messages.find((m) => m.role === "assistant");
      const err = messages.find((m) => m.role === "error");
      if (done) {
        lastAssistantRef.current = done;
        setGlobalCity(done.destination || "");
        setCurrentTrip({ sessionId, ...done });
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setChatLog((prev) => {
          const last = prev[prev.length - 1];
          if (last?.type === "assistant" && JSON.stringify(last.itinerary) === JSON.stringify(done.itinerary)) return prev;
          return [...prev, { type: "assistant", ...done }];
        });
      } else if (err) {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setChatLog((prev) => {
          const last = prev[prev.length - 1];
          if (last?.type === "error" && last.text === err.text) return prev;
          return [...prev, { type: "error", text: err.text }];
        });
      }
    }
  }, [streaming, messages, sessionId, setGlobalCity, setCurrentTrip]);

  const handleRefine = useCallback(
    (instruction) => {
      if (!canRefine) return;
      setChatLog((prev) => [...prev, { type: "user", text: instruction }]);
      refinePlan(instruction);
    },
    [canRefine, refinePlan]
  );

  useEffect(() => {
    if (pendingRefinement && canRefine) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      handleRefine(pendingRefinement);
      setPendingRefinement(null);
    }
  }, [pendingRefinement, canRefine, handleRefine, setPendingRefinement]);

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
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [cancel]);

  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text || streaming) return;
    setChatLog((prev) => [...prev, { type: "user", text }]);
    setInput("");

    if (canRefine && !looksLikeNewTrip(text)) {
      refinePlan(text);
      return;
    }

    const { destination, days, budget, extra } = parseInput(text);
    startPlan(destination, days, budget, extra);
  }, [input, streaming, canRefine, refinePlan, startPlan]);

  const handleExport = useCallback(async (fmt) => {
    if (!sessionId) return;
    try {
      const res = await fetch(`http://localhost:8001/export?session_id=${sessionId}&fmt=${fmt}`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Export failed" }));
        setChatLog((prev) => [...prev, { type: "error", text: err.detail || "Export failed" }]);
        return;
      }
      const blob = await res.blob();
      if (fmt === "pdf" && !blob.type.includes("pdf")) {
        setChatLog((prev) => [...prev, { type: "error", text: "PDF generation failed on the server." }]);
        return;
      }
      const url = URL.createObjectURL(blob);
      const ext = fmt === "markdown" ? "md" : fmt;
      Object.assign(document.createElement("a"), { href: url, download: `itinerary.${ext}` }).click();
      URL.revokeObjectURL(url);
    } catch {
      setChatLog((prev) => [...prev, { type: "error", text: "Export failed. Is the backend running?" }]);
    }
  }, [sessionId]);

  return (
    <div className="chat-page">
      <header className="chat-header">
        <div className="chat-header__brand"><Plane size={18} /> AI Travel Planner</div>
        <div className="chat-header__actions">
          {sessionId && (
            <div className="export-group">
              <button className="icon-btn" type="button" onClick={() => handleExport("json")} title="Download JSON"><Download size={14} /> JSON</button>
              <button className="icon-btn" type="button" onClick={() => handleExport("markdown")} title="Download Markdown"><Download size={14} /> MD</button>
              <button className="icon-btn" type="button" onClick={() => handleExport("pdf")} title="Download PDF"><Download size={14} /> PDF</button>
            </div>
          )}
          <button className="icon-btn icon-btn--round" type="button" onClick={() => setDark((d) => !d)} title="Toggle theme">
            {dark ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>
      </header>

      <main className="chat-messages">
        {chatLog.length === 0 && !streaming && (
          <div className="chat-empty">
            <div className="chat-empty__icon"><Landmark size={42} /></div>
            <h2>Plan your trip from one message</h2>
            <p>Try a destination, duration, and budget. I will build days, flights, hotels, weather, map pins, budget, and export files.</p>
            <div className="chat-empty__examples">
              {["Mumbai 5 days $2000", "Tokyo 7 days $3000", "Bali 10 days $1500"].map((ex) => (
                <button key={ex} type="button" className="example-chip" onClick={() => { setInput(ex); inputRef.current?.focus(); }}>
                  {ex}
                </button>
              ))}
            </div>
            <p className="chat-empty__shortcuts">
              <kbd>Enter</kbd> send - <kbd>Shift+Enter</kbd> newline - <kbd>Ctrl+K</kbd> focus - <kbd>Esc</kbd> cancel
            </p>
          </div>
        )}

        <div className="chat-history">
          <AnimatePresence>
            {chatLog.map((entry, i) => {
              if (entry.type === "user") {
                return (
                  <motion.div 
                    key={i} 
                    className="bubble bubble--user"
                    initial={{ opacity: 0, y: 15, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    transition={{ duration: 0.3 }}
                  >
                    {entry.text}
                  </motion.div>
                );
              }
              if (entry.type === "error") {
                return (
                  <motion.div 
                    key={i} 
                    className="bubble bubble--error"
                    initial={{ opacity: 0, y: 15, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    transition={{ duration: 0.3 }}
                  >
                    <AlertTriangle size={16} /> {entry.text}
                  </motion.div>
                );
              }
              if (entry.type === "assistant") {
                return (
                  <motion.div 
                    key={i} 
                    initial={{ opacity: 0, scale: 0.98, y: 10 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    transition={{ duration: 0.4 }}
                  >
                    <AssistantBubble msg={entry} onExport={handleExport} />
                  </motion.div>
                );
              }
              return null;
            })}
          </AnimatePresence>

          {streaming && (
            <motion.div 
              className="bubble bubble--assistant"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              <StreamingBubble steps={progressSteps} />
            </motion.div>
          )}
          <div ref={bottomRef} />
        </div>
      </main>

      <footer className="chat-input-bar">
        <div className="chat-input-area">
          <AnimatePresence>
            {canRefine && (
              <motion.div 
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
              >
                <RefinementChips onChip={handleRefine} />
              </motion.div>
            )}
          </AnimatePresence>
          <div className="input-shell">
            <textarea
              ref={inputRef}
          className="chat-input"
          rows={1}
          placeholder={canRefine ? "Ask for a refinement, or enter a new trip..." : "Where do you want to go?"}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          disabled={streaming}
        />
        {streaming ? (
          <button className="send-btn send-btn--cancel" type="button" onClick={cancel} title="Cancel"><Square size={18} /></button>
        ) : (
          <button className="send-btn" type="button" onClick={handleSend} disabled={!input.trim()} title="Send"><Send size={18} /></button>
        )}
          </div>
        </div>
      </footer>
    </div>
  );
}
