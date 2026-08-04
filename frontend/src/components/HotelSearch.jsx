import { useState, useEffect, useCallback } from "react";
import {
  ArrowRight,
  BedDouble,
  CalendarDays,
  Check,
  DollarSign,
  Leaf,
  MapPin,
  Search,
  Users,
  Wifi,
} from "lucide-react";
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
  SearchSelect,
  Shimmer,
  initials,
} from "./shared/TravelUI";
import { HotelCard } from "./shared/HotelCard";

const API_BASE = "http://localhost:8001";

function nightsBetween(a, b) {
  return Math.max(1, Math.round((new Date(b) - new Date(a)) / 86_400_000));
}

export default function HotelSearch() {
  const { globalCity, setPendingRefinement } = useGlobalState();
  const [localCity, setLocalCity] = useState(globalCity || "Paris");
  const navigate = useNavigate();
  const [checkIn, setCheckIn] = useState("2026-08-08");
  const [checkOut, setCheckOut] = useState("2026-08-13");
  const [adults, setAdults] = useState(2);
  
  const [hotels, setHotels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const [selected, setSelected] = useState(null);
  const [sort, setSort] = useState("rating");
  const [minStars, setMinStars] = useState(null);
  const [ecoOnly, setEcoOnly] = useState(false);
  
  const [lastCity, setLastCity] = useState("");

  const nights = nightsBetween(checkIn, checkOut);

  const doSearch = useCallback(async () => {
    if (!localCity.trim()) {
      setHotels([]);
      setLastCity("");
      return;
    }
    setLoading(true);
    setError(null);
    setLastCity(localCity);
    setSelected(null);

    try {
      const qs = new URLSearchParams({
        city: localCity,
        check_in: checkIn,
        check_out: checkOut,
        adults: adults.toString(),
      });

      const res = await fetch(`${API_BASE}/api/hotels?${qs}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setHotels(data.results || []);
    } catch {
      setError("Could not load live hotels. Check the backend and SERPER_API_KEY.");
      setHotels([]);
    } finally {
      setLoading(false);
    }
  }, [localCity, checkIn, checkOut, adults, nights]);

  useEffect(() => {
    const delay = setTimeout(() => {
      doSearch();
    }, 500); // 500ms debounce
    return () => clearTimeout(delay);
  }, [localCity, checkIn, checkOut, adults, doSearch]);

  const filtered = hotels
    .filter((h) => !minStars || (h.star_rating ?? 0) >= minStars)
    .filter((h) => !ecoOnly || h.eco_certified)
    .sort((a, b) =>
      sort === "price"
        ? a.price_per_night_usd - b.price_per_night_usd
        : (b.review_score ?? 0) - (a.review_score ?? 0)
    );

  const selectedHotel = hotels.find((h) => h.id === selected);

  return (
    <div className="planner-page">
      <PageHeader
        eyebrow="Where to stay"
        title={lastCity ? `Hotels in ${lastCity}` : "Hotels"}
        subtitle={`${nights} night${nights !== 1 ? "s" : ""} from ${checkIn} to ${checkOut}`}
        meta={`${filtered.length} option${filtered.length !== 1 ? "s" : ""}`}
      />

      <SearchPanel columns="1fr 1fr 1fr 1fr 1fr">
        <SearchInput type="text" label="City" icon={MapPin} value={localCity} onChange={(e) => setLocalCity(e.target.value)} />
        <SearchInput type="date" label="Check-in" icon={CalendarDays} value={checkIn} onChange={(e) => setCheckIn(e.target.value)} />
        <SearchInput type="date" label="Check-out" icon={CalendarDays} value={checkOut} onChange={(e) => setCheckOut(e.target.value)} />
        <SearchSelect label="Guests" icon={Users} value={adults} onChange={(e) => setAdults(Number(e.target.value))}>
          {[1, 2, 3, 4, 5, 6].map((n) => (
            <option key={n} value={n}>
              {n} Adult{n > 1 ? "s" : ""}
            </option>
          ))}
        </SearchSelect>
        <SearchButton loading={loading} onClick={doSearch} icon={Search}>
          Search
        </SearchButton>
      </SearchPanel>

      <ErrorBanner msg={error} />

      <div className="filter-row">
        <div className="chip-group">
          <span className="filter-label">Filters</span>
          <Pill label="Best rated" active={sort === "rating"} onClick={() => setSort("rating")} />
          <Pill label="Lowest price" active={sort === "price"} onClick={() => setSort("price")} />
          <Pill label="5 star" active={minStars === 5} onClick={() => setMinStars(minStars === 5 ? null : 5)} />
          <Pill label="4+ star" active={minStars === 4} onClick={() => setMinStars(minStars === 4 ? null : 4)} />
          <Pill label="Eco" active={ecoOnly} onClick={() => setEcoOnly((v) => !v)} />
        </div>
      </div>

      {loading ? (
        <Shimmer label={localCity ? `Finding rooms in ${localCity}` : "Finding rooms"} />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={BedDouble}
          title="No hotels match these filters."
          hint="Try increasing your max price or lowering the star rating."
          onClear={() => {
            setSort("rating");
            setMinStars(null);
            setEcoOnly(false);
          }}
        />
      ) : (
        <div className="results-grid">
          {filtered.map((h, i) => (
            <HotelCard key={h.id} hotel={h} index={i} selected={selected} onSelect={setSelected} />
          ))}
        </div>
      )}
      
      {selectedHotel && (
        <div className="selected-bar">
          <div>
            <strong>{selectedHotel.name}</strong>
            <div className="result-count">
              {selectedHotel.total_price_usd ? `$${selectedHotel.total_price_usd.toLocaleString()} total` : "Live listing selected"} for {nights} night{nights !== 1 ? "s" : ""}
            </div>
          </div>
          <button 
            type="button" 
            className="secondary-button"
            onClick={() => {
              setPendingRefinement(`Change hotel to ${selectedHotel.name}`);
              navigate("/chat");
            }}
          >
            <DollarSign size={17} />
            Add to itinerary
            <ArrowRight size={17} />
          </button>
        </div>
      )}
    </div>
  );
}
