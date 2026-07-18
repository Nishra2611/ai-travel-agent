"""
ai_travel_agent/geo/geo_clustering.py — Week 9

Groups attractions/restaurants/hotel into walkable zones so build_itinerary
(Week 5/6) can eventually favor same-cluster activities on the same day
instead of zig-zagging across a city. Deterministic clustering (DBSCAN),
same reasoning as slot assignment and budget allocation: this is a
well-defined geometric problem with a correct, verifiable answer -- an LLM
adds nothing but latency here.

_GeoClusterBuilder has zero LangChain/FastAPI dependencies, same pattern as
_ItineraryBuilder and _BudgetOptimizer: instantiate and unit-test it
directly with _GeoClusterBuilder().cluster(points), no mocking required.

Uses DBSCAN over k-means because a city's attractions are naturally uneven
density (a museum quarter is dense, a single out-of-town chateau is not),
and DBSCAN's noise category is the correct behavior for that second case --
k-means would be forced to assign the outlier to whichever cluster is
"least wrong," which then corrupts build_itinerary's day-grouping logic.

Drop this file at: ai_travel_agent/geo/geo_clustering.py
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
from sklearn.cluster import DBSCAN, KMeans
from sklearn.metrics import silhouette_score

from ai_travel_agent.geo.distance_matrix_client import GeoPoint
from ai_travel_agent.utils.logger import get_logger

logger = get_logger(__name__)

EARTH_RADIUS_METERS = 6_371_000

# Tuned against 3-city mock fixtures (Paris/Tokyo/New York) -- an initial
# 800m/3 default flagged 33-53% of Tokyo/NYC points as noise, too
# aggressive for city-center POI density. 1200m/2 gives 6-13% noise and
# 0.70-0.81 silhouette across all three. Re-verify against real geocoded
# data with scripts/verify_clustering_quality.py before trusting these on
# a new city.
DEFAULT_EPS_METERS = 1200.0
DEFAULT_MIN_SAMPLES = 2

CLUSTER_COLORS = [
    "#e6194B",
    "#3cb44b",
    "#4363d8",
    "#f58231",
    "#911eb4",
    "#42d4f4",
    "#f032e6",
    "#bfef45",
    "#469990",
    "#9A6324",
]


@dataclass
class GeoCluster:
    cluster_id: int
    label: str
    points: list[GeoPoint]
    centroid_lat: float
    centroid_lng: float
    color_hex: str = "#3388ff"


@dataclass
class ClusteringResult:
    city: str
    algorithm: Literal["dbscan", "kmeans"]
    clusters: list[GeoCluster] = field(default_factory=list)
    noise_points: list[GeoPoint] = field(default_factory=list)
    silhouette_score: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "city": self.city,
            "algorithm": self.algorithm,
            "silhouette_score": self.silhouette_score,
            "clusters": [
                {
                    "cluster_id": c.cluster_id,
                    "label": c.label,
                    "color": c.color_hex,
                    "centroid": {"lat": c.centroid_lat, "lng": c.centroid_lng},
                    "point_ids": [p.id for p in c.points],
                }
                for c in self.clusters
            ],
            "noise_point_ids": [p.id for p in self.noise_points],
        }


class _GeoClusterBuilder:
    """Internal, dependency-free clustering engine. See module docstring."""

    def cluster(
        self,
        city: str,
        points: list[GeoPoint],
        algorithm: Literal["dbscan", "kmeans"] = "dbscan",
        eps_meters: float = DEFAULT_EPS_METERS,
        min_samples: int = DEFAULT_MIN_SAMPLES,
        kmeans_k: int | None = None,
    ) -> ClusteringResult:
        if len(points) < 3:
            # Not an error -- a 1-2 attraction trip doesn't need clustering,
            # just return everything as a single implicit cluster.
            logger.info(
                "too few points to cluster meaningfully, returning single group"
            )
            if not points:
                return ClusteringResult(city=city, algorithm=algorithm)
            return ClusteringResult(
                city=city,
                algorithm=algorithm,
                clusters=[self._single_cluster(points)],
            )

        coords_rad = np.radians([[p.latitude, p.longitude] for p in points])

        if algorithm == "dbscan":
            labels = self._run_dbscan(coords_rad, eps_meters, min_samples)
        else:
            k = kmeans_k or max(2, min(8, round(len(points) / 7)))
            labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(
                coords_rad
            )

        clusters, noise = self._build_clusters(points, labels)
        score = self._safe_silhouette(coords_rad, labels)

        logger.info(
            "clustering complete",
            extra={
                "city": city,
                "algorithm": algorithm,
                "clusters": len(clusters),
                "noise": len(noise),
            },
        )
        return ClusteringResult(
            city=city,
            algorithm=algorithm,
            clusters=clusters,
            noise_points=noise,
            silhouette_score=score,
        )

    @staticmethod
    def _single_cluster(points: list[GeoPoint]) -> GeoCluster:
        lat = sum(p.latitude for p in points) / len(points)
        lng = sum(p.longitude for p in points) / len(points)
        return GeoCluster(
            cluster_id=0,
            label=f"All spots ({len(points)})",
            points=points,
            centroid_lat=lat,
            centroid_lng=lng,
            color_hex=CLUSTER_COLORS[0],
        )

    @staticmethod
    def _run_dbscan(
        coords_rad: np.ndarray, eps_meters: float, min_samples: int
    ) -> np.ndarray:
        eps_rad = eps_meters / EARTH_RADIUS_METERS
        return DBSCAN(
            eps=eps_rad, min_samples=min_samples, metric="haversine"
        ).fit_predict(coords_rad)

    @staticmethod
    def _build_clusters(
        points: list[GeoPoint], labels: np.ndarray
    ) -> tuple[list[GeoCluster], list[GeoPoint]]:
        clusters, noise = [], []
        color_cycle = itertools.cycle(CLUSTER_COLORS)
        for label in sorted(set(labels)):
            members = [
                point
                for point, point_label in zip(points, labels)
                if point_label == label
            ]
            # members = [p for p, l in zip(points, labels) if l == label]
            if label == -1:
                noise.extend(members)
                continue
            lat = sum(p.latitude for p in members) / len(members)
            lng = sum(p.longitude for p in members) / len(members)
            clusters.append(
                GeoCluster(
                    cluster_id=int(label),
                    label=f"Zone {int(label) + 1} ({len(members)} spots)",
                    points=members,
                    centroid_lat=lat,
                    centroid_lng=lng,
                    color_hex=next(color_cycle),
                )
            )
        return clusters, noise

    @staticmethod
    def _safe_silhouette(coords_rad: np.ndarray, labels: np.ndarray) -> float | None:
        mask = labels != -1
        if len(set(labels[mask])) < 2 or mask.sum() < 3:
            return None
        try:
            return round(
                float(
                    silhouette_score(coords_rad[mask], labels[mask], metric="haversine")
                ),
                3,
            )
        except ValueError:
            return None
