import { useState } from "react";

const API_BASE = "http://localhost:8000";

export default function BudgetTracker() {
  const [tripId, setTripId] = useState("trip1");
  const [budget, setBudget] = useState("");
  const [result, setResult] = useState(null);

  async function setBudgetAmount() {
    const res = await fetch(
      `${API_BASE}/api/trip/budget`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          trip_id: tripId,
          action: "set_budget",
          total_budget: Number(budget),
        }),
      }
    );

    const data = await res.json();
    setResult(data);
  }

  return (
    <div
      style={{
        maxWidth: "680px",
        margin: "20px auto",
        padding: "20px",
        border: "1px solid #ddd",
        borderRadius: "10px",
      }}
    >
      <h2>Budget Tracker</h2>

      <input
        value={tripId}
        onChange={(e) => setTripId(e.target.value)}
        placeholder="Trip ID"
      />

      <input
        type="number"
        value={budget}
        onChange={(e) => setBudget(e.target.value)}
        placeholder="Budget"
        style={{ marginLeft: "10px" }}
      />

      <button
        onClick={setBudgetAmount}
        style={{ marginLeft: "10px" }}
      >
        Save Budget
      </button>

      {result && (
        <pre>{JSON.stringify(result, null, 2)}</pre>
      )}
    </div>
  );
}