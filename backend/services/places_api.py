"""
Google Places API (New) client.

Two endpoints, routed per-row:
  - Path A (Place Details): used when the source row already has a Google
    Place ID. Deterministic lookup, no verification gate needed.
  - Path B (Text Search): used when there's no Place ID. Queries
    "{name}, {address}" with a location bias circle around the source
    coordinates, then the caller runs the result through the verification
    gate in utils.matching before trusting it.

Field masks are kept minimal on purpose - Google bills by requested field,
and userRatingCount/photos push the request into the Enterprise SKU, so we
only ever ask for the 8 fields the pipeline actually uses.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import requests

PLACE_DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"
TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# Text Search responses are nested under "places[].<field>", so the mask
# needs the "places." prefix. Place Details returns a single object, so the
# prefix must be dropped or the API rejects the request.
SEARCH_FIELD_MASK = (
    "places.id,places.displayName,places.location,places.rating,"
    "places.userRatingCount,places.websiteUri,places.businessStatus,"
    "places.photos,places.pureServiceAreaBusiness"
)
DETAILS_FIELD_MASK = (
    "id,displayName,location,rating,userRatingCount,websiteUri,"
    "businessStatus,photos,pureServiceAreaBusiness"
)

REQUEST_TIMEOUT_S = 10


@dataclass
class PlaceResult:
    """Normalized shape both API paths get squeezed into."""

    place_id: Optional[str] = None
    name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    rating: Optional[float] = None
    user_rating_count: Optional[int] = None
    website_uri: Optional[str] = None
    business_status: Optional[str] = None
    photos: Optional[list] = None
    pure_service_area_business: Optional[bool] = None

    @classmethod
    def from_api_json(cls, data: dict[str, Any]) -> "PlaceResult":
        location = data.get("location") or {}
        display_name = data.get("displayName") or {}
        return cls(
            place_id=data.get("id"),
            name=display_name.get("text"),
            latitude=location.get("latitude"),
            longitude=location.get("longitude"),
            rating=data.get("rating"),
            user_rating_count=data.get("userRatingCount", 0),
            website_uri=data.get("websiteUri"),
            business_status=data.get("businessStatus"),
            photos=data.get("photos"),
            pure_service_area_business=data.get("pureServiceAreaBusiness", False),
        )


class PlacesAPIError(Exception):
    """Wraps any HTTP/JSON failure so the pipeline can log it per-row."""


class PlacesClient:
    def __init__(self, api_key: str, location_bias_radius_m: float = 500.0):
        self.api_key = api_key
        self.location_bias_radius_m = location_bias_radius_m

    def get_place_details(self, place_id: str) -> PlaceResult:
        """Path A - deterministic lookup by an existing Place ID."""
        url = PLACE_DETAILS_URL.format(place_id=place_id)
        headers = {
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": DETAILS_FIELD_MASK,
        }
        try:
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_S)
            response.raise_for_status()
            return PlaceResult.from_api_json(response.json())
        except requests.RequestException as err:
            raise PlacesAPIError(str(err)) from err

    def search_text(
        self,
        name: str,
        address: str,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
    ) -> Optional[PlaceResult]:
        """Path B - free-text search, optionally biased around a coordinate."""
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": SEARCH_FIELD_MASK,
        }
        query = f"{name}, {address}".strip(", ")
        payload: dict[str, Any] = {"textQuery": query}
        if lat is not None and lng is not None:
            payload["locationBias"] = {
                "circle": {
                    "center": {"latitude": float(lat), "longitude": float(lng)},
                    "radius": self.location_bias_radius_m,
                }
            }
        try:
            response = requests.post(
                TEXT_SEARCH_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT_S
            )
            response.raise_for_status()
            places = response.json().get("places", [])
            return PlaceResult.from_api_json(places[0]) if places else None
        except requests.RequestException as err:
            raise PlacesAPIError(str(err)) from err
