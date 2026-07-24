const NODE_LABELS = {
  parse_preferences: "Parsing your request",
  allocate_budget: "Allocating budget",
  search_flights: "Searching flights",
  search_hotels: "Finding hotels",
  find_attractions: "Discovering attractions",
  find_restaurants: "Finding restaurants",
  check_weather: "Checking weather",
  track_budget: "Tracking budget",
  build_geo_clusters: "Clustering locations",
  build_itinerary: "Building itinerary",
  optimize_routes: "Optimizing routes",
  evaluate_budget: "Evaluating budget",
  assemble_output: "Assembling final plan",
};

export default function ProgressSteps({ steps, streaming }) {
  if (!steps.length) return null;
  const doneNodes = steps.map((s) => s.node);

  return (
    <div className="progress-steps">
      {Object.entries(NODE_LABELS).map(([node, label]) => {
        const idx = doneNodes.indexOf(node);
        const done = idx !== -1;
        const active = streaming && idx === doneNodes.length - 1;
        return (
          <div key={node} className={`progress-step${done ? " done" : ""}${active ? " active" : ""}`}>
            <span className="step-icon">{done ? "✓" : active ? "⟳" : "○"}</span>
            <span className="step-label">{label}</span>
          </div>
        );
      })}
    </div>
  );
}
