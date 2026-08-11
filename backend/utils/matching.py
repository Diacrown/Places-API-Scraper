"""
Match verification utilities.

Two independent checks decide whether a Google Places API result is allowed
to overwrite/enrich a source row:

  1. Haversine distance between the source coordinates and the API result's
     coordinates (meters).
  2. Normalized string similarity between the source name and the API
     result's display name (0.0-1.0, via difflib.SequenceMatcher).

Both must pass their threshold for a result to be treated as verified.
This mirrors the gate used across the Krakow / Toscana / Wroclaw scripts.
"""
from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional


EARTH_RADIUS_M = 6371000.0


def haversine_distance_m(
    lat1: Optional[float],
    lon1: Optional[float],
    lat2: Optional[float],
    lon2: Optional[float],
) -> float:
    """Great-circle distance between two lat/lng pairs, in meters.

    Returns float('inf') if either point is missing/invalid so that a
    verification gate comparing against a max-distance threshold fails
    safely instead of raising.
    """
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return float("inf")
    try:
        phi1, phi2 = math.radians(float(lat1)), math.radians(float(lat2))
        delta_phi = math.radians(float(lat2) - float(lat1))
        delta_lambda = math.radians(float(lon2) - float(lon1))
        a = (
            math.sin(delta_phi / 2.0) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
        )
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return EARTH_RADIUS_M * c
    except (TypeError, ValueError):
        return float("inf")


def normalize_for_matching(text: Optional[str]) -> str:
    """Lowercase, strip diacritics, and drop punctuation for comparison."""
    if not text:
        return ""
    text = str(text)
    normalized = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in normalized if not unicodedata.combining(c))
    return re.sub(r"[^\w\s]", "", stripped.lower()).strip()


def name_similarity(name1: Optional[str], name2: Optional[str]) -> float:
    """Normalized SequenceMatcher similarity ratio, 0.0-1.0."""
    c1, c2 = normalize_for_matching(name1), normalize_for_matching(name2)
    if not c1 or not c2:
        return 0.0
    return SequenceMatcher(None, c1, c2).ratio()


@dataclass
class VerificationResult:
    passed: bool
    distance_m: float
    similarity: float

    @property
    def flag_text(self) -> str:
        """The 'manual check (Xm, 0.XX)' string used across every mode."""
        dist_display = "?" if math.isinf(self.distance_m) else str(int(self.distance_m))
        return f"manual check ({dist_display}m, {self.similarity:.2f})"


def verify_match(
    source_lat: Optional[float],
    source_lng: Optional[float],
    source_name: Optional[str],
    result_lat: Optional[float],
    result_lng: Optional[float],
    result_name: Optional[str],
    max_distance_m: float = 150.0,
    min_similarity: float = 0.55,
) -> VerificationResult:
    """Run both gate checks and report the outcome plus the raw figures."""
    distance_m = haversine_distance_m(source_lat, source_lng, result_lat, result_lng)
    similarity = name_similarity(source_name, result_name)
    passed = distance_m <= max_distance_m and similarity >= min_similarity
    return VerificationResult(passed=passed, distance_m=distance_m, similarity=similarity)


def format_photo_count(photos: Optional[list]) -> str:
    """Exact count for 0-4 photos, '5+' string for 5 or more."""
    if not photos or not isinstance(photos, list):
        return "0"
    count = len(photos)
    return str(count) if count < 5 else "5+"
