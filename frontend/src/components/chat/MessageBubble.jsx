import ItineraryCards from "./ItineraryCards";
import TripMap from "./TripMap";

export default function MessageBubble({ msg }) {
  if (msg.role === "progress") {
    return (
      <div className="bubble bubble--progress">
        <span className="bubble__icon">⟳</span>
        <span>{msg.text}</span>
      </div>
    );
  }
  if (msg.role === "error") {
    return <div className="bubble bubble--error">⚠ {msg.text}</div>;
  }
  if (msg.role === "user") {
    return <div className="bubble bubble--user">{msg.text}</div>;
  }
  // assistant
  return (
    <div className="bubble bubble--assistant">
      <p>{msg.text}</p>
      {msg.itinerary && Object.keys(msg.itinerary).length > 0 && (
        <>
          <ItineraryCards itinerary={msg.itinerary} />
          <TripMap itinerary={msg.itinerary} />
        </>
      )}
    </div>
  );
}
