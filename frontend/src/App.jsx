import { BrowserRouter as Router, Navigate, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { BedDouble, CloudSun, Compass, Map, MessageCircle, Plane, ReceiptText, Sparkles, Utensils, WalletCards } from "lucide-react";
import ChatPage from "./components/ChatPage";
import HotelSearch from "./components/HotelSearch";
import AttractionSearch from "./components/AttractionSearch";
import RestaurantSearch from "./components/RestaurantSearch";
import WeatherSearch from "./components/WeatherSearch";
import BudgetTracker from "./components/BudgetTracker";
import { GlobalStateProvider, useGlobalState } from "./context/GlobalState";
import "./index.css";

const LINKS = [
  { to: "/chat", label: "Chat", icon: MessageCircle },
  { to: "/hotels", label: "Hotels", icon: BedDouble },
  { to: "/attractions", label: "Attractions", icon: Compass },
  { to: "/restaurants", label: "Restaurants", icon: Utensils },
  { to: "/weather", label: "Weather", icon: CloudSun },
  { to: "/budget", label: "Budget", icon: WalletCards },
];

function AppContent() {
  const { globalCity, setGlobalCity, currentTrip } = useGlobalState();
  const location = useLocation();
  const isChatPage = location.pathname === "/chat";

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
            <span><Map size={16} /> {currentTrip?.destination || globalCity || "Destination"}</span>
            {currentTrip?.days && <span><ReceiptText size={16} /> {currentTrip.days} days</span>}
            {currentTrip?.budget && <span><Sparkles size={16} /> ${currentTrip.budget}</span>}
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
            {!isChatPage ? (
              <input
                type="text"
                className="hero-card__input"
                placeholder="Where to?"
                value={globalCity}
                onChange={(e) => setGlobalCity(e.target.value)}
                style={{ padding: "0.5rem", borderRadius: "8px", border: "1px solid var(--color-border)", marginTop: "0.5rem", width: "100%" }}
              />
            ) : (
              <strong>{currentTrip?.destination || "New Trip"}</strong>
            )}
            <div className="hero-card__meta" style={{ marginTop: "1rem" }}>
              {currentTrip?.days && <span>{currentTrip.days} days</span>}
            </div>
          </div>
        </section>

        <nav className="tabbar" aria-label="Travel planner sections">
          {LINKS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => `tabbar__button${isActive ? " is-active" : ""}`}
            >
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <section className="workspace-panel">
          <Routes>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/hotels" element={<HotelSearch />} />
            <Route path="/attractions" element={<AttractionSearch />} />
            <Route path="/restaurants" element={<RestaurantSearch />} />
            <Route path="/weather" element={<WeatherSearch />} />
            <Route path="/budget" element={<BudgetTracker />} />
          </Routes>
        </section>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <GlobalStateProvider>
      <Router>
        <AppContent />
      </Router>
    </GlobalStateProvider>
  );
}
