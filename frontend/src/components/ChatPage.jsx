import { useCallback, useEffect, useRef, useState } from "react";
import { Download, Moon, Send, Square, Sun, X } from "lucide-react";
import MessageBubble from "./chat/MessageBubble";
import ProgressSteps from "./chat/ProgressSteps";
import RefinementChips from "./chat/RefinementChips";
import TypingIndicator from "./chat/TypingIndicator";
import { usePlanStream } from "../hooks/usePlanStream";
import { exportItinerary, refineTrip } from "../services/api";

export default function ChatPage() {
  const [dark, setDark] = useState(() => localStorage.getItem("theme") === "dark");
  const [input, setInput] = useState("");
  const [userMsgs, setUserMsgs] = useState([]);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  const { messages, streaming, sessionId, startPlan, cancel, addMsg } = usePlanStream();

  // combine user messages + stream messages in order
  const allMessages = [...userMsgs, ...messages];
  const progressSteps = messages.filter((m) => m.role === "progress");
  const lastItinerary = [...messages].reverse().find((m) => m.itinerary)?.itinerary || null;

  // dark mode
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);

  // auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [allMessages, streaming]);

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
    // try to extract destination, days, budget from natural language
    const daysMatch = text.match(/(\d+)\s*day/i);
    const budgetMatch = text.match(/\$(\d+)/);
    const days = daysMatch ? parseInt(daysMatch[1]) : 5;
    const budget = budgetMatch ? parseInt(budgetMatch[1]) : 1500;
    // destination = first capitalized word sequence before numbers
    const destMatch = text.match(/^([A-Za-z\s]+?)(?:\s+\d|\s*$)/);
    const destination = destMatch ? destMatch[1].trim() : text.split(" ")[0];
    return { destination, days, budget, extra: text };
  };

  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text || streaming) return;
    setUserMsgs((prev) => [...prev, { role: "user", text }]);
    setInput("");
    const { destination, days, budget, extra } = parseInput(text);
    startPlan(destination, days, budget, extra);
  }, [input, streaming, startPlan]);

  const handleRefine = useCallback(
    async (instruction) => {
      if (!sessionId || streaming) return;
      setUserMsgs((prev) => [...prev, { role: "user", text: instruction }]);
      addMsg({ role: "progress", text: "Refining your itinerary...", node: "refine" });
      try {
        const job = await refineTrip(sessionId, instruction);
        addMsg({ role: "assistant", text: `Refinement started (job: ${job.job_id}). Poll /status/${job.job_id} for result.` });
      } catch {
        addMsg({ role: "error", text: "Refinement failed. Try again." });
      }
    },
    [sessionId, streaming, addMsg]
  );

  const handleExport = useCallback(
    async (fmt) => {
      if (!sessionId) return;
      try {
        if (fmt === "json") {
          const data = await exportItinerary(sessionId, "json");
          const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a"); a.href = url; a.download = "itinerary.json"; a.click();
        } else if (fmt === "markdown") {
          const blob = await exportItinerary(sessionId, "markdown");
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a"); a.href = url; a.download = "itinerary.md"; a.click();
        } else if (fmt === "pdf") {
          const blob = await exportItinerary(sessionId, "pdf");
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a"); a.href = url; a.download = "itinerary.pdf"; a.click();
        }
      } catch {
        addMsg({ role: "error", text: "Export failed." });
      }
    },
    [sessionId, addMsg]
  );

  return (
    <div className="chat-page">
      {/* header */}
      <header className="chat-header">
        <div className="chat-header__brand">✈ AI Travel Planner</div>
        <div className="chat-header__actions">
          {sessionId && (
            <div className="export-group">
              <button className="icon-btn" title="Download JSON" onClick={() => handleExport("json")}>
                <Download size={16} /> JSON
              </button>
              <button className="icon-btn" title="Download Markdown" onClick={() => handleExport("markdown")}>
                <Download size={16} /> MD
              </button>
              <button className="icon-btn" title="Download PDF" onClick={() => handleExport("pdf")}>
                <Download size={16} /> PDF
              </button>
            </div>
          )}
          <button className="icon-btn" onClick={() => setDark((d) => !d)} title="Toggle dark mode">
            {dark ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        </div>
      </header>

      {/* messages */}
      <main className="chat-messages">
        {allMessages.length === 0 && !streaming && (
          <div className="chat-empty">
            <p>✈ Ask me to plan a trip!</p>
            <p className="chat-empty__hint">e.g. "Paris 5 days $2000" or "Tokyo family trip 7 days $3000"</p>
            <p className="chat-empty__shortcuts">
              <kbd>Enter</kbd> send · <kbd>Shift+Enter</kbd> new line · <kbd>Ctrl+K</kbd> focus · <kbd>Esc</kbd> cancel
            </p>
          </div>
        )}

        {allMessages.map((msg, i) => (
          <MessageBubble key={i} msg={msg} />
        ))}

        {streaming && progressSteps.length > 0 && (
          <div className="bubble bubble--assistant">
            <ProgressSteps steps={progressSteps} streaming={streaming} />
            <TypingIndicator />
          </div>
        )}

        <div ref={bottomRef} />
      </main>

      {/* refinement chips — show after itinerary is ready */}
      {lastItinerary && !streaming && (
        <RefinementChips onChip={handleRefine} disabled={streaming} />
      )}

      {/* input bar */}
      <footer className="chat-input-bar">
        <textarea
          ref={inputRef}
          className="chat-input"
          rows={1}
          placeholder="Where do you want to go? (Enter to send, Shift+Enter for new line)"
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
          <button className="send-btn" onClick={handleSend} disabled={!input.trim()} title="Send (Enter)">
            <Send size={18} />
          </button>
        )}
      </footer>
    </div>
  );
}
