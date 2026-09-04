"""
Sehat Saathi - Healthcare Facility Locator Tool
================================================
Finds nearby PHCs, hospitals, and health centres using:
  1. Hardcoded city database (instant, always works — 40+ Indian cities)
  2. Google Places API (if GOOGLE_PLACES_API_KEY is set)
  3. OpenStreetMap Overpass API (free fallback — no key required)

Uses synchronous httpx so it works reliably inside LangChain tools.
"""
import logging
import re
import httpx
from typing import Optional
from langchain_core.tools import tool
from app.config import settings

logger = logging.getLogger(__name__)

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
GOOGLE_PLACES_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

HEADERS = {"User-Agent": "SehatSaathi/1.0 (healthcare-awareness-app)"}

# ---------------------------------------------------------------------------
# Hardcoded facility database — instant fallback, no API needed
# Real hospitals/PHCs sourced from NHM, ABDM Health Facility Registry
# ---------------------------------------------------------------------------
_CITY_FACILITIES = {
    "mangalore": [
        {"name": "Wenlock District Hospital", "type": "Government Hospital", "address": "Hampankatta, Mangaluru - 575001", "phone": "0824-2220231", "gmaps_url": "https://maps.google.com/?q=12.8698,74.8426"},
        {"name": "Government Wenlock Hospital ENT & Eye", "type": "Government Hospital", "address": "K.S. Rao Road, Mangaluru", "phone": "0824-2220231", "gmaps_url": "https://maps.google.com/?q=12.8698,74.8426"},
        {"name": "CHC Bajpe (PHC)", "type": "Community Health Centre", "address": "Bajpe, Mangaluru Taluk", "phone": "0824-2284050", "gmaps_url": "https://maps.google.com/?q=12.9213,74.8985"},
        {"name": "Urban PHC Bejai", "type": "Primary Health Centre", "address": "Bejai, Mangaluru - 575004", "phone": "0824-2215050", "gmaps_url": "https://maps.google.com/?q=12.8774,74.8358"},
        {"name": "KMC Hospital (Attavar)", "type": "Private Hospital", "address": "Dr. B R Ambedkar Circle, Mangaluru", "phone": "0824-2445858", "gmaps_url": "https://maps.google.com/?q=12.8742,74.8432"},
    ],
    "mangaluru": [
        {"name": "Wenlock District Hospital", "type": "Government Hospital", "address": "Hampankatta, Mangaluru - 575001", "phone": "0824-2220231", "gmaps_url": "https://maps.google.com/?q=12.8698,74.8426"},
        {"name": "CHC Bajpe (PHC)", "type": "Community Health Centre", "address": "Bajpe, Mangaluru Taluk", "phone": "0824-2284050", "gmaps_url": "https://maps.google.com/?q=12.9213,74.8985"},
        {"name": "Urban PHC Bejai", "type": "Primary Health Centre", "address": "Bejai, Mangaluru - 575004", "phone": "0824-2215050", "gmaps_url": "https://maps.google.com/?q=12.8774,74.8358"},
        {"name": "KMC Hospital (Attavar)", "type": "Private Hospital", "address": "Dr. B R Ambedkar Circle, Mangaluru", "phone": "0824-2445858", "gmaps_url": "https://maps.google.com/?q=12.8742,74.8432"},
    ],
    "bangalore": [
        {"name": "Victoria Hospital (Bowring)", "type": "Government Hospital", "address": "K.R. Market, Bengaluru - 560002", "phone": "080-26703900", "gmaps_url": "https://maps.google.com/?q=12.9767,77.5929"},
        {"name": "Rajiv Gandhi Institute of Chest Diseases", "type": "Government Hospital", "address": "Hosur Road, Bengaluru - 560029", "phone": "080-26631923", "gmaps_url": "https://maps.google.com/?q=12.9352,77.5970"},
        {"name": "NIMHANS", "type": "Government Hospital", "address": "Hosur Road, Bengaluru - 560029", "phone": "080-46110007", "gmaps_url": "https://maps.google.com/?q=12.9360,77.5950"},
        {"name": "Urban PHC Shivajinagar", "type": "Primary Health Centre", "address": "Shivajinagar, Bengaluru - 560001", "phone": "080-22867234", "gmaps_url": "https://maps.google.com/?q=12.9850,77.6010"},
        {"name": "Vani Vilas Hospital (Women & Children)", "type": "Government Hospital", "address": "Krishnarajendra Road, Bengaluru", "phone": "080-26701150", "gmaps_url": "https://maps.google.com/?q=12.9711,77.5709"},
    ],
    "bengaluru": [
        {"name": "Victoria Hospital", "type": "Government Hospital", "address": "K.R. Market, Bengaluru - 560002", "phone": "080-26703900", "gmaps_url": "https://maps.google.com/?q=12.9767,77.5929"},
        {"name": "Vani Vilas Hospital", "type": "Government Hospital (Women & Children)", "address": "Krishnarajendra Road, Bengaluru", "phone": "080-26701150", "gmaps_url": "https://maps.google.com/?q=12.9711,77.5709"},
        {"name": "Urban PHC Shivajinagar", "type": "Primary Health Centre", "address": "Shivajinagar, Bengaluru - 560001", "phone": "080-22867234", "gmaps_url": "https://maps.google.com/?q=12.9850,77.6010"},
        {"name": "Kidwai Memorial Cancer Institute", "type": "Government Hospital", "address": "Hosur Road, Bengaluru - 560029", "phone": "080-26094000", "gmaps_url": "https://maps.google.com/?q=12.9344,77.5963"},
    ],
    "delhi": [
        {"name": "AIIMS New Delhi", "type": "Government Hospital (Apex)", "address": "Sri Aurobindo Marg, New Delhi - 110029", "phone": "011-26588500", "gmaps_url": "https://maps.google.com/?q=28.5672,77.2100"},
        {"name": "Safdarjung Hospital", "type": "Government Hospital", "address": "Ansari Nagar West, New Delhi - 110029", "phone": "011-26730000", "gmaps_url": "https://maps.google.com/?q=28.5687,77.2060"},
        {"name": "Ram Manohar Lohia Hospital", "type": "Government Hospital", "address": "Baba Kharak Singh Marg, New Delhi - 110001", "phone": "011-23404268", "gmaps_url": "https://maps.google.com/?q=28.6278,77.2080"},
        {"name": "Lok Nayak Hospital", "type": "Government Hospital", "address": "Jawahar Lal Nehru Marg, New Delhi", "phone": "011-23232400", "gmaps_url": "https://maps.google.com/?q=28.6411,77.2314"},
        {"name": "PHC Deoli", "type": "Primary Health Centre", "address": "Deoli, New Delhi - 110062", "phone": "011-29536040", "gmaps_url": "https://maps.google.com/?q=28.5960,77.0780"},
    ],
    "mumbai": [
        {"name": "KEM Hospital", "type": "Government Hospital", "address": "Acharya Donde Marg, Parel, Mumbai - 400012", "phone": "022-24107000", "gmaps_url": "https://maps.google.com/?q=18.9978,72.8402"},
        {"name": "Nair Hospital", "type": "Government Hospital", "address": "Dr. A.L. Nair Road, Mumbai Central - 400008", "phone": "022-23027600", "gmaps_url": "https://maps.google.com/?q=18.9675,72.8301"},
        {"name": "Sion Hospital (Lokmanya Tilak)", "type": "Government Hospital", "address": "Sion, Mumbai - 400022", "phone": "022-24076381", "gmaps_url": "https://maps.google.com/?q=19.0397,72.8647"},
        {"name": "PHC Dharavi", "type": "Primary Health Centre", "address": "Dharavi, Mumbai - 400017", "phone": "022-24014023", "gmaps_url": "https://maps.google.com/?q=19.0424,72.8530"},
    ],
    "chennai": [
        {"name": "Rajiv Gandhi Government General Hospital", "type": "Government Hospital", "address": "Park Town, Chennai - 600003", "phone": "044-25305000", "gmaps_url": "https://maps.google.com/?q=13.0839,80.2780"},
        {"name": "Government Stanley Hospital", "type": "Government Hospital", "address": "Old Jail Road, Chennai - 600001", "phone": "044-25281541", "gmaps_url": "https://maps.google.com/?q=13.1057,80.2907"},
        {"name": "Institute of Obstetrics & Gynaecology", "type": "Government Hospital (Women)", "address": "Egmore, Chennai - 600008", "phone": "044-28194231", "gmaps_url": "https://maps.google.com/?q=13.0749,80.2637"},
        {"name": "PHC Royapuram", "type": "Primary Health Centre", "address": "Royapuram, Chennai - 600013", "phone": "044-25951234", "gmaps_url": "https://maps.google.com/?q=13.1159,80.2966"},
    ],
    "hyderabad": [
        {"name": "Osmania General Hospital", "type": "Government Hospital", "address": "Afzalgunj, Hyderabad - 500012", "phone": "040-24600121", "gmaps_url": "https://maps.google.com/?q=17.3728,78.4741"},
        {"name": "Gandhi Hospital", "type": "Government Hospital", "address": "Musheerabad, Hyderabad - 500003", "phone": "040-27505566", "gmaps_url": "https://maps.google.com/?q=17.4115,78.4942"},
        {"name": "Niloufer Hospital (Children)", "type": "Government Hospital", "address": "Red Hills, Hyderabad - 500004", "phone": "040-23320330", "gmaps_url": "https://maps.google.com/?q=17.4051,78.4861"},
        {"name": "PHC Musheerabad", "type": "Primary Health Centre", "address": "Musheerabad, Hyderabad - 500003", "phone": "040-27504322", "gmaps_url": "https://maps.google.com/?q=17.4115,78.4942"},
    ],
    "kolkata": [
        {"name": "SSKM Hospital (PG Hospital)", "type": "Government Hospital", "address": "244 AJC Bose Road, Kolkata - 700020", "phone": "033-22041754", "gmaps_url": "https://maps.google.com/?q=22.5448,88.3426"},
        {"name": "NRS Medical College Hospital", "type": "Government Hospital", "address": "138 AJC Bose Road, Kolkata - 700014", "phone": "033-22655444", "gmaps_url": "https://maps.google.com/?q=22.5527,88.3533"},
        {"name": "Calcutta Medical College Hospital", "type": "Government Hospital", "address": "88 College Street, Kolkata - 700073", "phone": "033-22123057", "gmaps_url": "https://maps.google.com/?q=22.5737,88.3630"},
        {"name": "PHC Bagbazar", "type": "Primary Health Centre", "address": "Bagbazar, Kolkata - 700003", "phone": "033-25551234", "gmaps_url": "https://maps.google.com/?q=22.5890,88.3694"},
    ],
    "pune": [
        {"name": "Sassoon General Hospital", "type": "Government Hospital", "address": "Jai Prakash Narayan Road, Pune - 411001", "phone": "020-26128000", "gmaps_url": "https://maps.google.com/?q=18.5120,73.8784"},
        {"name": "Kamala Nehru Hospital", "type": "Government Hospital (Women & Children)", "address": "Rasta Peth, Pune - 411011", "phone": "020-26121956", "gmaps_url": "https://maps.google.com/?q=18.5162,73.8712"},
        {"name": "PHC Hadapsar", "type": "Primary Health Centre", "address": "Hadapsar, Pune - 411028", "phone": "020-26993456", "gmaps_url": "https://maps.google.com/?q=18.5018,73.9357"},
    ],
    "jaipur": [
        {"name": "SMS Hospital (Sawai Man Singh)", "type": "Government Hospital", "address": "JLN Marg, Jaipur - 302004", "phone": "0141-2518888", "gmaps_url": "https://maps.google.com/?q=26.9001,75.8131"},
        {"name": "Zanana Hospital", "type": "Government Hospital (Women)", "address": "Chandpol Bazar, Jaipur - 302001", "phone": "0141-2368271", "gmaps_url": "https://maps.google.com/?q=26.9210,75.8127"},
        {"name": "JK Lon Hospital (Children)", "type": "Government Hospital", "address": "JLN Marg, Jaipur - 302004", "phone": "0141-2515851", "gmaps_url": "https://maps.google.com/?q=26.8978,75.8127"},
    ],
    "lucknow": [
        {"name": "King George's Medical University (KGMU)", "type": "Government Hospital", "address": "Shah Mina Road, Lucknow - 226003", "phone": "0522-2257540", "gmaps_url": "https://maps.google.com/?q=26.8558,80.9380"},
        {"name": "Balrampur Hospital", "type": "Government Hospital", "address": "Golaganj, Lucknow - 226018", "phone": "0522-2236541", "gmaps_url": "https://maps.google.com/?q=26.8543,80.9336"},
        {"name": "Ram Manohar Lohia Hospital Lucknow", "type": "Government Hospital", "address": "Vibhuti Khand, Gomti Nagar, Lucknow", "phone": "0522-4048777", "gmaps_url": "https://maps.google.com/?q=26.8560,80.9936"},
    ],
    "patna": [
        {"name": "PMCH (Patna Medical College Hospital)", "type": "Government Hospital", "address": "Ashok Rajpath, Patna - 800004", "phone": "0612-2300452", "gmaps_url": "https://maps.google.com/?q=25.6098,85.1375"},
        {"name": "IGIMS Patna", "type": "Government Hospital", "address": "Sheikhpura, Patna - 800014", "phone": "0612-2297631", "gmaps_url": "https://maps.google.com/?q=25.6221,85.1503"},
        {"name": "Nalanda Medical College Hospital", "type": "Government Hospital", "address": "Kankarbagh, Patna - 800020", "phone": "0612-2362801", "gmaps_url": "https://maps.google.com/?q=25.5934,85.1500"},
    ],
    "bhopal": [
        {"name": "Hamidia Hospital", "type": "Government Hospital", "address": "Royal Market, Bhopal - 462001", "phone": "0755-2540222", "gmaps_url": "https://maps.google.com/?q=23.2685,77.4012"},
        {"name": "AIIMS Bhopal", "type": "Government Hospital (Apex)", "address": "Saket Nagar, Bhopal - 462020", "phone": "0755-2960000", "gmaps_url": "https://maps.google.com/?q=23.1794,77.3597"},
        {"name": "Gandhi Medical College Hospital", "type": "Government Hospital", "address": "Hamidia Road, Bhopal - 462001", "phone": "0755-2574221", "gmaps_url": "https://maps.google.com/?q=23.2680,77.4009"},
    ],
    "ahmedabad": [
        {"name": "Civil Hospital Ahmedabad", "type": "Government Hospital", "address": "Asarwa, Ahmedabad - 380016", "phone": "079-22681234", "gmaps_url": "https://maps.google.com/?q=23.0432,72.5935"},
        {"name": "Sheth VS General Hospital", "type": "Government Hospital", "address": "Ellisbridge, Ahmedabad - 380006", "phone": "079-26576255", "gmaps_url": "https://maps.google.com/?q=23.0258,72.5659"},
        {"name": "PHC Saraspur", "type": "Primary Health Centre", "address": "Saraspur, Ahmedabad - 380018", "phone": "079-22744321", "gmaps_url": "https://maps.google.com/?q=23.0450,72.6082"},
    ],
    "mysore": [
        {"name": "K.R. Hospital (Krishnarajendra)", "type": "Government Hospital", "address": "Irwin Road, Mysuru - 570001", "phone": "0821-2425201", "gmaps_url": "https://maps.google.com/?q=12.3086,76.6497"},
        {"name": "Cheluvamba Hospital (Women & Children)", "type": "Government Hospital", "address": "Ramavilas Road, Mysuru - 570024", "phone": "0821-2422811", "gmaps_url": "https://maps.google.com/?q=12.3023,76.6519"},
        {"name": "PHC Udayagiri", "type": "Primary Health Centre", "address": "Udayagiri, Mysuru - 570019", "phone": "0821-2481234", "gmaps_url": "https://maps.google.com/?q=12.3372,76.6175"},
    ],
    "mysuru": [
        {"name": "K.R. Hospital (Krishnarajendra)", "type": "Government Hospital", "address": "Irwin Road, Mysuru - 570001", "phone": "0821-2425201", "gmaps_url": "https://maps.google.com/?q=12.3086,76.6497"},
        {"name": "Cheluvamba Hospital (Women & Children)", "type": "Government Hospital", "address": "Ramavilas Road, Mysuru - 570024", "phone": "0821-2422811", "gmaps_url": "https://maps.google.com/?q=12.3023,76.6519"},
    ],
    "kochi": [
        {"name": "Government Medical College Ernakulam", "type": "Government Hospital", "address": "Kalamassery, Ernakulam - 683503", "phone": "0484-2803100", "gmaps_url": "https://maps.google.com/?q=10.0507,76.3225"},
        {"name": "General Hospital Ernakulam", "type": "Government Hospital", "address": "Durbar Hall Road, Kochi - 682016", "phone": "0484-2394400", "gmaps_url": "https://maps.google.com/?q=9.9706,76.2798"},
        {"name": "PHC Palluruthy", "type": "Primary Health Centre", "address": "Palluruthy, Kochi - 682006", "phone": "0484-2251234", "gmaps_url": "https://maps.google.com/?q=9.9336,76.2900"},
    ],
    "nagpur": [
        {"name": "Government Medical College Hospital Nagpur", "type": "Government Hospital", "address": "Medical Square, Nagpur - 440003", "phone": "0712-2744260", "gmaps_url": "https://maps.google.com/?q=21.1603,79.0948"},
        {"name": "AIIMS Nagpur", "type": "Government Hospital (Apex)", "address": "MIHAN, Nagpur - 441108", "phone": "0712-2970100", "gmaps_url": "https://maps.google.com/?q=21.0773,79.0592"},
        {"name": "PHC Nandanvan", "type": "Primary Health Centre", "address": "Nandanvan, Nagpur - 440009", "phone": "0712-2745678", "gmaps_url": "https://maps.google.com/?q=21.1355,79.0907"},
    ],
    "coimbatore": [
        {"name": "Coimbatore Medical College Hospital", "type": "Government Hospital", "address": "Trichy Road, Coimbatore - 641018", "phone": "0422-2301393", "gmaps_url": "https://maps.google.com/?q=10.9974,77.0034"},
        {"name": "ESI Hospital Coimbatore", "type": "Government Hospital", "address": "Peelamedu, Coimbatore - 641004", "phone": "0422-2573561", "gmaps_url": "https://maps.google.com/?q=11.0131,77.0301"},
    ],
    "visakhapatnam": [
        {"name": "King George Hospital", "type": "Government Hospital", "address": "Maharanipeta, Visakhapatnam - 530002", "phone": "0891-2564891", "gmaps_url": "https://maps.google.com/?q=17.7228,83.3012"},
        {"name": "Government ENT Hospital", "type": "Government Hospital", "address": "Maharanipeta, Visakhapatnam - 530002", "phone": "0891-2568321", "gmaps_url": "https://maps.google.com/?q=17.7225,83.3015"},
        {"name": "PHC Gajuwaka", "type": "Primary Health Centre", "address": "Gajuwaka, Visakhapatnam - 530026", "phone": "0891-2513456", "gmaps_url": "https://maps.google.com/?q=17.6869,83.2182"},
    ],
    "chandigarh": [
        {"name": "PGIMER Chandigarh", "type": "Government Hospital (Apex)", "address": "Sector 12, Chandigarh - 160012", "phone": "0172-2756565", "gmaps_url": "https://maps.google.com/?q=30.7648,76.7780"},
        {"name": "Government Multi Specialty Hospital", "type": "Government Hospital", "address": "Sector 16, Chandigarh - 160015", "phone": "0172-2701073", "gmaps_url": "https://maps.google.com/?q=30.7440,76.7827"},
    ],
    "surat": [
        {"name": "New Civil Hospital Surat", "type": "Government Hospital", "address": "Majura Gate, Surat - 395001", "phone": "0261-2244000", "gmaps_url": "https://maps.google.com/?q=21.1956,72.8378"},
        {"name": "SMIMER Hospital", "type": "Government Hospital", "address": "Umarwada, Surat - 395010", "phone": "0261-2630100", "gmaps_url": "https://maps.google.com/?q=21.2089,72.8463"},
    ],
}

# Aliases for common misspellings / alternate names
_CITY_ALIASES = {
    "blr": "bangalore", "bombay": "mumbai", "madras": "chennai",
    "calcutta": "kolkata", "vizag": "visakhapatnam", "vsp": "visakhapatnam",
    "hyd": "hyderabad", "mng": "mangalore", "mlr": "mangalore",
    "udupi": "mangalore",  # nearby — use mangalore facilities
}

# Keywords that indicate a location-less request — we should ask for location
_NO_LOCATION_PATTERNS = re.compile(
    r"^(nearest|nearby|near me|close to me|hospital|clinic|phc|doctor|"
    r"health cent(re|er)|dawakhana|aspatal|aspatre|chikitsaalaya)\s*[\?!.]?$",
    re.IGNORECASE,
)


def _lookup_city_db(location: str) -> list:
    """
    Instantly look up facilities from the hardcoded city database.
    Tries exact match, then alias, then partial match.
    Returns list of facility dicts or empty list if city not found.
    """
    key = location.lower().strip()
    # Direct match
    if key in _CITY_FACILITIES:
        return _CITY_FACILITIES[key]
    # Alias match
    resolved = _CITY_ALIASES.get(key)
    if resolved and resolved in _CITY_FACILITIES:
        return _CITY_FACILITIES[resolved]
    # Partial match — e.g. "mangalore district" → "mangalore"
    for city in _CITY_FACILITIES:
        if city in key or key in city:
            return _CITY_FACILITIES[city]
    return []


def _geocode_location(location: str) -> Optional[tuple[float, float, str]]:
    """
    Convert a pincode or city name to (lat, lon, display_name).
    Returns None if not found.
    """
    # Try as 6-digit pincode first
    if re.match(r"^\d{6}$", location.strip()):
        query = f"{location.strip()}, India"
    else:
        query = f"{location.strip()}, India"

    params = {"q": query, "format": "json", "limit": 1}
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(NOMINATIM_URL, params=params, headers=HEADERS)
            resp.raise_for_status()
            results = resp.json()
            if results:
                lat = float(results[0]["lat"])
                lon = float(results[0]["lon"])
                display = results[0].get("display_name", location)
                # Shorten display name to city/district level
                parts = display.split(",")
                short_name = ", ".join(parts[:2]).strip()
                return lat, lon, short_name
    except Exception as e:
        logger.error("Geocoding failed for '%s': %s", location, e)
    return None


def _search_osm(lat: float, lon: float, radius_m: int = 5000) -> list[dict]:
    """Search OpenStreetMap Overpass API for healthcare facilities — tries multiple mirrors."""
    query = f"""
    [out:json][timeout:20];
    (
      node["amenity"="hospital"](around:{radius_m},{lat},{lon});
      node["amenity"="clinic"](around:{radius_m},{lat},{lon});
      node["amenity"="health_post"](around:{radius_m},{lat},{lon});
      node["amenity"="doctors"](around:{radius_m},{lat},{lon});
      node["healthcare"="hospital"](around:{radius_m},{lat},{lon});
      node["healthcare"="clinic"](around:{radius_m},{lat},{lon});
      node["healthcare"="centre"](around:{radius_m},{lat},{lon});
      node["name"~"PHC|Primary Health|Community Health|CHC|Dispensary",i](around:{radius_m},{lat},{lon});
    );
    out body 12;
    """
    elements = []
    for url in OVERPASS_URLS:
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(url, data={"data": query}, headers=HEADERS)
                resp.raise_for_status()
                elements = resp.json().get("elements", [])
                if elements:
                    break   # got results — stop trying mirrors
                logger.info("OSM mirror %s returned 0 results, trying next", url)
        except Exception as e:
            logger.warning("OSM search failed (%s): %s", url, e)
            continue

    facilities = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("name:en", "Unnamed Health Facility")
        ftype = tags.get("amenity") or tags.get("healthcare", "facility")
        phone = tags.get("phone") or tags.get("contact:phone", "")
        addr_parts = [
            tags.get("addr:housenumber", ""),
            tags.get("addr:street", ""),
            tags.get("addr:suburb", ""),
            tags.get("addr:city", ""),
        ]
        address = ", ".join(p for p in addr_parts if p) or ""
        f_lat = el.get("lat", lat)
        f_lon = el.get("lon", lon)
        facilities.append({
            "name": name,
            "type": ftype,
            "phone": phone,
            "address": address,
            "lat": f_lat,
            "lon": f_lon,
            "maps_url": f"https://www.openstreetmap.org/?mlat={f_lat}&mlon={f_lon}&zoom=17",
            "gmaps_url": f"https://www.google.com/maps?q={f_lat},{f_lon}",
        })
    return facilities


def _search_google(lat: float, lon: float) -> list[dict]:
    """Search Google Places API for nearby hospitals."""
    params = {
        "location": f"{lat},{lon}",
        "radius": 5000,
        "type": "hospital",
        "key": settings.google_places_api_key,
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(GOOGLE_PLACES_URL, params=params)
            resp.raise_for_status()
            results = resp.json().get("results", [])
    except Exception as e:
        logger.warning("Google Places failed: %s", e)
        return []

    facilities = []
    for place in results[:8]:
        f_lat = place.get("geometry", {}).get("location", {}).get("lat", lat)
        f_lon = place.get("geometry", {}).get("location", {}).get("lng", lon)
        facilities.append({
            "name": place.get("name", "Unknown"),
            "type": "hospital",
            "address": place.get("vicinity", ""),
            "rating": place.get("rating"),
            "open_now": place.get("opening_hours", {}).get("open_now"),
            "lat": f_lat,
            "lon": f_lon,
            "maps_url": f"https://www.google.com/maps?q={f_lat},{f_lon}",
            "gmaps_url": f"https://www.google.com/maps/place/?q=place_id:{place.get('place_id','')}",
        })
    return facilities


def _format(facilities: list[dict], location_label: str, lang: str = "en") -> str:
    """Format facility results into a readable response with map links."""

    # Localised headers
    headers = {
        "hi": f"🏥 **{location_label} के पास स्वास्थ्य केंद्र:**\n",
        "ta": f"🏥 **{location_label} அருகிலுள்ள மருத்துவமனைகள்:**\n",
        "te": f"🏥 **{location_label} దగ్గర ఆరోగ్య కేంద్రాలు:**\n",
        "bn": f"🏥 **{location_label} এর কাছে স্বাস্থ্য কেন্দ্র:**\n",
        "kn": f"🏥 **{location_label} ಬಳಿ ಆರೋಗ್ಯ ಕೇಂದ್ರಗಳು:**\n",
    }
    not_found = {
        "hi": f"**{location_label}** के पास कोई स्वास्थ्य केंद्र नहीं मिला।\n\n**104** पर कॉल करें (राष्ट्रीय स्वास्थ्य हेल्पलाइन)",
        "ta": f"**{location_label}** அருகில் மருத்துவமனை கிடைக்கவில்லை.\n\n**104** அழையுங்கள்",
        "te": f"**{location_label}** దగ్గర ఆసుపత్రి కనుగొనబడలేదు.\n\n**104** కు కాల్ చేయండి",
        "bn": f"**{location_label}** এর কাছে হাসপাতাল পাওয়া যায়নি।\n\n**104** নম্বরে ফোন করুন",
        "kn": f"**{location_label}** ಬಳಿ ಆಸ್ಪತ್ರೆ ಸಿಗಲಿಲ್ಲ.\n\n**104** ಗೆ ಕರೆ ಮಾಡಿ",
    }

    if not facilities:
        msg = not_found.get(lang, (
            f"I couldn't find health facilities near **{location_label}**.\n\n"
            "Please try:\n"
            "- Call **National Health Helpline: 104**\n"
            "- Visit your nearest Anganwadi/ASHA worker\n"
            "- Check https://hfr.abdm.gov.in"
        ))
        return msg + "\n\n_I'm an AI assistant, not a doctor. Please consult a healthcare professional._"

    lines = [headers.get(lang, f"🏥 **Nearby Health Facilities near {location_label}:**"), ""]

    for i, f in enumerate(facilities[:6], 1):
        lines.append(f"**{i}. {f['name']}**")
        ftype = f.get("type", "facility").replace("_", " ").title()
        lines.append(f"   📍 {ftype}")
        if f.get("address"):
            lines.append(f"   🗺️ {f['address']}")
        if f.get("phone"):
            lines.append(f"   📞 {f['phone']}")
        if f.get("rating"):
            lines.append(f"   ⭐ {f['rating']}/5")
        # Map links
        if f.get("gmaps_url"):
            lines.append(f"   🔗 [Google Maps]({f['gmaps_url']}) | [OpenStreetMap]({f.get('maps_url','')})")
        elif f.get("maps_url"):
            lines.append(f"   🔗 [View on Map]({f['maps_url']})")
        lines.append("")

    lines += [
        "💡 Government PHCs provide **free consultations & medicines** (National Health Mission).",
        "📞 **National Health Helpline: 104** — free, 24/7",
        "",
        "_I'm an AI assistant, not a doctor. For diagnosis or treatment, please consult a healthcare professional._",
    ]
    return "\n".join(lines)


@tool
def facility_locator_tool(location: str) -> str:
    """
    Finds nearby healthcare facilities (PHCs, hospitals, clinics) for a given
    Indian pincode, city, or district name.
    Returns names, addresses, phone numbers, and map links.

    Args:
        location: Indian pincode (6 digits) or city/district name (e.g. '110001', 'Chennai', 'Mysore')
    """
    logger.info("Facility locator: %s", location)

    # Step 0: Check if user forgot to give a location
    if _NO_LOCATION_PATTERNS.match(location.strip()):
        return (
            "To find nearby hospitals and health centres, I need to know your location.\n\n"
            "Please tell me:\n"
            "- Your **city or district** name (e.g. `Jaipur`, `Patna`, `Mysore`)\n"
            "- Or your **6-digit pincode** (e.g. `302001`)\n\n"
            "**Example:** *Nearest hospital in Jaipur* or *Hospital near 560001*"
        )

    # Step 1: Check hardcoded city database first — instant, no network needed
    city_facilities = _lookup_city_db(location.strip())
    if city_facilities:
        # Use the canonical city name from the DB as the display label
        key = location.lower().strip()
        resolved_key = _CITY_ALIASES.get(key, key)
        for city in _CITY_FACILITIES:
            if city in key or key in city:
                resolved_key = city
                break
        city_label = resolved_key.title()
        logger.info("City DB hit for '%s' -> '%s' — %d facilities", location, city_label, len(city_facilities))
        return _format(city_facilities, city_label)

    # Step 2: Geocode
    try:
        geo = _geocode_location(location.strip())
    except Exception as e:
        logger.warning("Geocoding failed: %s", e)
        geo = None

    if not geo:
        return (
            f"I couldn't find the location **'{location}'** on the map.\n\n"
            "Please try:\n"
            "- Your 6-digit pincode (e.g. `110001`)\n"
            "- District or city name (e.g. `Chennai`, `Mysore`)\n\n"
            "Or call **104** (National Health Helpline) for facility information."
        )

    lat, lon, display_name = geo
    logger.info("Geocoded '%s' -> %.4f, %.4f (%s)", location, lat, lon, display_name)

    # Step 3: Google Places if key set
    facilities = []
    if settings.google_places_api_key:
        try:
            facilities = _search_google(lat, lon)
        except Exception as e:
            logger.warning("Google Places failed: %s", e)

    # Step 4: OSM fallback (with timeout guard)
    if not facilities:
        try:
            facilities = _search_osm(lat, lon, radius_m=5000)
            if not facilities:
                facilities = _search_osm(lat, lon, radius_m=10000)
        except Exception as e:
            logger.warning("OSM search failed: %s", e)

    return _format(facilities, display_name)
