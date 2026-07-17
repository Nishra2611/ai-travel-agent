from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class BudgetCategory(StrEnum):
    FLIGHTS = "flights"
    ACCOMMODATION = "accommodation"
    FOOD = "food"
    ACTIVITIES = "activities"
    TRANSPORT = "transport"
    MISC = "misc"


class BudgetProfile(StrEnum):
    BACKPACKER = "backpacker"
    MID_RANGE = "mid_range"
    LUXURY = "luxury"


# Starting-point split (% of total budget) per profile, before preference
# weighting. Tuned as reasonable defaults — revisit once real trip cost
# data flows through track_budget.
DEFAULT_PROFILE_SPLITS: dict[BudgetProfile, dict[BudgetCategory, float]] = {
    BudgetProfile.BACKPACKER: {
        BudgetCategory.FLIGHTS: 0.30,
        BudgetCategory.ACCOMMODATION: 0.20,
        BudgetCategory.FOOD: 0.25,
        BudgetCategory.ACTIVITIES: 0.15,
        BudgetCategory.TRANSPORT: 0.07,
        BudgetCategory.MISC: 0.03,
    },
    BudgetProfile.MID_RANGE: {
        BudgetCategory.FLIGHTS: 0.28,
        BudgetCategory.ACCOMMODATION: 0.32,
        BudgetCategory.FOOD: 0.20,
        BudgetCategory.ACTIVITIES: 0.12,
        BudgetCategory.TRANSPORT: 0.05,
        BudgetCategory.MISC: 0.03,
    },
    BudgetProfile.LUXURY: {
        BudgetCategory.FLIGHTS: 0.25,
        BudgetCategory.ACCOMMODATION: 0.45,
        BudgetCategory.FOOD: 0.15,
        BudgetCategory.ACTIVITIES: 0.10,
        BudgetCategory.TRANSPORT: 0.03,
        BudgetCategory.MISC: 0.02,
    },
}

# Hard floors (% of total budget) so optimization never zeroes a category.
MIN_CATEGORY_FLOOR_PCT: dict[BudgetCategory, float] = {
    BudgetCategory.FLIGHTS: 0.10,
    BudgetCategory.ACCOMMODATION: 0.10,
    BudgetCategory.FOOD: 0.08,
    BudgetCategory.ACTIVITIES: 0.03,
    BudgetCategory.TRANSPORT: 0.02,
    BudgetCategory.MISC: 0.0,
}

# Search-tool hints per profile — lets allocate_budget bias FlightSearchTool
# / HotelSearchTool filters, not just label money.
SCENARIO_SEARCH_HINTS: dict[BudgetProfile, dict] = {
    BudgetProfile.BACKPACKER: {
        "max_hotel_stars": 3,
        "min_hotel_rating": 3.5,
        "flight_max_stops": 2,
    },
    BudgetProfile.MID_RANGE: {
        "max_hotel_stars": 4,
        "min_hotel_rating": 4.0,
        "flight_max_stops": 1,
    },
    BudgetProfile.LUXURY: {
        "max_hotel_stars": 5,
        "min_hotel_rating": 4.5,
        "flight_max_stops": 0,
    },
}

# "X over Y" / "X matters more than Y" -> boost X, reduce Y.
_PRIORITY_RE = re.compile(
    r"prioriti[sz]e\s+(?P<a>[a-z ]+?)\s+over\s+(?P<b>[a-z ]+)", re.I
)
_COMPARATIVE_RE = re.compile(
    r"(?P<a>[a-z ]+?)\s+matters?\s+more\s+than\s+(?P<b>[a-z ]+)", re.I
)

_CATEGORY_SYNONYMS: dict[str, BudgetCategory] = {
    "accommodation": BudgetCategory.ACCOMMODATION,
    "hotel": BudgetCategory.ACCOMMODATION,
    "hotels": BudgetCategory.ACCOMMODATION,
    "lodging": BudgetCategory.ACCOMMODATION,
    "dining": BudgetCategory.FOOD,
    "food": BudgetCategory.FOOD,
    "restaurants": BudgetCategory.FOOD,
    "flights": BudgetCategory.FLIGHTS,
    "flight": BudgetCategory.FLIGHTS,
    "airfare": BudgetCategory.FLIGHTS,
    "activities": BudgetCategory.ACTIVITIES,
    "experiences": BudgetCategory.ACTIVITIES,
    "tours": BudgetCategory.ACTIVITIES,
    "attractions": BudgetCategory.ACTIVITIES,
    "transport": BudgetCategory.TRANSPORT,
    "transportation": BudgetCategory.TRANSPORT,
    "taxis": BudgetCategory.TRANSPORT,
    "shopping": BudgetCategory.MISC,
    "souvenirs": BudgetCategory.MISC,
}

_BOOST_MULTIPLIER = 1.4
_REDUCE_MULTIPLIER = 0.7


def parse_preference_weights(text: str | None) -> dict[BudgetCategory, float]:
    """
    'I prioritize accommodation over dining' -> {ACCOMMODATION: 1.4, FOOD: 0.7}

    Rule-based, same reasoning as deterministic slot assignment: this is a
    small closed vocabulary of phrasing patterns, not a task that needs an
    LLM call on every request.
    """
    if not text:
        return {}

    weights: dict[BudgetCategory, float] = {}
    for pattern in (_PRIORITY_RE, _COMPARATIVE_RE):
        for match in pattern.finditer(text):
            cat_a = _resolve_category(match.group("a"))
            cat_b = _resolve_category(match.group("b"))
            if cat_a:
                weights[cat_a] = weights.get(cat_a, 1.0) * _BOOST_MULTIPLIER
            if cat_b:
                weights[cat_b] = weights.get(cat_b, 1.0) * _REDUCE_MULTIPLIER
    return weights


def _resolve_category(phrase: str) -> BudgetCategory | None:
    phrase = phrase.strip().lower()
    for token, category in _CATEGORY_SYNONYMS.items():
        if token in phrase:
            return category
    return None


@dataclass
class CategoryAllocation:
    category: BudgetCategory
    allocated_amount: float
    percentage: float
    min_required: float


@dataclass
class BudgetAllocation:
    total_budget: float
    profile: BudgetProfile
    allocations: list[CategoryAllocation]
    search_hints: dict

    def get(self, category: BudgetCategory) -> CategoryAllocation:
        for a in self.allocations:
            if a.category == category:
                return a
        raise KeyError(category)

    def as_dict(self) -> dict:
        """Plain-dict shape for dropping straight into TravelState."""
        return {
            "total_budget": self.total_budget,
            "profile": self.profile.value,
            "allocations": {
                a.category.value: {
                    "amount": round(a.allocated_amount, 2),
                    "percentage": round(a.percentage, 4),
                }
                for a in self.allocations
            },
            "search_hints": self.search_hints,
        }


@dataclass
class TradeoffSuggestion:
    category: BudgetCategory
    action: str  # "upgrade" | "cut"
    current_amount: float
    suggested_amount: float
    delta: float


@dataclass
class TradeoffReport:
    status: str  # "under_budget" | "over_budget" | "on_budget"
    surplus_or_deficit: float
    suggestions: list[TradeoffSuggestion]

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "surplus_or_deficit": round(self.surplus_or_deficit, 2),
            "suggestions": [
                {
                    "category": s.category.value,
                    "action": s.action,
                    "current_amount": round(s.current_amount, 2),
                    "suggested_amount": round(s.suggested_amount, 2),
                    "delta": round(s.delta, 2),
                }
                for s in self.suggestions
            ],
        }


@dataclass
class AdherenceScore:
    overall_score: float
    category_scores: dict[BudgetCategory, float]
    total_spent: float
    variance_pct: float
    verdict: str

    def as_dict(self) -> dict:
        return {
            "overall_score": self.overall_score,
            "category_scores": {k.value: v for k, v in self.category_scores.items()},
            "total_spent": round(self.total_spent, 2),
            "variance_pct": self.variance_pct,
            "verdict": self.verdict,
        }


_CUT_PRIORITY = [
    BudgetCategory.MISC,
    BudgetCategory.TRANSPORT,
    BudgetCategory.ACTIVITIES,
    BudgetCategory.FOOD,
    BudgetCategory.ACCOMMODATION,
    BudgetCategory.FLIGHTS,
]
_UPGRADE_PRIORITY = [
    BudgetCategory.ACCOMMODATION,
    BudgetCategory.ACTIVITIES,
    BudgetCategory.FOOD,
    BudgetCategory.FLIGHTS,
    BudgetCategory.TRANSPORT,
    BudgetCategory.MISC,
]
_CATEGORY_WEIGHTS = {
    BudgetCategory.FLIGHTS: 0.25,
    BudgetCategory.ACCOMMODATION: 0.30,
    BudgetCategory.FOOD: 0.20,
    BudgetCategory.ACTIVITIES: 0.15,
    BudgetCategory.TRANSPORT: 0.07,
    BudgetCategory.MISC: 0.03,
}


class _BudgetOptimizer:
    """Internal, dependency-free budget engine. See module docstring."""

    def allocate(
        self,
        total_budget: float,
        profile: BudgetProfile | str = BudgetProfile.MID_RANGE,
        preference_text: str | None = None,
    ) -> BudgetAllocation:
        if total_budget <= 0:
            raise ValueError("total_budget must be > 0")
        profile = BudgetProfile(profile)

        base_split = dict(DEFAULT_PROFILE_SPLITS[profile])
        weights = parse_preference_weights(preference_text)
        weighted_split = self._apply_weights(base_split, weights)
        final_split = self._enforce_floors(weighted_split)

        allocations = [
            CategoryAllocation(
                category=cat,
                allocated_amount=round(pct * total_budget, 2),
                percentage=pct,
                min_required=round(
                    MIN_CATEGORY_FLOOR_PCT.get(cat, 0.0) * total_budget, 2
                ),
            )
            for cat, pct in final_split.items()
        ]
        return BudgetAllocation(
            total_budget=total_budget,
            profile=profile,
            allocations=allocations,
            search_hints=SCENARIO_SEARCH_HINTS[profile],
        )

    def suggest_tradeoffs(
        self, allocation: BudgetAllocation, actual_spend: dict[BudgetCategory, float]
    ) -> TradeoffReport:
        total_actual = sum(actual_spend.values())
        delta = allocation.total_budget - total_actual  # positive = surplus
        noise_threshold = 0.05 * allocation.total_budget

        if abs(delta) <= noise_threshold:
            return TradeoffReport(
                status="on_budget", surplus_or_deficit=delta, suggestions=[]
            )
        if delta > 0:
            return TradeoffReport(
                status="under_budget",
                surplus_or_deficit=delta,
                suggestions=self._suggest_upgrades(allocation, actual_spend, delta),
            )
        return TradeoffReport(
            status="over_budget",
            surplus_or_deficit=delta,
            suggestions=self._suggest_cuts(allocation, actual_spend, -delta),
        )

    def adherence_score(
        self, allocation: BudgetAllocation, actual_spend: dict[BudgetCategory, float]
    ) -> AdherenceScore:
        category_scores: dict[BudgetCategory, float] = {}
        weighted_sum = 0.0
        weight_total = 0.0

        for alloc in allocation.allocations:
            actual = actual_spend.get(alloc.category, 0.0)
            score = self._category_score(alloc.allocated_amount, actual)
            category_scores[alloc.category] = round(score, 1)
            w = _CATEGORY_WEIGHTS.get(alloc.category, 0.0)
            weighted_sum += score * w
            weight_total += w

        overall = weighted_sum / weight_total if weight_total > 0 else 0.0
        total_spent = sum(actual_spend.values())
        variance_pct = (
            (total_spent - allocation.total_budget) / allocation.total_budget * 100
            if allocation.total_budget > 0
            else 0.0
        )
        return AdherenceScore(
            overall_score=round(overall, 1),
            category_scores=category_scores,
            total_spent=total_spent,
            variance_pct=round(variance_pct, 1),
            verdict=self._verdict(overall, variance_pct),
        )

    # -- internals --------------------------------------------------------

    @staticmethod
    def _apply_weights(
        base_split: dict[BudgetCategory, float], weights: dict[BudgetCategory, float]
    ) -> dict[BudgetCategory, float]:
        if not weights:
            return base_split
        weighted = {cat: pct * weights.get(cat, 1.0) for cat, pct in base_split.items()}
        total = sum(weighted.values())
        return (
            {cat: v / total for cat, v in weighted.items()} if total > 0 else base_split
        )

    @staticmethod
    def _enforce_floors(
        split: dict[BudgetCategory, float],
    ) -> dict[BudgetCategory, float]:
        """Water-filling pass: pull categories up to their floor by
        proportionally shaving categories that are above theirs. Verified
        (see tests/unit/test_budget_optimizer.py) to converge within 5
        passes for all 3 profiles under weights up to the 3.0x cap."""
        split = dict(split)
        for _ in range(5):
            deficits = {
                c: MIN_CATEGORY_FLOOR_PCT.get(c, 0.0) - split[c]
                for c in split
                if split[c] < MIN_CATEGORY_FLOOR_PCT.get(c, 0.0)
            }
            if not deficits:
                break
            total_deficit = sum(deficits.values())
            donors = {
                c: split[c] - MIN_CATEGORY_FLOOR_PCT.get(c, 0.0)
                for c in split
                if c not in deficits and split[c] > MIN_CATEGORY_FLOOR_PCT.get(c, 0.0)
            }
            pool = sum(donors.values())
            if pool <= 0:
                break
            for c, amt in deficits.items():
                split[c] += amt
            for c, headroom in donors.items():
                split[c] -= (headroom / pool) * total_deficit
        total = sum(split.values())
        return {c: v / total for c, v in split.items()}

    @staticmethod
    def _category_score(allocated: float, actual: float) -> float:
        if allocated <= 0:
            return 100.0 if actual <= 0 else 0.0
        variance = (actual - allocated) / allocated
        multiplier = (
            2.0 if variance > 0 else 1.0
        )  # overspend hurts more than underspend
        return max(0.0, min(100.0, 100.0 - abs(variance) * multiplier * 100.0))

    @staticmethod
    def _verdict(overall_score: float, variance_pct: float) -> str:
        if overall_score >= 90:
            return "excellent_adherence"
        if overall_score >= 75:
            return "good_adherence"
        if overall_score >= 50:
            return "significant_deviation"
        return "over_budget" if variance_pct > 0 else "under_budget"

    def _suggest_upgrades(
        self, allocation, actual_spend, surplus
    ) -> list[TradeoffSuggestion]:
        suggestions, remaining = [], surplus
        for category in _UPGRADE_PRIORITY:
            if remaining <= 0:
                break
            current = actual_spend.get(category, 0.0)
            step = min(allocation.get(category).allocated_amount * 0.15, remaining)
            if step < 1:
                continue
            suggestions.append(
                TradeoffSuggestion(category, "upgrade", current, current + step, step)
            )
            remaining -= step
        return suggestions

    def _suggest_cuts(
        self, allocation, actual_spend, deficit
    ) -> list[TradeoffSuggestion]:
        suggestions, remaining = [], deficit
        for category in _CUT_PRIORITY:
            if remaining <= 0:
                break
            current = actual_spend.get(category, 0.0)
            floor = allocation.get(category).min_required
            headroom = max(current - floor, 0.0)
            if headroom <= 0:
                continue
            step = min(headroom, current * 0.20, remaining)
            if step < 1:
                continue
            suggestions.append(
                TradeoffSuggestion(category, "cut", current, current - step, -step)
            )
            remaining -= step
        return suggestions
