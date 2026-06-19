import { useState } from "react";

const API_BASE = "http://localhost:8000";

export default function WeatherSearch() {
  const [city, setCity] = useState("London");
  const [days, setDays] = useState(3);
  const [forecast, setForecast] = useState([]);
  const [loading, setLoading] = useState(false);

  async function getWeather() {
    try {
      setLoading(true);

      const res = await fetch(
        `${API_BASE}/api/trip/weather?city=${city}&days=${days}`
      );

      const data = await res.json();

      setForecast(data);
    } catch (err) {
      console.error(err);
      alert("Failed to fetch weather");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        maxWidth: "680px",
        margin: "20px auto",
        padding: "20px",
        border: "1px solid #ddd",
        borderRadius: "10px",
      }}
    >
      <h2>Weather Forecast</h2>

      <input
        value={city}
        onChange={(e) => setCity(e.target.value)}
        placeholder="City"
      />

      <input
        type="number"
        value={days}
        min="1"
        max="5"
        onChange={(e) => setDays(e.target.value)}
        style={{ marginLeft: "10px" }}
      />

      <button
        onClick={getWeather}
        style={{ marginLeft: "10px" }}
      >
        Search
      </button>

      {loading && <p>Loading...</p>}

      {forecast.map((day) => (
        <div
          key={day.date}
          style={{
            border: "1px solid #eee",
            padding: "10px",
            marginTop: "10px",
          }}
        >
          <h4>{day.date}</h4>
          <p>{day.condition}</p>
          <p>
            {day.temp_min}°C - {day.temp_max}°C
          </p>
          <p>Humidity: {day.humidity_pct}%</p>
          <p>Rain Chance: {day.rain_chance_pct}%</p>
        </div>
      ))}
    </div>
  );
}