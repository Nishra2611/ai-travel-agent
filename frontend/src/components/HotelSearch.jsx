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

const API_BASE = "http://localhost:8000";

const AMENITY_ICONS = {
  "Free Wi-Fi": Wifi,
  Pool: BedDouble,
  Spa: SparkleIcon,
  Gym: Check,
  Breakfast: Check,
  Bar: Check,
  Rooftop: Check,
  Concierge: Check,
  Garden: Leaf,
  Restaurant: Check,
  "Shared Kitchen": Check,
  "Historic Building": Check,
  Kitchenette: Check,
};

const DEST_HINTS = [
  "Where are you off to?",
  "Paris calling",
  "Tokyo dreams await",
  "Bali or bust",
  "Find your escape",
];

function SparkleIcon(props) {
  return <Check {...props} />;
}

function nightsBetween(a, b) {
  return Math.max(1, Math.round((new Date(b) - new Date(a)) / 86_400_000));
}

function buildMockHotels(city, nights) {
  return Array.from({ length: 8 }, (_, i) => ({
    id: `local-${i}`,
    name: `Sample Hotel ${i + 1} ${city}`,
    star_rating: 5 - Math.floor(i / 2),
    review_score: parseFloat((4.8 - i * 0.15).toFixed(1)),
    review_count: 1000 - i * 80,
    price_per_night_usd: 300 - i * 25,
    total_price_usd: (300 - i * 25) * nights,
    address: `${i + 1} Example Street, ${city}`,
    amenities: ["Free Wi-Fi", "Breakfast"].concat(i < 3 ? ["Pool", "Spa"] : []),
    eco_certified: i % 3 === 0,
    check_in_time: "3:00 PM",
    check_out_time: "12:00 PM",
    location: { latitude: 48.85 + i * 0.01, longitude: 2.35 + i * 0.01 },
  }));
}

function HotelCard({ hotel, index, selected, onSelect }) {
  const isSelected = selected === hotel.id;
  const gradient = PALETTES[index % PALETTES.length];

  return (
    <article
      className={`result-card hotel-card${isSelected ? " is-selected" : ""}`}
      onClick={() => onSelect(isSelected ? null : hotel.id)}
    >
      <div className="card-image" style={{ background: `linear-gradient(180deg, rgba(15,23,42,.04), rgba(15,23,42,.62)), ${gradient}` }}>
        <div className="card-image__initials">{initials(hotel.name)}</div>
      </div>

      <div className="card-body">
        <div className="card-title-row">
          <div>
            <h3 className="card-title">{hotel.name}</h3>
            <Rating score={hotel.review_score} count={hotel.review_count} />
          </div>
          <div className="price-block">
            <strong>${hotel.price_per_night_usd.toFixed(0)}</strong>
            <span>per night</span>
          </div>
        </div>

        <div className="icon-line">
          <MapPin size={16} />
          <span>{hotel.address}</span>
        </div>

        <div className="amenity-row">
          {hotel.eco_certified && (
            <span className="badge">
              <Leaf size={13} />
              Eco certified
            </span>
          )}
          {hotel.amenities.slice(0, 5).map((amenity) => {
            const Icon = AMENITY_ICONS[amenity] || Check;
            return (
              <span className="badge" key={amenity}>
                <Icon size={13} />
                {amenity}
              </span>
            );
          })}
          {hotel.amenities.length > 5 && <span className="badge">+{hotel.amenities.length - 5} more</span>}
        </div>

        <div className="expanded-details">
          <div className="mini-stat">
            <span>Total stay</span>
            <strong>${hotel.total_price_usd.toLocaleString()}</strong>
          </div>
          <div className="mini-stat">
            <span>Check-in</span>
            <strong>{hotel.check_in_time || "3:00 PM"}</strong>
          </div>
          <div className="mini-stat">
            <span>Check-out</span>
            <strong>{hotel.check_out_time || "12:00 PM"}</strong>
          </div>
        </div>
      </div>
    </article>
  );
}

export default function HotelSearch() {
  const [city, setCity] = useState("Paris");
  const [checkIn, setCheckIn] = useState("2025-12-10");
  const [checkOut, setCheckOut] = useState("2025-12-15");
  const [adults, setAdults] = useState(2);
  const [hotels, setHotels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);
  const [sort, setSort] = useState("rating");
  const [minStars, setMinStars] = useState(null);
  const [ecoOnly, setEcoOnly] = useState(false);
  const [lastQuery, setLastQuery] = useState({
    city: "Paris",
    checkIn: "2025-12-10",
    checkOut: "2025-12-15",
  });
  const [hintIdx, setHintIdx] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setHintIdx((i) => (i + 1) % DEST_HINTS.length), 2800);
    return () => clearInterval(t);
  }, []);

  const nights = nightsBetween(lastQuery.checkIn, lastQuery.checkOut);

  const doSearch = useCallback(async () => {
    setLoading(true);
    setError(null);
    setSelected(null);
    setLastQuery({ city, checkIn, checkOut });

    try {
      const qs = new URLSearchParams({ city, check_in: checkIn, check_out: checkOut, adults });
      const res = await fetch(`${API_BASE}/api/hotels?${qs}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setHotels(data.results ?? []);
    } catch {
      setError("Could not reach the server. Showing sample results.");
      setHotels(buildMockHotels(city, nights));
    } finally {
      setLoading(false);
    }
  }, [city, checkIn, checkOut, adults, nights]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    doSearch();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
        eyebrow="Places to stay"
        title={`Find your room in ${lastQuery.city}`}
        subtitle={`${nights} night${nights !== 1 ? "s" : ""} from ${lastQuery.checkIn} to ${lastQuery.checkOut}`}
        meta={`${filtered.length} place${filtered.length !== 1 ? "s" : ""}`}
      />

      <SearchPanel columns="2fr 1fr 1fr .8fr 1.1fr">
        <SearchInput
          label="Destination"
          icon={MapPin}
          value={city}
          onChange={(e) => setCity(e.target.value)}
          placeholder={DEST_HINTS[hintIdx]}
        />
        <SearchInput label="Check-in" icon={CalendarDays} type="date" value={checkIn} onChange={(e) => setCheckIn(e.target.value)} />
        <SearchInput label="Check-out" icon={CalendarDays} type="date" value={checkOut} onChange={(e) => setCheckOut(e.target.value)} />
        <SearchSelect label="Guests" icon={Users} value={adults} onChange={(e) => setAdults(Number(e.target.value))}>
          {[1, 2, 3, 4, 5, 6].map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </SearchSelect>
        <SearchButton loading={loading} onClick={doSearch} icon={Search}>
          Search Hotels
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
        <span className="result-count">{filtered.length} matching stays</span>
      </div>

      {loading ? (
        <Shimmer label={`Scanning ${city} for the best stays`} />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={BedDouble}
          title="No hotels match these filters."
          hint="Try a broader rating, price, or sustainability filter."
          onClear={() => {
            setSort("rating");
            setMinStars(null);
            setEcoOnly(false);
          }}
        />
      ) : (
        <div className="results-grid">
          {filtered.map((hotel, i) => (
            <HotelCard key={hotel.id} hotel={hotel} index={i} selected={selected} onSelect={setSelected} />
          ))}
        </div>
      )}

      {selectedHotel && (
        <div className="selected-bar">
          <div>
            <strong>{selectedHotel.name}</strong>
            <div className="result-count">
              ${selectedHotel.total_price_usd.toLocaleString()} total for {nights} night{nights !== 1 ? "s" : ""}
            </div>
          </div>
          <button type="button" className="secondary-button">
            <DollarSign size={17} />
            Add to itinerary
            <ArrowRight size={17} />
          </button>
        </div>
      )}
    </div>
  );
}
