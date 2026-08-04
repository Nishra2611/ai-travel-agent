import { useState, useEffect, useCallback } from "react";
import { Clock3, Compass, Globe2, Landmark, MapPin, Plus, Search } from "lucide-react";
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

const API_BASE = "http://localhost:8001";

const CATEGORY_LABELS = {
  attraction: "Attraction",
  museum: "Museum",
  gallery: "Gallery",
  zoo: "Zoo",
  theme_park: "Theme park",
  viewpoint: "Viewpoint",
  park: "Park",
  garden: "Garden",
};

function buildMockAttractions(city) {
  const names = ["Old Town Square", "Central Museum", "Riverside Park", "City Cathedral", "Grand Gallery"];
  const cats = ["attraction", "museum", "park", "attraction", "gallery"];
  return names.map((n, i) => ({
    name: `${n}, ${city}`,
    lat: 48.85 + i * 0.01,
    lng: 2.35 + i * 0.01,
    category: cats[i],
    hours: i % 2 === 0 ? "09:00-18:00" : null,
    rating: parseFloat((4.7 - i * 0.15).toFixed(1)),
  }));
}

function AttractionCard({ attraction, index }) {
  const gradient = PALETTES[index % PALETTES.length];
  const label = CATEGORY_LABELS[attraction.category] || "Place of interest";

  return (
    <article className="result-card">
      <div className="card-image" style={{ background: `linear-gradient(180deg, rgba(15,23,42,.04), rgba(15,23,42,.62)), ${gradient}` }}>
        <div className="card-image__initials">{initials(attraction.name)}</div>
      </div>
      <div className="card-body">
        <div className="card-title-row">
          <div>
            <h3 className="card-title">{attraction.name}</h3>
            <Rating score={attraction.rating} />
          </div>
          <Tag color="info">{label}</Tag>
        </div>

        <div className="icon-line">
          <Clock3 size={16} />
          <span>{attraction.hours ? `Open ${attraction.hours}` : "Hours not listed"}</span>
        </div>

        <div className="card-actions" style={{ marginTop: 16, justifyContent: "space-between", gap: 10 }}>
          <span className="badge">
            <Landmark size={13} />
            Recommended stop
          </span>
          <button 
            type="button" 
            className="secondary-button"
            onClick={() => onAdd && onAdd(attraction.name)}
          >
            <Plus size={17} />
            Add to Trip
          </button>
        </div>
      </div>
    </article>
  );
}

export default function AttractionSearch() {
  const { globalCity, setPendingRefinement } = useGlobalState();
  const navigate = useNavigate();
  const [localCity, setLocalCity] = useState(globalCity || "London");
  const [country, setCountry] = useState("");
  const [attractions, setAttractions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [category, setCategory] = useState(null);
  const [lastCity, setLastCity] = useState("");

  const doSearch = useCallback(async () => {
    if (!localCity.trim()) {
      setAttractions([]);
      setLastCity("");
      return;
    }
    setLoading(true);
    setError(null);
    setLastCity(localCity);

    try {
      const qs = new URLSearchParams({ city: localCity, limit: 12 });
      if (country) qs.set("country", country);
      const res = await fetch(`${API_BASE}/api/trip/attractions?${qs}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setAttractions(Array.isArray(data) ? data : []);
    } catch {
      setError("Could not reach the server. Showing sample results.");
      setAttractions([]);
    } finally {
      setLoading(false);
    }
  }, [localCity, country]);

  useEffect(() => {
    const delay = setTimeout(() => {
      doSearch();
    }, 500); // 500ms debounce
    return () => clearTimeout(delay);
  }, [localCity, country, doSearch]);

  const categories = [...new Set(attractions.map((a) => a.category).filter(Boolean))];
  const filtered = category ? attractions.filter((a) => a.category === category) : attractions;

  return (
    <div className="planner-page">
      <PageHeader
        eyebrow="Things to do"
        title={lastCity ? `Attractions in ${lastCity}` : "Attractions"}
        subtitle="Discover highly rated experiences, landmarks, museums, and local highlights."
        meta={`${filtered.length} place${filtered.length !== 1 ? "s" : ""}`}
      />

      <SearchPanel columns="1fr 1fr 1fr">
        <SearchInput type="text" label="City" icon={MapPin} value={localCity} onChange={(e) => setLocalCity(e.target.value)} />
        <SearchInput label="Country" icon={Globe2} value={country} onChange={(e) => setCountry(e.target.value)} placeholder="Optional" />
        <SearchButton loading={loading} onClick={doSearch} icon={Search}>
          Search
        </SearchButton>
      </SearchPanel>

      <ErrorBanner msg={error} />

      {categories.length > 0 && (
        <div className="filter-row">
          <div className="chip-group">
            <span className="filter-label">Category</span>
            <Pill label="All" active={!category} onClick={() => setCategory(null)} />
            {categories.map((c) => (
              <Pill
                key={c}
                label={CATEGORY_LABELS[c] || c}
                active={category === c}
                onClick={() => setCategory(category === c ? null : c)}
              />
            ))}
          </div>
        </div>
      )}

      {loading ? (
        <Shimmer label={localCity ? `Scanning ${localCity} for things to do` : "Scanning for things to do"} />
      ) : filtered.length === 0 ? (
        <EmptyState icon={Compass} title="No attractions match these filters." hint="Clear the category filter to widen your search." onClear={() => setCategory(null)} />
      ) : (
        <div className="results-grid">
          {filtered.map((a, i) => (
            <AttractionCard 
              key={`${a.name}-${i}`} 
              attraction={a} 
              index={i} 
              onAdd={(name) => {
                setPendingRefinement(`Add ${name} to my itinerary`);
                navigate("/chat");
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
