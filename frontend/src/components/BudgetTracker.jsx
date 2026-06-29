import { useState, useEffect, useCallback } from "react";
import { ChartPie, CircleDollarSign, Landmark, Plus, ReceiptText, RotateCcw, WalletCards } from "lucide-react";
import {
  ErrorBanner,
  MetricCard,
  PageHeader,
  SearchInput,
  SearchSelect,
} from "./shared/TravelUI";

const API_BASE = "http://localhost:8000";

const CATEGORIES = ["accommodation", "food", "attractions", "transport", "shopping", "misc"];

function money(n) {
  if (n == null) return "USD --";
  return "USD " + Math.round(n).toLocaleString();
}

function CategoryBar({ category, amount, maxAmount }) {
  const pct = maxAmount ? Math.max(4, Math.round((amount / maxAmount) * 100)) : 0;
  return (
    <div className="category-row">
      <div className="category-row__head">
        <span>{category}</span>
        <strong>{money(amount)}</strong>
      </div>
      <div className="bar-track">
        <div className="bar-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export default function BudgetTracker() {
  const [tripId, setTripId] = useState("demo-trip");
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);
  const [budgetInput, setBudgetInput] = useState("");
  const [expCategory, setExpCategory] = useState(CATEGORIES[0]);
  const [expAmount, setExpAmount] = useState("");
  const [expDesc, setExpDesc] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/trip/budget/${encodeURIComponent(tripId)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setSummary(data);
      setError(null);
    } catch {
      setError("Could not reach the server. Check the backend is running.");
    }
  }, [tripId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
  }, [refresh]);

  async function postAction(payload) {
    setBusy(true);
    try {
      const res = await fetch(`${API_BASE}/api/trip/budget`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ trip_id: tripId, ...payload }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      await refresh();
    } catch (e) {
      setError(e.message || "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  function handleSetBudget() {
    const val = parseFloat(budgetInput);
    if (isNaN(val) || val <= 0) return setError("Enter a budget amount greater than 0.");
    postAction({ action: "set_budget", total_budget: val });
    setBudgetInput("");
  }

  function handleAddExpense() {
    const val = parseFloat(expAmount);
    if (isNaN(val) || val <= 0) return setError("Enter an expense amount greater than 0.");
    postAction({ action: "add_expense", category: expCategory, amount: val, description: expDesc });
    setExpAmount("");
    setExpDesc("");
  }

  function handleReset() {
    postAction({ action: "reset" });
  }

  const spent = summary?.spent_total || 0;
  const total = summary?.total_budget;
  const remaining = summary?.remaining;
  const byCategory = summary?.by_category || {};
  const maxCategoryAmount = Math.max(1, ...Object.values(byCategory));
  const pctSpent = total ? Math.min(100, Math.round((spent / total) * 100)) : 0;
  const overBudget = total != null && spent > total;

  return (
    <div className="planner-page">
      <PageHeader
        eyebrow="Spending"
        title="Trip budget"
        subtitle="Track total budget, remaining balance, category spend, and new expenses."
        meta={total != null ? `${pctSpent}% used` : "No budget set"}
      />

      <div className="content-card">
        <SearchInput label="Trip ID" icon={Landmark} value={tripId} onChange={(e) => setTripId(e.target.value)} placeholder="e.g. paris-dec-2025" />
      </div>

      <ErrorBanner msg={error} />

      <div className="metric-grid">
        <MetricCard label="Total budget" value={total != null ? money(total) : "GBP --"} icon={WalletCards} />
        <MetricCard label="Spent" value={money(spent)} icon={ReceiptText} />
        <MetricCard label="Remaining" value={remaining != null ? money(remaining) : "GBP --"} icon={CircleDollarSign} />
        <MetricCard label="Budget usage" value={`${pctSpent}%`} icon={ChartPie} />
      </div>

      <div className="content-card">
        <div className="card-title-row">
          <div>
            <h3 className="card-title">Budget usage</h3>
            <p className="result-count" style={{ marginTop: 5 }}>
              {total == null
                ? "Set a total budget below to start tracking."
                : overBudget
                  ? `${money(spent - total)} over budget`
                  : `${money(remaining)} remaining`}
            </p>
          </div>
          <strong>{money(spent)}</strong>
        </div>
        <div className="progress-track" style={{ marginTop: 16 }}>
          <div className="progress-fill" style={{ width: `${pctSpent}%`, background: overBudget ? "var(--color-danger)" : undefined }} />
        </div>

        <div className="budget-actions">
          <SearchInput
            label="Set total budget"
            icon={WalletCards}
            type="number"
            value={budgetInput}
            onChange={(e) => setBudgetInput(e.target.value)}
            placeholder="e.g. 1500"
          />
          <button type="button" onClick={handleSetBudget} disabled={busy} className="primary-button">
            Set Budget
          </button>
        </div>
      </div>

      <div className="content-card">
        <h3 className="card-title" style={{ marginBottom: 14 }}>Add an expense</h3>
        <div className="expense-grid">
          <SearchSelect label="Category" icon={ChartPie} value={expCategory} onChange={(e) => setExpCategory(e.target.value)}>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </SearchSelect>
          <SearchInput label="Amount" icon={CircleDollarSign} type="number" value={expAmount} onChange={(e) => setExpAmount(e.target.value)} placeholder="35" />
          <SearchInput label="Description" icon={ReceiptText} value={expDesc} onChange={(e) => setExpDesc(e.target.value)} placeholder="Optional" />
          <button type="button" onClick={handleAddExpense} disabled={busy} className="primary-button">
            <Plus size={18} />
            Add
          </button>
        </div>
      </div>

      {Object.keys(byCategory).length > 0 && (
        <div className="content-card">
          <h3 className="card-title" style={{ marginBottom: 16 }}>Expense breakdown</h3>
          {Object.entries(byCategory)
            .sort((a, b) => b[1] - a[1])
            .map(([cat, amt]) => (
              <CategoryBar key={cat} category={cat} amount={amt} maxAmount={maxCategoryAmount} />
            ))}
        </div>
      )}

      <button type="button" onClick={handleReset} disabled={busy} className="ghost-button">
        <RotateCcw size={16} />
        Reset this trip's budget
      </button>
    </div>
  );
}
