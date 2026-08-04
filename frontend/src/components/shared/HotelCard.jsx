import { BedDouble, Check, Leaf, MapPin, Wifi } from "lucide-react";
import { PALETTES, Rating, initials } from "./TravelUI";

const AMENITY_ICONS = {
  "Free Wi-Fi": Wifi,
  Pool: BedDouble,
  Spa: Check,
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

export function HotelCard({ hotel, index, selected, onSelect, standalone = false, hidePrice = false }) {
  const isSelected = selected === hotel.id;
  const gradient = PALETTES[index % PALETTES.length] || PALETTES[0];

  const content = (
    <>
      <div className="card-image" style={{ background: `linear-gradient(180deg, rgba(15,23,42,.04), rgba(15,23,42,.62)), ${gradient}` }}>
        <div className="card-image__initials">{initials(hotel.name)}</div>
      </div>

      <div className="card-body">
        <div className="card-title-row">
          <div>
            <h3 className="card-title">{hotel.name}</h3>
            <Rating score={hotel.review_score || hotel.rating} count={hotel.review_count || hotel.ratingCount} />
          </div>
          {!hidePrice && (
            <div className="price-block">
              <strong>{hotel.price_per_night_usd || hotel.price_per_night ? `$${Number(hotel.price_per_night_usd || hotel.price_per_night).toFixed(0)}` : "View"}</strong>
              <span>{(hotel.price_per_night_usd || hotel.price_per_night) ? "per night" : "live listing"}</span>
            </div>
          )}
        </div>

        <div className="icon-line">
          <MapPin size={16} />
          <span>{hotel.address || "City Center"}</span>
        </div>

        <div className="amenity-row">
          {hotel.eco_certified && (
            <span className="badge">
              <Leaf size={13} />
              Eco certified
            </span>
          )}
          {(hotel.amenities || []).slice(0, 5).map((amenity) => {
            const Icon = AMENITY_ICONS[amenity] || Check;
            return (
              <span className="badge" key={amenity}>
                <Icon size={13} />
                {amenity}
              </span>
            );
          })}
        </div>
        
        {!hidePrice && hotel.total_price_usd && (
           <div className="price-total">
             Total stay: ${hotel.total_price_usd.toFixed(0)}
           </div>
        )}
      </div>
    </>
  );

  if (standalone) {
    return (
      <article className="result-card hotel-card">
        {content}
      </article>
    );
  }

  return (
    <article
      className={`result-card hotel-card${isSelected ? " is-selected" : ""}`}
      onClick={() => onSelect && onSelect(isSelected ? null : hotel.id)}
    >
      {content}
    </article>
  );
}
