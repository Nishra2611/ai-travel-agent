import { useState } from "react";
import { ChevronDown, ChevronRight, Clock3, MapPin } from "lucide-react";

function titleFor(item) {
  if (typeof item !== "object" || item === null) return String(item);
  const slot = item.time_slot ? `${String(item.time_slot).replace("_", " ")}: ` : "";
  return `${slot}${item.title || item.name || item.location_name || "Activity"}`;
}

function metaFor(item) {
  if (typeof item !== "object" || item === null) return "";
  const bits = [];
  if (item.estimated_duration_hours) bits.push(`${item.estimated_duration_hours}h`);
  if (item.estimated_cost_usd) bits.push(`$${Number(item.estimated_cost_usd).toFixed(0)}`);
  if (item.location_name && item.location_name !== item.title) bits.push(item.location_name);
  return bits.join(" - ");
}

function DayCard({ day, activities }) {
  const [open, setOpen] = useState(true);
  const items = Array.isArray(activities) ? activities : [activities];

  return (
    <div className="day-card">
      <button type="button" className="day-card__header" onClick={() => setOpen((o) => !o)}>
        <span className="day-card__arrow">{open ? <ChevronDown size={17} /> : <ChevronRight size={17} />}</span>
        <span>{day}</span>
        <span className="day-card__count">{items.length} activities</span>
      </button>
      {open && (
        <ul className="day-card__body">
          {items.map((item, i) => {
            const meta = metaFor(item);
            const hasCoords = typeof item === "object" && item?.lat && item?.lng;
            return (
              <li key={i} className="day-card__item">
                <span className="day-card__item-title">{titleFor(item)}</span>
                {meta && (
                  <span className="day-card__item-meta">
                    {hasCoords ? <MapPin size={13} /> : <Clock3 size={13} />}
                    {meta}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export default function ItineraryCards({ itinerary }) {
  if (!itinerary || !Object.keys(itinerary).length) return null;
  return (
    <div className="itinerary-cards">
      {Object.entries(itinerary).map(([day, activities]) => (
        <DayCard key={day} day={day} activities={activities} />
      ))}
    </div>
  );
}
