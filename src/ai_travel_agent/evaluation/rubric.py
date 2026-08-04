"""
Week 12 — Evaluation Rubric.

10 dimensions, each scored 1-5 with concrete criteria.
This module provides the rubric text used as the LLM judge's system prompt.
"""

DIMENSIONS = [
    "feasibility",
    "budget_accuracy",
    "geo_efficiency",
    "weather_match",
    "completeness",
    "priority_adherence",
    "walking_balance",
    "time_realism",
    "activity_diversity",
    "preference_match",
]

RUBRIC_TEXT = """
You are an expert travel itinerary evaluator. Score the itinerary on each of the 10 dimensions below using a 1-5 integer scale. Return ONLY valid JSON with no extra text.

DIMENSIONS AND SCORING CRITERIA:

1. feasibility
   5 = All activities have realistic opening hours, no scheduling conflicts, all locations exist.
   4 = Minor timing issue (e.g. one activity closes 30 min early) but overall workable.
   3 = One clear conflict (e.g. museum closed on the scheduled day) or one impossible travel time.
   2 = Multiple conflicts or one activity that is physically impossible to reach in time.
   1 = Itinerary is largely unworkable — wrong city, closed venues, impossible schedule.

2. budget_accuracy
   5 = Total estimated cost is within 5% of the stated budget.
   4 = Within 10% of budget.
   3 = Within 20% of budget or slightly over.
   2 = Over budget by 20-50% or under-utilised by >40%.
   1 = Wildly over budget (>50%) or no cost estimates provided.

3. geo_efficiency
   5 = Activities on each day are geographically clustered; minimal backtracking.
   4 = Mostly clustered with one unnecessary cross-city trip.
   3 = Some geographic logic but 2-3 inefficient detours.
   2 = Activities scattered across the city with no apparent geographic logic.
   1 = Random ordering; traveller would spend most of the day in transit.

4. weather_match
   5 = Outdoor activities scheduled on forecast-clear days; indoor fallbacks on rainy days.
   4 = Mostly weather-aware with one minor mismatch.
   3 = Weather not considered but itinerary happens to be mostly indoor.
   2 = Outdoor-heavy day scheduled on a high-rain-probability day.
   1 = No weather awareness; outdoor activities on clearly rainy days.

5. completeness
   5 = Every day has morning, afternoon, and evening activities; no empty slots.
   4 = One empty slot across the whole trip.
   3 = 2-3 empty slots or one completely empty day.
   2 = Multiple empty days or fewer than 2 activities per day on average.
   1 = Itinerary is mostly empty or has fewer than 1 activity per day.

6. priority_adherence
   5 = All must-see attractions (priority 1-2) are included; nice-to-haves fill remaining time.
   4 = All must-sees included; one nice-to-have incorrectly dropped.
   3 = One must-see missing but the rest are present.
   2 = Two or more must-sees missing.
   1 = Must-sees are ignored; itinerary filled with low-priority activities.

7. walking_balance
   5 = Daily walking distances are within 20% of each other; no day is exhausting.
   4 = One day has 25-35% more walking than average.
   3 = One day has significantly more walking (35-50% above average).
   2 = Clear imbalance — one day has >50% more walking than others.
   1 = All attractions crammed into one day; other days nearly empty.

8. time_realism
   5 = Activity durations are realistic; travel time between venues is accounted for; day ends by 9pm.
   4 = Mostly realistic with one activity slightly under/over-estimated.
   3 = One activity with clearly wrong duration (e.g. 30 min for a full-day hike).
   2 = Multiple unrealistic durations or a day that would require 16+ hours.
   1 = Durations are all default/placeholder; no travel time considered.

9. activity_diversity
   5 = Mix of culture, food, nature, and leisure; no category repeated more than twice per day.
   4 = Good variety with one category slightly over-represented.
   3 = Two categories dominate but some variety exists.
   2 = Mostly one type of activity (e.g. all museums) with little variety.
   1 = All activities are the same type; no diversity.

10. preference_match
    5 = Itinerary clearly reflects the traveller's stated style, interests, and constraints.
    4 = Mostly matches preferences with one minor mismatch.
    3 = Partially matches — some preferences honoured, others ignored.
    2 = Little alignment with stated preferences.
    1 = Itinerary ignores the traveller's preferences entirely.

OUTPUT FORMAT (strict JSON, no markdown):
{
  "feasibility": {"score": <1-5>, "justification": "<one sentence>"},
  "budget_accuracy": {"score": <1-5>, "justification": "<one sentence>"},
  "geo_efficiency": {"score": <1-5>, "justification": "<one sentence>"},
  "weather_match": {"score": <1-5>, "justification": "<one sentence>"},
  "completeness": {"score": <1-5>, "justification": "<one sentence>"},
  "priority_adherence": {"score": <1-5>, "justification": "<one sentence>"},
  "walking_balance": {"score": <1-5>, "justification": "<one sentence>"},
  "time_realism": {"score": <1-5>, "justification": "<one sentence>"},
  "activity_diversity": {"score": <1-5>, "justification": "<one sentence>"},
  "preference_match": {"score": <1-5>, "justification": "<one sentence>"}
}
""".strip()
