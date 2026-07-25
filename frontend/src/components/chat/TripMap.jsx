import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";

// fix default marker icons broken by webpack/vite
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

function extractPins(itinerary) {
  const pins = [];
  if (!itinerary) return pins;
  const walk = (obj) => {
    if (!obj || typeof obj !== "object") return;
    if (Array.isArray(obj)) { obj.forEach(walk); return; }
    if (typeof obj.lat === "number" && typeof obj.lng === "number") {
      pins.push({ lat: obj.lat, lng: obj.lng, name: obj.name || obj.title || "Point" });
      return;
    }
    Object.values(obj).forEach(walk);
  };
  walk(itinerary);
  return pins;
}

export default function TripMap({ itinerary, center = [48.8566, 2.3522] }) {
  const pins = extractPins(itinerary);
  const mapCenter = pins.length ? [pins[0].lat, pins[0].lng] : center;

  return (
    <div className="trip-map">
      <MapContainer center={mapCenter} zoom={12} style={{ height: "300px", width: "100%", borderRadius: "12px" }}>
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        />
        {pins.map((p, i) => (
          <Marker key={i} position={[p.lat, p.lng]}>
            <Popup>{p.name}</Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
