import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

const CITY_CENTERS = {
  mumbai: [19.076, 72.8777],
  tokyo: [35.6762, 139.6503],
  bali: [-8.3405, 115.092],
  paris: [48.8566, 2.3522],
  london: [51.5072, -0.1276],
  "new york": [40.7128, -74.006],
};

function extractPins(itinerary) {
  const pins = [];
  if (!itinerary) return pins;

  const walk = (obj) => {
    if (!obj || typeof obj !== "object") return;
    if (Array.isArray(obj)) {
      obj.forEach(walk);
      return;
    }
    if (typeof obj.lat === "number" && typeof obj.lng === "number") {
      pins.push({
        lat: obj.lat,
        lng: obj.lng,
        name: obj.name || obj.title || obj.location_name || "Point",
      });
      return;
    }
    Object.values(obj).forEach(walk);
  };

  walk(itinerary);
  return pins;
}

export default function TripMap({ itinerary, destination = "", center = [19.076, 72.8777] }) {
  const pins = extractPins(itinerary);
  const destCenter = CITY_CENTERS[destination.toLowerCase()] || center;
  const mapCenter = pins.length ? [pins[0].lat, pins[0].lng] : destCenter;

  return (
    <div className="trip-map">
      <MapContainer key={mapCenter.join(",")} center={mapCenter} zoom={12} style={{ height: "320px", width: "100%", borderRadius: "8px" }}>
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        />
        {pins.map((p, i) => (
          <Marker key={`${p.name}-${i}`} position={[p.lat, p.lng]}>
            <Popup>{p.name}</Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
