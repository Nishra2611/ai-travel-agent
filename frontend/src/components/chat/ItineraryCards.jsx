import { useState } from "react";

function DayCard({ day, activities }) {
  const [open, setOpen] = useState(true);
  const items = Array.isArray(activities) ? activities : [String(activities)];

  return (
    <div className="day-card">
      <button className="day-card__header" onClick={() => setOpen((o) => !o)}>
        <span className="day-card__arrow">{open ? "▼" : "▶"}</span>
        <span>{day}</span>
        <span className="day-card__count">{items.length} activities</span>
      </button>
      {open && (
        <ul className="day-card__body">
          {items.map((item, i) => (
            <li key={i} className="day-card__item">
              {typeof item === "object" ? JSON.stringify(item) : item}
            </li>
          ))}
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
