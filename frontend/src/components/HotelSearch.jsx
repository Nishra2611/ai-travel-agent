import { useState, useEffect, useCallback } from "react";

// ─── config ───────────────────────────────────────────────────────────────
// Point this at your FastAPI server. Change if you deploy elsewhere.
const API_BASE = "http://localhost:8000";

// ─── constants ────────────────────────────────────────────────────────────

const AMENITY_ICONS = {
  "Free Wi-Fi": "📶",
  Pool: "🏊",
  Spa: "💆",
  Gym: "🏋️",
  Breakfast: "🥐",
  Bar: "🍸",
  Rooftop: "🌆",
  Concierge: "🛎️",
  Garden: "🌿",
  Restaurant: "🍽️",
  "Shared Kitchen": "🍳",
  "Historic Building": "🏛️",
  Kitchenette: "🍴",
};

const PALETTES = [
  { bg: "#E1F5EE", tx: "#085041" },
  { bg: "#EEEDFE", tx: "#3C3489" },
  { bg: "#FAECE7", tx: "#712B13" },
  { bg: "#FAEEDA", tx: "#633806" },
  { bg: "#E6F1FB", tx: "#0C447C" },
];

const DEST_HINTS = [
  "Where are you off to?",
  "Paris calling…",
  "Tokyo dreams await",
  "Bali or bust",
  "Find your escape",
];

// ─── helpers ──────────────────────────────────────────────────────────────

function initials(name) {
  return name
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();
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

// ─── small shared pieces ─────────────────────────────────────────────────

function Stars({ score, count }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
      {[1, 2, 3, 4, 5].map((i) => (
        <span
          key={i}
          style={{
            fontSize: 11,
            color:
              i <= Math.floor(score)
                ? "#BA7517"
                : i === Math.ceil(score) && score % 1 >= 0.5
                ? "#EF9F27"
                : "var(--color-border-secondary)",
          }}
        >
          ★
        </span>
      ))}
      {count != null && (
        <span style={{ fontSize: 11, color: "var(--color-text-secondary)" }}>
          {score} · {count.toLocaleString()} reviews
        </span>
      )}
    </div>
  );
}

function Pill({ label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: "5px 13px",
        borderRadius: 20,
        fontSize: 12,
        border: active ? "1px solid #BA7517" : "0.5px solid var(--color-border-tertiary)",
        background: active ? "#FAEEDA" : "var(--color-background-primary)",
        color: active ? "#633806" : "var(--color-text-secondary)",
        cursor: "pointer",
        fontFamily: "inherit",
        transition: "all .15s",
      }}
    >
      {label}
    </button>
  );
}

function SearchInput({ label, ...props }) {
  return (
    <div>
      <div
        style={{
          fontSize: 10,
          color: "var(--color-text-secondary)",
          fontWeight: 500,
          letterSpacing: ".06em",
          marginBottom: 4,
          textTransform: "uppercase",
        }}
      >
        {label}
      </div>
      <input
        {...props}
        style={{
          width: "100%",
          fontSize: 13,
          padding: "8px 10px",
          border: "0.5px solid var(--color-border-tertiary)",
          borderRadius: "var(--border-radius-md)",
          background: "var(--color-background-secondary)",
          color: "var(--color-text-primary)",
          fontFamily: "inherit",
          outline: "none",
          boxSizing: "border-box",
        }}
        onFocus={(e) => (e.target.style.borderColor = "#BA7517")}
        onBlur={(e) => (e.target.style.borderColor = "var(--color-border-tertiary)")}
      />
    </div>
  );
}

function Shimmer({ city }) {
  return (
    <div style={{ padding: "48px 0", textAlign: "center" }}>
      <div style={{ fontSize: 13, color: "var(--color-text-secondary)", marginBottom: 16 }}>
        Scanning {city} for the best stays…
      </div>
      <div
        style={{
          height: 3,
          background: "var(--color-background-secondary)",
          borderRadius: 2,
          overflow: "hidden",
          maxWidth: 320,
          margin: "0 auto",
        }}
      >
        <div
          style={{
            height: "100%",
            width: "40%",
            background: "#BA7517",
            borderRadius: 2,
            animation: "shimmer 1.3s ease-in-out infinite",
          }}
        />
      </div>
      <style>{`@keyframes shimmer{0%{margin-left:-40%}100%{margin-left:140%}}`}</style>
    </div>
  );
}

function ErrorBanner({ msg }) {
  if (!msg) return null;
  return (
    <div
      style={{
        padding: "10px 14px",
        borderRadius: "var(--border-radius-md)",
        background: "#FAEEDA",
        color: "#633806",
        fontSize: 12,
        marginBottom: 14,
        border: "0.5px solid #EF9F27",
      }}
    >
      {msg}
    </div>
  );
}

// ─── hotel card ───────────────────────────────────────────────────────────

function HotelCard({ hotel, index, selected, onSelect }) {
  const pal = PALETTES[index % PALETTES.length];
  const isSel = selected === hotel.id;

  return (
    <div
      onClick={() => onSelect(isSel ? null : hotel.id)}
      style={{
        background: isSel ? "#F1EFE8" : "var(--color-background-primary)",
        border: isSel ? "1.5px solid #BA7517" : "0.5px solid var(--color-border-tertiary)",
        borderRadius: "var(--border-radius-lg)",
        padding: "16px 18px",
        cursor: "pointer",
        marginBottom: 10,
        transition: "all .18s",
      }}
    >
      <div style={{ display: "flex", gap: 14, alignItems: "flex-start" }}>
        <div
          style={{
            width: 48,
            height: 48,
            borderRadius: 12,
            flexShrink: 0,
            background: pal.bg,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 13,
            fontWeight: 500,
            color: pal.tx,
            letterSpacing: 1,
          }}
        >
          {initials(hotel.name)}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
                <span style={{ fontSize: 14, fontWeight: 500, color: "var(--color-text-primary)" }}>
                  {hotel.name}
                </span>
                {hotel.eco_certified && (
                  <span
                    style={{
                      fontSize: 10,
                      padding: "1px 6px",
                      borderRadius: 8,
                      background: "#EAF3DE",
                      color: "#3B6D11",
                      fontWeight: 500,
                    }}
                  >
                    eco
                  </span>
                )}
              </div>
              <Stars score={hotel.review_score} count={hotel.review_count} />
            </div>

            <div style={{ textAlign: "right", flexShrink: 0 }}>
              <div style={{ fontSize: 18, fontWeight: 500, color: "var(--color-text-primary)", lineHeight: 1.2 }}>
                ${hotel.price_per_night_usd.toFixed(0)}
              </div>
              <div style={{ fontSize: 11, color: "var(--color-text-secondary)" }}>/ night</div>
            </div>
          </div>

          <div
            style={{
              fontSize: 12,
              color: "var(--color-text-secondary)",
              marginTop: 6,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            📍 {hotel.address}
          </div>

          <div style={{ display: "flex", gap: 5, marginTop: 9, flexWrap: "wrap" }}>
            {hotel.amenities.slice(0, 5).map((a) => (
              <span
                key={a}
                style={{
                  fontSize: 11,
                  padding: "2px 8px",
                  borderRadius: 10,
                  background: "var(--color-background-secondary)",
                  color: "var(--color-text-secondary)",
                  whiteSpace: "nowrap",
                }}
              >
                {AMENITY_ICONS[a] || "•"} {a}
              </span>
            ))}
            {hotel.amenities.length > 5 && (
              <span style={{ fontSize: 11, color: "var(--color-text-secondary)", padding: "2px 4px" }}>
                +{hotel.amenities.length - 5} more
              </span>
            )}
          </div>
        </div>
      </div>

      {isSel && (
        <div
          style={{
            marginTop: 14,
            paddingTop: 14,
            borderTop: "0.5px solid var(--color-border-tertiary)",
            display: "grid",
            gridTemplateColumns: "1fr 1fr 1fr",
            gap: 10,
          }}
        >
          {[
            ["Total stay", `$${hotel.total_price_usd.toLocaleString()}`],
            ["Check-in", hotel.check_in_time || "3:00 PM"],
            ["Check-out", hotel.check_out_time || "12:00 PM"],
          ].map(([l, v]) => (
            <div
              key={l}
              style={{
                background: "var(--color-background-primary)",
                borderRadius: "var(--border-radius-md)",
                padding: "10px 12px",
                border: "0.5px solid var(--color-border-tertiary)",
              }}
            >
              <div style={{ fontSize: 11, color: "var(--color-text-secondary)", marginBottom: 2 }}>{l}</div>
              <div style={{ fontSize: 14, fontWeight: 500, color: "var(--color-text-primary)" }}>{v}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── HotelSearch — the only export ─────────────────────────────────────────
//
// Standalone, self-contained. Drop this anywhere — a bare App.jsx, a route,
// a tab — without it assuming anything about the rest of the app.
// Talks to GET {API_BASE}/api/hotels (your FastAPI HotelSearchTool endpoint).

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
      setHotels(data.hotels ?? []);
    } catch (e) {
      setError("Could not reach the server — showing sample results.");
      setHotels(buildMockHotels(city, nights));
    } finally {
      setLoading(false);
    }
  }, [city, checkIn, checkOut, adults, nights]);

  // initial load with default values
  useEffect(() => {
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
    <div style={{ maxWidth: 680, margin: "0 auto", padding: "24px 16px", fontFamily: "system-ui, -apple-system, sans-serif" }}>
      <div style={{ marginBottom: 24 }}>
        <div
          style={{
            fontSize: 11,
            color: "#BA7517",
            fontWeight: 500,
            letterSpacing: ".08em",
            marginBottom: 5,
            textTransform: "uppercase",
          }}
        >
          Places to stay
        </div>
        <h2 style={{ fontSize: 22, fontWeight: 500, color: "var(--color-text-primary)", margin: 0 }}>
          Find your room in {lastQuery.city}
        </h2>
        <p style={{ fontSize: 13, color: "var(--color-text-secondary)", margin: "4px 0 0" }}>
          {nights} night{nights !== 1 ? "s" : ""} · {lastQuery.checkIn} → {lastQuery.checkOut}
        </p>
      </div>

      <div
        style={{
          background: "var(--color-background-primary)",
          border: "0.5px solid var(--color-border-tertiary)",
          borderRadius: "var(--border-radius-lg)",
          padding: "18px 20px",
          marginBottom: 22,
        }}
      >
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 70px 100px", gap: 10, alignItems: "end" }}>
          <SearchInput
            label="Destination"
            value={city}
            onChange={(e) => setCity(e.target.value)}
            placeholder={DEST_HINTS[hintIdx]}
          />
          <SearchInput label="Check-in" type="date" value={checkIn} onChange={(e) => setCheckIn(e.target.value)} />
          <SearchInput label="Check-out" type="date" value={checkOut} onChange={(e) => setCheckOut(e.target.value)} />
          <div>
            <div
              style={{
                fontSize: 10,
                color: "var(--color-text-secondary)",
                fontWeight: 500,
                letterSpacing: ".06em",
                marginBottom: 4,
                textTransform: "uppercase",
              }}
            >
              Guests
            </div>
            <select
              value={adults}
              onChange={(e) => setAdults(Number(e.target.value))}
              style={{
                width: "100%",
                fontSize: 13,
                padding: "8px 6px",
                border: "0.5px solid var(--color-border-tertiary)",
                borderRadius: "var(--border-radius-md)",
                background: "var(--color-background-secondary)",
                color: "var(--color-text-primary)",
                fontFamily: "inherit",
              }}
            >
              {[1, 2, 3, 4, 5, 6].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </div>
          <div>
            <div style={{ fontSize: 10, opacity: 0, marginBottom: 4 }}>x</div>
            <button
              onClick={doSearch}
              disabled={loading}
              style={{
                width: "100%",
                padding: "9px 0",
                background: loading ? "var(--color-border-secondary)" : "#2C2C2A",
                color: "#fff",
                border: "none",
                borderRadius: "var(--border-radius-md)",
                fontSize: 13,
                fontWeight: 500,
                cursor: loading ? "default" : "pointer",
                fontFamily: "inherit",
                transition: "background .15s",
              }}
            >
              {loading ? "searching…" : "Search"}
            </button>
          </div>
        </div>
      </div>

      <ErrorBanner msg={error} />

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14, gap: 8, flexWrap: "wrap" }}>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
          <span style={{ fontSize: 11, color: "var(--color-text-secondary)", fontWeight: 500 }}>Filter:</span>
          <Pill label="Best rated" active={sort === "rating"} onClick={() => setSort("rating")} />
          <Pill label="Lowest price" active={sort === "price"} onClick={() => setSort("price")} />
          <Pill label="5 star" active={minStars === 5} onClick={() => setMinStars(minStars === 5 ? null : 5)} />
          <Pill label="4+ star" active={minStars === 4} onClick={() => setMinStars(minStars === 4 ? null : 4)} />
          <Pill label="Eco" active={ecoOnly} onClick={() => setEcoOnly((v) => !v)} />
        </div>
        <span style={{ fontSize: 12, color: "var(--color-text-secondary)", flexShrink: 0 }}>
          {filtered.length} place{filtered.length !== 1 ? "s" : ""}
        </span>
      </div>

      {loading ? (
        <Shimmer city={city} />
      ) : filtered.length === 0 ? (
        <div style={{ padding: "48px 0", textAlign: "center" }}>
          <div style={{ fontSize: 28, marginBottom: 10 }}>🏨</div>
          <div style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>No hotels match these filters.</div>
          <button
            onClick={() => {
              setSort("rating");
              setMinStars(null);
              setEcoOnly(false);
            }}
            style={{ marginTop: 10, fontSize: 12, color: "#BA7517", background: "none", border: "none", cursor: "pointer", fontFamily: "inherit" }}
          >
            Clear filters
          </button>
        </div>
      ) : (
        filtered.map((h, i) => (
          <HotelCard key={h.id} hotel={h} index={i} selected={selected} onSelect={setSelected} />
        ))
      )}

      {selectedHotel && (
        <div
          style={{
            marginTop: 20,
            padding: "14px 18px",
            borderRadius: "var(--border-radius-lg)",
            background: "#F1EFE8",
            border: "0.5px solid var(--color-border-tertiary)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div>
            <div style={{ fontSize: 13, fontWeight: 500, color: "var(--color-text-primary)" }}>{selectedHotel.name}</div>
            <div style={{ fontSize: 12, color: "var(--color-text-secondary)", marginTop: 2 }}>
              ${selectedHotel.total_price_usd.toLocaleString()} total · {nights} night{nights !== 1 ? "s" : ""}
            </div>
          </div>
          <button
            style={{
              padding: "9px 20px",
              background: "#2C2C2A",
              color: "#fff",
              border: "none",
              borderRadius: "var(--border-radius-md)",
              fontSize: 13,
              fontWeight: 500,
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            Add to itinerary
          </button>
        </div>
      )}
    </div>
  );
}
