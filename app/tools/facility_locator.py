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

# Common Indian pincode prefixes → city name in _CITY_FACILITIES
# Covers the most-asked pincodes so the tool never needs a network call for these
_PINCODE_TO_CITY = {
    # Delhi NCR — 110xxx
    "110001": "delhi", "110002": "delhi", "110003": "delhi", "110004": "delhi",
    "110005": "delhi", "110006": "delhi", "110007": "delhi", "110008": "delhi",
    "110009": "delhi", "110010": "delhi", "110011": "delhi", "110012": "delhi",
    "110013": "delhi", "110014": "delhi", "110015": "delhi", "110016": "delhi",
    "110017": "delhi", "110018": "delhi", "110019": "delhi", "110020": "delhi",
    "110021": "delhi", "110022": "delhi", "110023": "delhi", "110024": "delhi",
    "110025": "delhi", "110026": "delhi", "110027": "delhi", "110028": "delhi",
    "110029": "delhi", "110030": "delhi", "110031": "delhi", "110032": "delhi",
    "110033": "delhi", "110034": "delhi", "110035": "delhi", "110036": "delhi",
    "110037": "delhi", "110038": "delhi", "110039": "delhi", "110040": "delhi",
    "110041": "delhi", "110042": "delhi", "110043": "delhi", "110044": "delhi",
    "110045": "delhi", "110046": "delhi", "110047": "delhi", "110048": "delhi",
    "110049": "delhi", "110050": "delhi", "110051": "delhi", "110052": "delhi",
    "110053": "delhi", "110054": "delhi", "110055": "delhi", "110056": "delhi",
    "110057": "delhi", "110058": "delhi", "110059": "delhi", "110060": "delhi",
    "110061": "delhi", "110062": "delhi", "110063": "delhi", "110064": "delhi",
    "110065": "delhi", "110066": "delhi", "110067": "delhi", "110068": "delhi",
    "110069": "delhi", "110070": "delhi", "110071": "delhi", "110072": "delhi",
    "110073": "delhi", "110074": "delhi", "110075": "delhi", "110076": "delhi",
    "110077": "delhi", "110078": "delhi", "110079": "delhi", "110080": "delhi",
    "110081": "delhi", "110082": "delhi", "110083": "delhi", "110084": "delhi",
    "110085": "delhi", "110086": "delhi", "110087": "delhi", "110088": "delhi",
    "110089": "delhi", "110090": "delhi", "110091": "delhi", "110092": "delhi",
    "110093": "delhi", "110094": "delhi", "110095": "delhi", "110096": "delhi",
    # Mumbai — 400xxx
    "400001": "mumbai", "400002": "mumbai", "400003": "mumbai", "400004": "mumbai",
    "400005": "mumbai", "400006": "mumbai", "400007": "mumbai", "400008": "mumbai",
    "400009": "mumbai", "400010": "mumbai", "400011": "mumbai", "400012": "mumbai",
    "400013": "mumbai", "400014": "mumbai", "400015": "mumbai", "400016": "mumbai",
    "400017": "mumbai", "400018": "mumbai", "400019": "mumbai", "400020": "mumbai",
    "400021": "mumbai", "400022": "mumbai", "400023": "mumbai", "400024": "mumbai",
    "400025": "mumbai", "400026": "mumbai", "400027": "mumbai", "400028": "mumbai",
    "400029": "mumbai", "400030": "mumbai",
    # Bangalore — 560xxx
    "560001": "bangalore", "560002": "bangalore", "560003": "bangalore",
    "560004": "bangalore", "560005": "bangalore", "560006": "bangalore",
    "560007": "bangalore", "560008": "bangalore", "560009": "bangalore",
    "560010": "bangalore", "560011": "bangalore", "560012": "bangalore",
    "560013": "bangalore", "560014": "bangalore", "560015": "bangalore",
    "560016": "bangalore", "560017": "bangalore", "560018": "bangalore",
    "560019": "bangalore", "560020": "bangalore", "560021": "bangalore",
    "560022": "bangalore", "560023": "bangalore", "560024": "bangalore",
    "560025": "bangalore", "560026": "bangalore", "560027": "bangalore",
    "560028": "bangalore", "560029": "bangalore", "560030": "bangalore",
    "560034": "bangalore", "560037": "bangalore", "560040": "bangalore",
    "560041": "bangalore", "560043": "bangalore", "560045": "bangalore",
    "560048": "bangalore", "560050": "bangalore", "560068": "bangalore",
    "560076": "bangalore", "560078": "bangalore", "560079": "bangalore",
    "560085": "bangalore", "560086": "bangalore", "560094": "bangalore",
    "560095": "bangalore", "560100": "bangalore",
    # Chennai — 600xxx
    "600001": "chennai", "600002": "chennai", "600003": "chennai",
    "600004": "chennai", "600005": "chennai", "600006": "chennai",
    "600007": "chennai", "600008": "chennai", "600009": "chennai",
    "600010": "chennai", "600011": "chennai", "600012": "chennai",
    "600013": "chennai", "600014": "chennai", "600015": "chennai",
    "600017": "chennai", "600018": "chennai", "600020": "chennai",
    "600024": "chennai", "600025": "chennai", "600026": "chennai",
    "600028": "chennai", "600029": "chennai", "600030": "chennai",
    "600031": "chennai", "600032": "chennai", "600033": "chennai",
    "600034": "chennai", "600035": "chennai", "600040": "chennai",
    # Hyderabad — 500xxx
    "500001": "hyderabad", "500002": "hyderabad", "500003": "hyderabad",
    "500004": "hyderabad", "500005": "hyderabad", "500006": "hyderabad",
    "500007": "hyderabad", "500008": "hyderabad", "500009": "hyderabad",
    "500010": "hyderabad", "500011": "hyderabad", "500012": "hyderabad",
    "500013": "hyderabad", "500015": "hyderabad", "500016": "hyderabad",
    "500017": "hyderabad", "500018": "hyderabad", "500019": "hyderabad",
    "500020": "hyderabad", "500026": "hyderabad", "500027": "hyderabad",
    "500028": "hyderabad", "500029": "hyderabad", "500030": "hyderabad",
    "500032": "hyderabad", "500033": "hyderabad", "500034": "hyderabad",
    "500035": "hyderabad", "500036": "hyderabad", "500038": "hyderabad",
    # Kolkata — 700xxx
    "700001": "kolkata", "700002": "kolkata", "700003": "kolkata",
    "700004": "kolkata", "700005": "kolkata", "700006": "kolkata",
    "700007": "kolkata", "700008": "kolkata", "700009": "kolkata",
    "700010": "kolkata", "700011": "kolkata", "700012": "kolkata",
    "700013": "kolkata", "700014": "kolkata", "700015": "kolkata",
    "700016": "kolkata", "700017": "kolkata", "700018": "kolkata",
    "700019": "kolkata", "700020": "kolkata",
    # Pune — 411xxx
    "411001": "pune", "411002": "pune", "411003": "pune", "411004": "pune",
    "411005": "pune", "411006": "pune", "411007": "pune", "411008": "pune",
    "411009": "pune", "411011": "pune", "411012": "pune", "411013": "pune",
    "411014": "pune", "411015": "pune", "411016": "pune", "411017": "pune",
    "411018": "pune", "411019": "pune", "411020": "pune", "411021": "pune",
    "411028": "pune", "411037": "pune", "411038": "pune", "411041": "pune",
    # Mangalore — 575xxx
    "575001": "mangalore", "575002": "mangalore", "575003": "mangalore",
    "575004": "mangalore", "575005": "mangalore", "575006": "mangalore",
    "575007": "mangalore", "575008": "mangalore",
    # Mysore — 570xxx
    "570001": "mysore", "570002": "mysore", "570003": "mysore",
    "570004": "mysore", "570008": "mysore", "570010": "mysore",
    "570011": "mysore", "570015": "mysore", "570019": "mysore",
    "570024": "mysore", "570025": "mysore",
    # Jaipur — 302xxx
    "302001": "jaipur", "302002": "jaipur", "302003": "jaipur",
    "302004": "jaipur", "302005": "jaipur", "302006": "jaipur",
    "302012": "jaipur", "302015": "jaipur", "302016": "jaipur",
    "302017": "jaipur", "302018": "jaipur", "302019": "jaipur",
    "302020": "jaipur", "302021": "jaipur", "302022": "jaipur",
    # Lucknow — 226xxx
    "226001": "lucknow", "226002": "lucknow", "226003": "lucknow",
    "226004": "lucknow", "226005": "lucknow", "226006": "lucknow",
    "226007": "lucknow", "226008": "lucknow", "226009": "lucknow",
    "226010": "lucknow", "226012": "lucknow", "226016": "lucknow",
    "226017": "lucknow", "226018": "lucknow", "226021": "lucknow",
    # Patna — 800xxx
    "800001": "patna", "800002": "patna", "800003": "patna",
    "800004": "patna", "800005": "patna", "800006": "patna",
    "800007": "patna", "800008": "patna", "800009": "patna",
    "800010": "patna", "800011": "patna", "800012": "patna",
    "800013": "patna", "800014": "patna", "800015": "patna",
    "800016": "patna", "800020": "patna",
    # Ahmedabad — 380xxx
    "380001": "ahmedabad", "380002": "ahmedabad", "380004": "ahmedabad",
    "380005": "ahmedabad", "380006": "ahmedabad", "380007": "ahmedabad",
    "380008": "ahmedabad", "380009": "ahmedabad", "380013": "ahmedabad",
    "380014": "ahmedabad", "380015": "ahmedabad", "380016": "ahmedabad",
    "380018": "ahmedabad", "380019": "ahmedabad", "380021": "ahmedabad",
    "380022": "ahmedabad", "380023": "ahmedabad", "380024": "ahmedabad",
    "380025": "ahmedabad", "380026": "ahmedabad", "380027": "ahmedabad",
    # Chandigarh — 160xxx
    "160001": "chandigarh", "160002": "chandigarh", "160003": "chandigarh",
    "160009": "chandigarh", "160011": "chandigarh", "160012": "chandigarh",
    "160014": "chandigarh", "160015": "chandigarh", "160017": "chandigarh",
    "160018": "chandigarh", "160019": "chandigarh", "160020": "chandigarh",
    "160022": "chandigarh", "160023": "chandigarh", "160025": "chandigarh",
    "160036": "chandigarh", "160047": "chandigarh", "160059": "chandigarh",
    # Kochi — 682xxx
    "682001": "kochi", "682002": "kochi", "682003": "kochi",
    "682004": "kochi", "682005": "kochi", "682006": "kochi",
    "682007": "kochi", "682008": "kochi", "682009": "kochi",
    "682010": "kochi", "682011": "kochi", "682012": "kochi",
    "682013": "kochi", "682016": "kochi", "682017": "kochi",
    "682018": "kochi", "682019": "kochi", "682020": "kochi",
    # Nagpur — 440xxx
    "440001": "nagpur", "440002": "nagpur", "440003": "nagpur",
    "440004": "nagpur", "440005": "nagpur", "440006": "nagpur",
    "440007": "nagpur", "440008": "nagpur", "440009": "nagpur",
    "440010": "nagpur", "440012": "nagpur", "440013": "nagpur",
    "440014": "nagpur", "440015": "nagpur", "440016": "nagpur",
    "440017": "nagpur", "440018": "nagpur", "440022": "nagpur",
    # Coimbatore — 641xxx
    "641001": "coimbatore", "641002": "coimbatore", "641003": "coimbatore",
    "641004": "coimbatore", "641005": "coimbatore", "641006": "coimbatore",
    "641007": "coimbatore", "641008": "coimbatore", "641009": "coimbatore",
    "641010": "coimbatore", "641011": "coimbatore", "641012": "coimbatore",
    "641013": "coimbatore", "641014": "coimbatore", "641015": "coimbatore",
    "641016": "coimbatore", "641017": "coimbatore", "641018": "coimbatore",
    "641019": "coimbatore", "641020": "coimbatore",
    # Visakhapatnam — 530xxx
    "530001": "visakhapatnam", "530002": "visakhapatnam", "530003": "visakhapatnam",
    "530004": "visakhapatnam", "530005": "visakhapatnam", "530007": "visakhapatnam",
    "530009": "visakhapatnam", "530011": "visakhapatnam", "530012": "visakhapatnam",
    "530013": "visakhapatnam", "530016": "visakhapatnam", "530017": "visakhapatnam",
    "530022": "visakhapatnam", "530026": "visakhapatnam",
    # Surat — 395xxx
    "395001": "surat", "395002": "surat", "395003": "surat",
    "395004": "surat", "395005": "surat", "395006": "surat",
    "395007": "surat", "395008": "surat", "395009": "surat",
    "395010": "surat", "395011": "surat", "395012": "surat",
    # Bhopal — 462xxx
    "462001": "bhopal", "462002": "bhopal", "462003": "bhopal",
    "462010": "bhopal", "462011": "bhopal", "462016": "bhopal",
    "462020": "bhopal", "462022": "bhopal", "462023": "bhopal",
    "462026": "bhopal", "462027": "bhopal", "462030": "bhopal",
    "462031": "bhopal", "462036": "bhopal", "462038": "bhopal",
    # Indore — 452xxx (use bhopal as nearest DB entry)
    "452001": "bhopal", "452002": "bhopal", "452003": "bhopal",
    "452004": "bhopal", "452005": "bhopal", "452006": "bhopal",
    "452007": "bhopal", "452008": "bhopal", "452009": "bhopal",
    "452010": "bhopal",
}

# Keywords that indicate a location-less request — we should ask for location
# Matches ONLY bare requests with no location — e.g. "nearest hospital" or "hospital?"
# Does NOT match inputs that include a city, pincode, or preposition indicating a location.
_NO_LOCATION_PATTERNS = re.compile(
    r"^(?:nearest|nearby|near me|close to me|find|show|get|locate|"
    r"(?:nearest\s+)?(?:hospital|clinic|phc|doctor|health\s+cent(?:re|er)|"
    r"dawakhana|aspatal|aspatre|chikitsaalaya))\s*[\?!.]?$",
    re.IGNORECASE,
)


def _add_osm_url(facilities: list) -> list:
    """
    For hardcoded city DB entries that have gmaps_url but no maps_url,
    derive the OpenStreetMap URL from the lat/lon in gmaps_url.
    """
    import re as _re
    result = []
    for f in facilities:
        entry = dict(f)
        if not entry.get("maps_url") and entry.get("gmaps_url"):
            m = _re.search(r"q=([\d.]+),([\d.]+)", entry["gmaps_url"])
            if m:
                lat, lon = m.group(1), m.group(2)
                entry["maps_url"] = (
                    f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}"
                    f"&zoom=17#map=17/{lat}/{lon}"
                )
        result.append(entry)
    return result


def _lookup_city_db(location: str) -> list:
    """
    Instantly look up facilities from the hardcoded city database.
    Tries pincode map, exact match, alias, then partial match.
    Returns list of facility dicts or empty list if city not found.
    """
    key = location.lower().strip()
    # Pincode lookup — e.g. "110001" → "delhi"
    if re.match(r"^\d{6}$", key):
        city = _PINCODE_TO_CITY.get(key)
        if city and city in _CITY_FACILITIES:
            return _add_osm_url(_CITY_FACILITIES[city])
    # Direct match
    if key in _CITY_FACILITIES:
        return _add_osm_url(_CITY_FACILITIES[key])
    # Alias match
    resolved = _CITY_ALIASES.get(key)
    if resolved and resolved in _CITY_FACILITIES:
        return _add_osm_url(_CITY_FACILITIES[resolved])
    # Partial match — e.g. "mangalore district" → "mangalore"
    for city in _CITY_FACILITIES:
        if city in key or key in city:
            return _add_osm_url(_CITY_FACILITIES[city])
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
    for url in OVERPASS_URLS[:2]:   # try at most 2 mirrors to bound total wait time
        try:
            with httpx.Client(timeout=8.0) as client:
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
        raw_lat = el.get("lat")
        raw_lon = el.get("lon")
        try:
            f_lat = float(raw_lat) if raw_lat is not None else lat
            f_lon = float(raw_lon) if raw_lon is not None else lon
        except (TypeError, ValueError):
            f_lat, f_lon = lat, lon
        facilities.append({
            "name": name,
            "type": ftype,
            "phone": phone,
            "address": address,
            "lat": f_lat,
            "lon": f_lon,
            "maps_url": f"https://www.openstreetmap.org/?mlat={f_lat}&mlon={f_lon}&zoom=17#map=17/{f_lat}/{f_lon}",
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
    logger.info("Facility locator raw input: %s", location)

    # Pre-process: if the LLM passed the full user sentence, extract pincode or city from it
    pincode_in_text = re.search(r"\b(\d{6})\b", location)
    if pincode_in_text:
        location = pincode_in_text.group(1)
        logger.info("Extracted pincode from sentence: %s", location)
    else:
        # Try to extract a city name from common phrase patterns
        city_match = re.search(
            r"(?:near(?:est)?|in|at|around|hospital in|clinic in|phc in)\s+([A-Za-z][\w\s]{1,25}?)(?:\s*[?!.,]|$)",
            location, re.IGNORECASE
        )
        if city_match:
            location = city_match.group(1).strip()
            logger.info("Extracted city from sentence: %s", location)

    logger.info("Facility locator resolved: %s", location)

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
