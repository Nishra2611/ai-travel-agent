import { useCallback, useRef, useState } from "react";

const WS_URL = "ws://localhost:8000/ws/plan";

export function usePlanStream() {
  const [messages, setMessages] = useState([]);
  const [streaming, setStreaming] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const wsRef = useRef(null);

  const addMsg = useCallback((msg) => setMessages((prev) => [...prev, msg]), []);

  const startPlan = useCallback(
    (destination, days, budget, extra = "") => {
      if (wsRef.current) wsRef.current.close();
      setMessages([]);
      setStreaming(true);
      setSessionId(null);

      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => ws.send(JSON.stringify({ destination, days, budget, extra }));

      ws.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.type === "session") {
          setSessionId(data.session_id);
        } else if (data.type === "progress") {
          addMsg({ role: "progress", text: data.message, node: data.node });
        } else if (data.type === "done") {
          setSessionId(data.session_id);
          addMsg({
            role: "assistant",
            itinerary: data.itinerary || {},
            destination: data.destination || destination,
            flights: data.flights || [],
            hotels: data.hotels || [],
            weather: data.weather || [],
            budget: data.budget || {},
          });
          setStreaming(false);
        } else if (data.type === "error") {
          addMsg({ role: "error", text: data.message });
          setStreaming(false);
        }
      };

      ws.onerror = () => {
        addMsg({ role: "error", text: "Connection error. Is the backend running?" });
        setStreaming(false);
      };

      ws.onclose = () => setStreaming(false);
    },
    [addMsg]
  );

  const cancel = useCallback(() => {
    wsRef.current?.close();
    setStreaming(false);
  }, []);

  return { messages, streaming, sessionId, startPlan, cancel, addMsg };
}
