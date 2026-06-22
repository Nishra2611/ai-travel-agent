import { useState, useEffect, useCallback } from "react";
import { MapPin, Search, Utensils } from "lucide-react";
import {
  EmptyState,
  ErrorBanner,
  PageHeader,
  PALETTES,
  Pill,
  Rating,
  SearchButton,
  SearchInput,
  SearchPanel,
  Shimmer,
  Tag,
  initials,
} from "./shared/TravelUI";

const API_BASE = "http://localhost:8000";
const BUDGET_TIERS = ["$", "$$", "$$$", "$$$$"];

function priceTag(level) {
  if (level == null) return null;
  return "$".repeat(level + 1);
}

function buildMockRestaurants(city) {
  const names = ["Trattoria Bella", "The Garden Table", "Spice Route", "Riverside Bistro", "Corner Bakehouse"];
  return names.map((n, i) => ({
    name: `${n}`,
    rating: parseFloat((4.8 - i * 0.12).toFixed(1)),
    price_level: i % 4,
    address: `${i + 12} Market Street, ${city}`,
    types: ["restaurant"],
  }));
}

function RestaurantCard({ restaurant, index, cuisine }) {
  const gradient = PALETTES[index % PALETTES.length];
  const tier = priceTag(restaurant.price_level);

  return (
    <article className="result-card">
      <div className="card-image" style={{ background: `linear-gradient(180deg, rgba(15,23,42,.04), rgba(15,23,42,.62)), ${gradient}` }}>
        <div className="card-image__initials">{initials(restaurant.name)}</div>
      </div>
      <div className="card-body">
        <div className="card-title-row">
          <div>
            <h3 className="card-title">{restaurant.name}</h3>
            <Rating score={restaurant.rating} />
          </div>
          {tier && <Tag color="amber">{tier}</Tag>}
        </div>

        <div className="tag-row">
          <span className="badge">
            <Utensils size={13} />
            {cuisine || "Local cuisine"}
          </span>
        </div>

        {restaurant.address && (
          <div className="icon-line">
            <MapPin size={16} />
            <span>{restaurant.address}</span>
          </div>
        )}
      </div>
    </article>
  );
}

export default function RestaurantSearch() {
  const [city, setCity] = useState("London");
  const [cuisine, setCuisine] = useState("");
  const [restaurants, setRestaurants] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [budget, setBudget] = useState(null);
  const [minRating, setMinRating] = useState(0);
  const [lastCity, setLastCity] = useState("London");

  const doSearch = useCallback(async () => {
    setLoading(true);
    setError(null);
    setLastCity(city);

    try {
      const qs = new URLSearchParams({ city, limit: 12, min_rating: minRating });
      if (cuisine) qs.set("cuisine", cuisine);
      if (budget) qs.set("budget", budget);
      const res = await fetch(`${API_BASE}/api/trip/restaurants?${qs}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setRestaurants(Array.isArray(data) ? data : []);
    } catch {
      setError("Could not reach the server. Showing sample results.");
      setRestaurants(buildMockRestaurants(city));
    } finally {
      setLoading(false);
    }
  }, [city, cuisine, budget, minRating]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    doSearch();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="planner-page">
      <PageHeader
        eyebrow="Where to eat"
        title={`Restaurants in ${lastCity}`}
        subtitle="Compare cuisines, ratings, price tiers, and addresses for your itinerary."
        meta={`${restaurants.length} place${restaurants.length !== 1 ? "s" : ""}`}
      />

      <SearchPanel columns="2fr 1.4fr 1fr">
        <SearchInput label="City" icon={MapPin} value={city} onChange={(e) => setCity(e.target.value)} placeholder="e.g. London" />
        <SearchInput label="Cuisine" icon={Utensils} value={cuisine} onChange={(e) => setCuisine(e.target.value)} placeholder="Optional" />
        <SearchButton loading={loading} onClick={doSearch} icon={Search}>
          Search
        </SearchButton>
      </SearchPanel>

      <ErrorBanner msg={error} />

      <div className="filter-row">
        <div className="chip-group">
          <span className="filter-label">Budget</span>
          {BUDGET_TIERS.map((b) => (
            <Pill key={b} label={b} active={budget === b} onClick={() => { setBudget(budget === b ? null : b); doSearch(); }} />
          ))}
          <span className="filter-label">Rating</span>
          {[0, 4, 4.5].map((r) => (
            <Pill key={r} label={r === 0 ? "Any" : `${r}+`} active={minRating === r} onClick={() => { setMinRating(r); doSearch(); }} />
          ))}
        </div>
      </div>

      {loading ? (
        <Shimmer label={`Finding tables in ${city}`} />
      ) : restaurants.length === 0 ? (
        <EmptyState
          icon={Utensils}
          title="No restaurants match these filters."
          hint="Reset budget and rating filters to see more options."
          onClear={() => {
            setBudget(null);
            setMinRating(0);
            doSearch();
          }}
        />
      ) : (
        <div className="results-grid">
          {restaurants.map((r, i) => (
            <RestaurantCard key={`${r.name}-${i}`} restaurant={r} index={i} cuisine={cuisine} />
          ))}
        </div>
      )}
    </div>
  );
}
