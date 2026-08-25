"""
Sehat Saathi - Healthcare Facility Locator Tool
================================================
Finds nearby PHCs, hospitals, and health centres using:
  1. Google Places API (if API key is configured)
  2. OpenStreetMap Overpass API (free fallback, no key required)
"""
import logging
import httpx
from typing import Optional
from langchain_core.tools import tool
from app.config import settings

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
GOOGLE_PLACES_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

# India pincode geocode API (free, no key required)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


async def _geocode_pincode(pincode: str) -> Optional[tuple[float, float]]:
    """Convert an Indian pincode to (lat, lon) using Nominatim."""
    params = {
        "q": f"{pincode}, India",
        "format": "json",
        "limit": 1,
    }
    headers = {"User-Agent": "SehatSaathi/1.0 (healthcare-awareness-app)"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(NOMINATIM_URL, params=params, headers=headers)
        resp.raise_for_status()
        results = resp.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    return None


async def _search_osm_facilities(lat: float, lon: float, radius_m: int = 5000) -> list[dict]:
    """Search OpenStreetMap for healthcare facilities near (lat, lon)."""
    query = f"""
    [out:json][timeout:25];
    (
      node["amenity"="hospital"](around:{radius_m},{lat},{lon});
      node["amenity"="clinic"](around:{radius_m},{lat},{lon});
      node["amenity"="health_post"](around:{radius_m},{lat},{lon});
      node["healthcare"="centre"](around:{radius_m},{lat},{lon});
      node["healthcare"="clinic"](around:{radius_m},{lat},{lon});
      node["healthcare"="hospital"](around:{radius_m},{lat},{lon});
      node["name"~"PHC|Primary Health|Community Health|CHC",i](around:{radius_m},{lat},{lon});
    );
    out body 10;
    """
    headers = {"User-Agent": "SehatSaathi/1.0"}
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(OVERPASS_URL, data={"data": query}, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    facilities = []
    for element in data.get("elements", []):
        tags = element.get("tags", {})
        name = tags.get("name", "Unnamed Health Facility")
        facility_type = tags.get("amenity") or tags.get("healthcare", "health_facility")
        phone = tags.get("phone") or tags.get("contact:phone", "Not listed")
        address_parts = [
            tags.get("addr:housenumber", ""),
            tags.get("addr:street", ""),
            tags.get("addr:city", ""),
            tags.get("addr:state", ""),
        ]
        address = ", ".join(p for p in address_parts if p) or "Address not available"
        facilities.append(
            {
                "name": name,
                "type": facility_type,
                "phone": phone,
                "address": address,
                "lat": element.get("lat"),
                "lon": element.get("lon"),
            }
        )
    return facilities


async def _search_google_places(lat: float, lon: float) -> list[dict]:
    """Search Google Places API for nearby hospitals/clinics."""
    params = {
        "location": f"{lat},{lon}",
        "radius": 5000,
        "type": "hospital",
        "key": settings.google_places_api_key,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(GOOGLE_PLACES_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    facilities = []
    for place in data.get("results", [])[:8]:
        facilities.append(
            {
                "name": place.get("name", "Unknown"),
                "type": "hospital",
                "address": place.get("vicinity", "Address not available"),
                "rating": place.get("rating"),
                "open_now": place.get("opening_hours", {}).get("open_now"),
                "place_id": place.get("place_id"),
            }
        )
    return facilities


def _format_facilities(facilities: list[dict], location_label: str) -> str:
    """Format facility list into a user-friendly response."""
    if not facilities:
        return (
            f"I couldn't find any health facilities near **{location_label}** in my database.\n\n"
            "Please try:\n"
            "- Calling the **National Health Helpline: 104** for facility information\n"
            "- Visiting the nearest Anganwadi worker or ASHA worker in your village\n"
            "- Checking https://hfr.abdm.gov.in (Health Facility Registry, India)\n\n"
            "_I'm an AI assistant, not a doctor. For diagnosis or treatment, please consult a healthcare professional._"
        )

    lines = [
        f"🏥 **Nearby Health Facilities near {location_label}:**",
        "",
    ]

    for i, f in enumerate(facilities[:6], 1):
        lines.append(f"**{i}. {f['name']}**")
        lines.append(f"   📍 Type: {f.get('type', 'Health Facility').replace('_', ' ').title()}")
        if f.get("address"):
            lines.append(f"   🗺️ Address: {f['address']}")
        if f.get("phone") and f["phone"] != "Not listed":
            lines.append(f"   📞 Phone: {f['phone']}")
        if f.get("rating"):
            lines.append(f"   ⭐ Rating: {f['rating']}/5")
        lines.append("")

    lines += [
        "💡 **Tip:** Government PHCs (Primary Health Centres) provide **free consultations** "
        "and medicines under the National Health Mission.",
        "",
        "📞 **National Health Helpline: 104** — for health information and facility guidance.",
        "",
        "_I'm an AI assistant, not a doctor. For diagnosis or treatment, please consult a healthcare professional._",
    ]
    return "\n".join(lines)


@tool
def facility_locator_tool(location: str) -> str:
    """
    Finds nearby healthcare facilities (PHCs, hospitals, clinics) for the given
    location or Indian pincode. Returns facility names, addresses, and contact details.

    Args:
        location: A location description — can be an Indian pincode (e.g., '110001'),
                  a city name, or a district/village name.
    """
    import asyncio

    logger.info("Facility locator requested for: %s", location)

    async def _run():
        # Step 1: Geocode location
        coords = None
        if location.strip().isdigit() and len(location.strip()) == 6:
            coords = await _geocode_pincode(location.strip())
        else:
            # Try geocoding by name
            params = {"q": f"{location}, India", "format": "json", "limit": 1}
            headers = {"User-Agent": "SehatSaathi/1.0"}
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(NOMINATIM_URL, params=params, headers=headers)
                results = resp.json()
                if results:
                    coords = (float(results[0]["lat"]), float(results[0]["lon"]))

        if not coords:
            return (
                f"I wasn't able to find the location **'{location}'** on the map.\n\n"
                "Please try:\n"
                "- Providing your 6-digit pincode (e.g., 110001)\n"
                "- Giving your district or city name\n\n"
                "Alternatively, call **104** (National Health Helpline) for facility information."
            )

        lat, lon = coords

        # Step 2: Try Google Places first (better data), fall back to OSM
        facilities = []
        if settings.google_places_api_key:
            try:
                facilities = await _search_google_places(lat, lon)
            except Exception as e:
                logger.warning("Google Places failed, falling back to OSM: %s", e)

        if not facilities:
            try:
                facilities = await _search_osm_facilities(lat, lon)
            except Exception as e:
                logger.error("OSM search failed: %s", e)

        return _format_facilities(facilities, location)

    return asyncio.run(_run())
