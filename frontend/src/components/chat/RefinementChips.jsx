const CHIPS = [
  "Less walking",
  "Upgrade hotel",
  "Add museums",
  "More shopping",
  "Family friendly",
  "Budget friendly",
  "Add restaurants",
  "Outdoor activities",
];

export default function RefinementChips({ onChip, disabled }) {
  return (
    <div className="refinement-chips">
      {CHIPS.map((chip) => (
        <button
          key={chip}
          className="chip"
          onClick={() => onChip(chip)}
          disabled={disabled}
          type="button"
        >
          {chip}
        </button>
      ))}
    </div>
  );
}
