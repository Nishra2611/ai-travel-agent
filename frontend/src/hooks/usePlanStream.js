import { useCallback, useRef, useState } from "react";

const WS_URL = "ws://localhost:8000/ws/plan";

export function usePlanStream() {
  const [messages, setMessages] = useState([]);
  const [streaming, setStreaming] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const wsRef = useRef(null);

  const addMsg = useCallback((msg) => setMessages((prev) => [...prev, msg]), []);

  const openPlanSocket = useCallback(
    (payload, fallbackDestination = "") => {
      if (wsRef.current) wsRef.current.close();
      setMessages([]);
      setStreaming(true);
      if (!payload.session_id) setSessionId(null);

      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => ws.send(JSON.stringify(payload));

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
            destination: data.destination || fallbackDestination,
            flights: data.flights || [],
            hotels: data.hotels || [],
            weather: data.weather || [],
            budget: data.budget || {},
            fullOutput: data.full_output || null,
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

  const startPlan = useCallback(
    (destination, days, budget, extra = "") => {
      openPlanSocket({ destination, days, budget, extra }, destination);
    },
    [openPlanSocket]
  );

  const refinePlan = useCallback(
    (instruction) => {
      if (!sessionId) return;
      openPlanSocket({ session_id: sessionId, instruction, refine: true }, "");
    },
    [openPlanSocket, sessionId]
  );

  const cancel = useCallback(() => {
    wsRef.current?.close();
    setStreaming(false);
  }, []);

  return { messages, streaming, sessionId, startPlan, refinePlan, cancel, addMsg };
}
