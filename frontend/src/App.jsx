import { useState } from "react";
import {
  BedDouble,
  CloudSun,
  Compass,
  Map,
  Plane,
  ReceiptText,
  Sparkles,
  Utensils,
  WalletCards,
} from "lucide-react";
import HotelSearch from "./components/HotelSearch";
import AttractionSearch from "./components/AttractionSearch";
import RestaurantSearch from "./components/RestaurantSearch";
import WeatherSearch from "./components/WeatherSearch";
import BudgetTracker from "./components/BudgetTracker";

const TABS = [
  { id: "hotels", label: "Hotels", Icon: BedDouble, Component: HotelSearch },
  { id: "attractions", label: "Attractions", Icon: Compass, Component: AttractionSearch },
  { id: "restaurants", label: "Restaurants", Icon: Utensils, Component: RestaurantSearch },
  { id: "weather", label: "Weather", Icon: CloudSun, Component: WeatherSearch },
  { id: "budget", label: "Budget", Icon: WalletCards, Component: BudgetTracker },
];

export default function App() {
  const [active, setActive] = useState("hotels");
  const ActiveComponent = TABS.find((t) => t.id === active)?.Component || HotelSearch;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar__inner">
          <div className="brand">
            <div className="brand__mark" aria-hidden="true">
              <Plane size={21} />
            </div>
            <div>
              <div className="brand__title">AI Travel Planner</div>
              <div className="brand__subtitle">Curated trip intelligence</div>
            </div>
          </div>

          <div className="trip-summary" aria-label="Current trip summary">
            <span><Map size={16} /> Paris</span>
            <span><ReceiptText size={16} /> 5 nights</span>
            <span><Sparkles size={16} /> 2 guests</span>
          </div>
        </div>
      </header>

      <main className="app-main">
        <section className="hero-panel">
          <div className="hero-panel__content">
            <span className="eyebrow">Travel command center</span>
            <h1>Plan a polished trip from stay to spend.</h1>
            <p>
              Explore hotels, attractions, restaurants, weather, and budget insights in one focused planning workspace.
            </p>
          </div>
          <div className="hero-card" aria-label="Featured trip details">
            <span className="hero-card__label">Current search</span>
            <strong>Paris getaway</strong>
            <span>Dec 10 - Dec 15</span>
            <div className="hero-card__meta">
              <span>5 nights</span>
              <span>2 guests</span>
            </div>
          </div>
        </section>

        <nav className="tabbar" aria-label="Travel planner sections">
          {TABS.map(({ id, label, Icon }) => (
            <button
              key={id}
              type="button"
              className={`tabbar__button${active === id ? " is-active" : ""}`}
              onClick={() => setActive(id)}
            >
              <Icon size={18} />
              <span>{label}</span>
            </button>
          ))}
        </nav>

        <section className="workspace-panel">
          <ActiveComponent />
        </section>
      </main>
    </div>
  );
}
