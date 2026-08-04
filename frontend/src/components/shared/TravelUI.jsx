/* eslint-disable react-refresh/only-export-components */
import {
  AlertTriangle,
  ArrowRight,
  CalendarDays,
  CircleDollarSign,
  CloudSun,
  MapPin,
  Search,
  SlidersHorizontal,
  Sparkles,
  Star,
} from "lucide-react";

export const ACCENT = "#0f766e";

export const PALETTES = [
  "linear-gradient(135deg, #14b8a6, #60a5fa 48%, #f97316)",
  "linear-gradient(135deg, #0f766e, #22c55e 48%, #f59e0b)",
  "linear-gradient(135deg, #2563eb, #06b6d4 52%, #fb7185)",
  "linear-gradient(135deg, #7c3aed, #0ea5e9 48%, #f97316)",
  "linear-gradient(135deg, #334155, #14b8a6 52%, #facc15)",
];

export function initials(name) {
  return (name || "")
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase();
}

export function Pill({ label, active, onClick }) {
  return (
    <button type="button" onClick={onClick} className={`chip${active ? " is-active" : ""}`}>
      {label}
    </button>
  );
}

export function SearchInput({ label, icon: Icon = MapPin, ...props }) {
  return (
    <div className="field">
      <label>{label}</label>
      <div className="input-shell">
        <Icon size={18} />
        <input {...props} />
      </div>
    </div>
  );
}

export function SearchSelect({ label, icon: Icon = SlidersHorizontal, children, ...props }) {
  return (
    <div className="field">
      <label>{label}</label>
      <div className="input-shell">
        <Icon size={18} />
        <select {...props}>{children}</select>
      </div>
    </div>
  );
}

export function SearchButton({ loading, onClick, children = "Search", icon: Icon = Search }) {
  return (
    <button type="button" onClick={onClick} disabled={loading} className="primary-button">
      <Icon size={19} />
      {loading ? "Searching" : children}
    </button>
  );
}

export function SearchPanel({ children, columns }) {
  return (
    <div className="search-panel">
      <div className="search-grid" style={{ gridTemplateColumns: columns }}>
        {children}
      </div>
    </div>
  );
}

export function PageHeader({ eyebrow, title, subtitle, meta }) {
  return (
    <div className="page-header">
      <div>
        <span className="eyebrow" style={{ color: "var(--color-primary)" }}>
          {eyebrow}
        </span>
        <h2>{title}</h2>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {meta && <div className="result-count">{meta}</div>}
    </div>
  );
}

export function Shimmer({ label, count = 4 }) {
  return (
    <div>
      {label && <div className="result-count" style={{ marginBottom: 12 }}>{label}</div>}
      <div className="skeleton-list">
        {Array.from({ length: count }, (_, i) => (
          <div key={i} className="skeleton-card" />
        ))}
      </div>
    </div>
  );
}

export function ErrorBanner({ msg }) {
  if (!msg) return null;
  return (
    <div className="error-banner" role="alert">
      <AlertTriangle size={18} />
      <span>{msg}</span>
    </div>
  );
}

export function EmptyState({ title, hint, onClear, icon: Icon = Sparkles }) {
  return (
    <div className="empty-state">
      <div>
        <div className="empty-state__icon">
          <Icon size={24} />
        </div>
        <h3>{title}</h3>
        {hint && <p>{hint}</p>}
        {onClear && (
          <button type="button" onClick={onClear} className="secondary-button">
            Clear filters
            <ArrowRight size={17} />
          </button>
        )}
      </div>
    </div>
  );
}

export function MetricCard({ label, value, icon: Icon = CircleDollarSign }) {
  return (
    <div className="metric-card">
      <div className="metric-card__icon">
        <Icon size={20} />
      </div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function Rating({ score, count }) {
  if (score == null) return <span className="result-count">No rating yet</span>;
  return (
    <div className="rating-row">
      <span className="rating-pill">
        <Star size={13} fill="currentColor" />
        {score}
      </span>
      {count != null && <span>{count.toLocaleString()} reviews</span>}
    </div>
  );
}

export function Stars(props) {
  return <Rating {...props} />;
}

export function Tag({ children, color = "neutral" }) {
  return <span className={`tag tag--${color}`}>{children}</span>;
}

export function DateIcon() {
  return <CalendarDays size={18} />;
}

export function WeatherIcon() {
  return <CloudSun size={22} />;
}
