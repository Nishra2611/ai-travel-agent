import { useState, useEffect, useCallback } from "react";
import { MapPin, Search, Utensils } from "lucide-react";
import { useGlobalState } from "../context/GlobalState";
import { useNavigate } from "react-router-dom";
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

function RestaurantCard({ restaurant, index, cuisine, onAdd }) {
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

        <div className="card-actions" style={{ marginTop: 16, justifyContent: "flex-end", gap: 10 }}>
          <button 
            type="button" 
            className="secondary-button"
            onClick={() => onAdd(restaurant.name)}
          >
            Add to Trip
          </button>
        </div>
      </div>
    </article>
  );
}

export default function RestaurantSearch() {
  const { globalCity, setPendingRefinement } = useGlobalState();
  const [localCity, setLocalCity] = useState(globalCity || "Paris");
  const navigate = useNavigate();
  const [cuisine, setCuisine] = useState("");
  const [restaurants, setRestaurants] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [budget, setBudget] = useState(null);
  const [minRating, setMinRating] = useState(0);
  const [lastCity, setLastCity] = useState("");

  const doSearch = useCallback(async () => {
    if (!localCity.trim()) {
      setRestaurants([]);
      setLastCity("");
      return;
    }
    setLoading(true);
    setError(null);
    setLastCity(localCity);

    try {
      const qs = new URLSearchParams({ city: localCity, limit: 12, min_rating: minRating });
      if (cuisine) qs.set("cuisine", cuisine);
      if (budget) qs.set("budget", budget);
      const res = await fetch(`${API_BASE}/api/trip/restaurants?${qs}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setRestaurants(Array.isArray(data) ? data : []);
    } catch {
      setError("Could not load live restaurants. Check the backend and SERPER_API_KEY.");
      setRestaurants([]);
    } finally {
      setLoading(false);
    }
  }, [localCity, cuisine, budget, minRating]);

  useEffect(() => {
    const delay = setTimeout(() => {
      doSearch();
    }, 500); // 500ms debounce
    return () => clearTimeout(delay);
  }, [localCity, cuisine, budget, minRating, doSearch]);

  return (
    <div className="planner-page">
      <PageHeader
        eyebrow="Where to eat"
        title={lastCity ? `Restaurants in ${lastCity}` : "Restaurants"}
        subtitle="Compare cuisines, ratings, price tiers, and addresses for your itinerary."
        meta={`${restaurants.length} place${restaurants.length !== 1 ? "s" : ""}`}
      />

      <SearchPanel columns="1fr 1fr 1fr">
        <SearchInput type="text" label="City" icon={MapPin} value={localCity} onChange={(e) => setLocalCity(e.target.value)} />
        <SearchInput label="Cuisine (Optional)" icon={Utensils} value={cuisine} onChange={(e) => setCuisine(e.target.value)} placeholder="e.g. Italian, Sushi" />
        <SearchButton loading={loading} onClick={doSearch} icon={Search}>
          Search
        </SearchButton>
      </SearchPanel>

      <ErrorBanner msg={error} />

      <div className="filter-row">
        <div className="chip-group">
          <span className="filter-label">Budget</span>
          {BUDGET_TIERS.map((b) => (
            <Pill key={b} label={b} active={budget === b} onClick={() => { setBudget(budget === b ? null : b); }} />
          ))}
          <span className="filter-label">Rating</span>
          {[0, 4, 4.5].map((r) => (
            <Pill key={r} label={r === 0 ? "Any" : `${r}+`} active={minRating === r} onClick={() => { setMinRating(r); }} />
          ))}
        </div>
      </div>

      {loading ? (
        <Shimmer label={localCity ? `Finding tables in ${localCity}` : "Finding tables"} />
      ) : restaurants.length === 0 ? (
        <EmptyState
          icon={Utensils}
          title="No restaurants match these filters."
          hint="Reset budget and rating filters to see more options."
          onClear={() => {
            setBudget(null);
            setMinRating(0);
          }}
        />
      ) : (
        <div className="results-grid">
          {restaurants.map((r, i) => (
            <RestaurantCard 
              key={`${r.name}-${i}`} 
              restaurant={r} 
              index={i} 
              cuisine={cuisine} 
              onAdd={(name) => {
                setPendingRefinement(`Add restaurant ${name} to my itinerary`);
                navigate("/chat");
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
