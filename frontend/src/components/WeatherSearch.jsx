import { useState, useEffect, useCallback } from "react";
import { CloudRain, CloudSun, Droplets, MapPin, Search, Sun, Thermometer, Umbrella } from "lucide-react";
import {
  EmptyState,
  ErrorBanner,
  MetricCard,
  PageHeader,
  SearchButton,
  SearchInput,
  SearchPanel,
  SearchSelect,
  Shimmer,
} from "./shared/TravelUI";

const API_BASE = "http://localhost:8000";

function buildMockWeather(days) {
  const conditions = ["Sunny", "Partly cloudy", "Cloudy", "Light rain", "Sunny"];
  const today = new Date();
  return Array.from({ length: days }, (_, i) => {
    const d = new Date(today);
    d.setDate(d.getDate() + i);
    return {
      date: d.toISOString().split("T")[0],
      condition: conditions[i % conditions.length],
      temp_min: 11 + (i % 3),
      temp_max: 19 + (i % 4),
      rain_chance_pct: [10, 20, 65, 30, 5][i % 5],
      humidity_pct: 55 + (i % 3) * 8,
    };
  });
}

function formatDate(dateStr) {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

function WeatherCard({ day, globalMin, globalMax }) {
  const range = globalMax - globalMin || 1;
  const left = ((day.temp_min - globalMin) / range) * 100;
  const width = ((day.temp_max - day.temp_min) / range) * 100;
  const isRainy = day.rain_chance_pct >= 50;
  const Icon = isRainy ? CloudRain : day.condition?.toLowerCase().includes("cloud") ? CloudSun : Sun;

  return (
    <article className="weather-card">
      <div className="weather-card__top">
        <div>
          <strong>{formatDate(day.date)}</strong>
          <div className="result-count" style={{ marginTop: 4 }}>{day.condition}</div>
        </div>
        <div className="weather-icon">
          <Icon size={22} />
        </div>
      </div>

      <div className="weather-temp">{Math.round(day.temp_max)} deg</div>
      <div className="temp-track" aria-label="Daily temperature range">
        <div
          className="temp-range"
          style={{
            marginLeft: `${Math.max(0, left)}%`,
            width: `${Math.max(8, width)}%`,
          }}
        />
      </div>

      <div className="weather-facts">
        <span>{Math.round(day.temp_min)} deg low</span>
        <span>{day.rain_chance_pct}% rain</span>
        <span>{day.humidity_pct}% humidity</span>
      </div>
    </article>
  );
}

export default function WeatherSearch() {
  const [city, setCity] = useState("London");
  const [days, setDays] = useState(5);
  const [forecast, setForecast] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastCity, setLastCity] = useState("London");

  const doSearch = useCallback(async () => {
    setLoading(true);
    setError(null);
    setLastCity(city);

    try {
      const qs = new URLSearchParams({ city, days });
      const res = await fetch(`${API_BASE}/api/trip/weather?${qs}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setForecast(Array.isArray(data) && data.length ? data : []);
      if (Array.isArray(data) && data.length === 0) {
        setError("No forecast available for this city. Check the city name or API key.");
      }
    } catch {
      setError("Could not reach the server. Showing sample results.");
      setForecast(buildMockWeather(days));
    } finally {
      setLoading(false);
    }
  }, [city, days]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    doSearch();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const allTemps = forecast.flatMap((d) => [d.temp_min, d.temp_max]);
  const globalMin = allTemps.length ? Math.min(...allTemps) : 0;
  const globalMax = allTemps.length ? Math.max(...allTemps) : 1;
  const avgHigh = forecast.length ? Math.round(forecast.reduce((s, d) => s + d.temp_max, 0) / forecast.length) : 0;
  const avgLow = forecast.length ? Math.round(forecast.reduce((s, d) => s + d.temp_min, 0) / forecast.length) : 0;
  const rainyDays = forecast.filter((d) => d.rain_chance_pct >= 50).length;

  return (
    <div className="planner-page">
      <PageHeader
        eyebrow="Forecast"
        title={`Weather in ${lastCity}`}
        subtitle="Plan around temperature, rain chance, and humidity before you book."
        meta={`${forecast.length} day${forecast.length !== 1 ? "s" : ""}`}
      />

      <SearchPanel columns="2fr 1fr 1fr">
        <SearchInput label="City" icon={MapPin} value={city} onChange={(e) => setCity(e.target.value)} placeholder="e.g. London" />
        <SearchSelect label="Days" icon={CloudSun} value={days} onChange={(e) => setDays(Number(e.target.value))}>
          {[3, 5, 7, 8].map((n) => (
            <option key={n} value={n}>{n} days</option>
          ))}
        </SearchSelect>
        <SearchButton loading={loading} onClick={doSearch} icon={Search}>
          Search
        </SearchButton>
      </SearchPanel>

      <ErrorBanner msg={error} />

      {loading ? (
        <Shimmer label={`Checking the skies over ${city}`} />
      ) : forecast.length === 0 ? (
        <EmptyState icon={CloudSun} title="No forecast data to show." hint="Try a different city or a shorter forecast window." />
      ) : (
        <>
          <div className="metric-grid">
            <MetricCard label="Avg high" value={`${avgHigh} deg`} icon={Thermometer} />
            <MetricCard label="Avg low" value={`${avgLow} deg`} icon={Thermometer} />
            <MetricCard label="Rainy days" value={`${rainyDays} of ${forecast.length}`} icon={Umbrella} />
            <MetricCard
              label="Avg humidity"
              value={`${Math.round(forecast.reduce((s, d) => s + d.humidity_pct, 0) / forecast.length)}%`}
              icon={Droplets}
            />
          </div>

          <div className="weather-grid">
            {forecast.map((day, i) => (
              <WeatherCard key={day.date || i} day={day} globalMin={globalMin} globalMax={globalMax} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
