"""Canonical Indian states/UTs and cities (keep in sync with kb-ui/src/data/indiaTerritory.ts)."""

from __future__ import annotations

STATE_CITIES: dict[str, list[str]] = {
    "Andhra Pradesh": ["Visakhapatnam", "Vijayawada", "Guntur", "Nellore", "Tirupati", "Kurnool", "Other"],
    "Arunachal Pradesh": ["Itanagar", "Naharlagun", "Tawang", "Other"],
    "Assam": ["Guwahati", "Dibrugarh", "Silchar", "Jorhat", "Tezpur", "Other"],
    "Bihar": ["Patna", "Gaya", "Muzaffarpur", "Bhagalpur", "Darbhanga", "Other"],
    "Chhattisgarh": ["Raipur", "Bhilai", "Bilaspur", "Korba", "Durg", "Other"],
    "Delhi": ["New Delhi", "Delhi", "Dwarka", "Rohini", "Saket", "Other"],
    "Goa": ["Panaji", "Margao", "Vasco da Gama", "Mapusa", "Other"],
    "Gujarat": ["Ahmedabad", "Surat", "Vadodara", "Rajkot", "Bhavnagar", "Gandhinagar", "Other"],
    "Haryana": [
        "Gurugram", "Faridabad", "Panipat", "Ambala", "Karnal", "Hisar",
        "Rohtak", "Sonipat", "Panchkula", "Other",
    ],
    "Himachal Pradesh": ["Shimla", "Dharamshala", "Solan", "Mandi", "Other"],
    "Jharkhand": ["Ranchi", "Jamshedpur", "Dhanbad", "Bokaro", "Other"],
    "Karnataka": ["Bengaluru", "Mysuru", "Mangaluru", "Hubballi", "Belagavi", "Other"],
    "Kerala": ["Thiruvananthapuram", "Kochi", "Kozhikode", "Thrissur", "Kollam", "Other"],
    "Madhya Pradesh": ["Bhopal", "Indore", "Jabalpur", "Gwalior", "Ujjain", "Other"],
    "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Thane", "Nashik", "Aurangabad", "Other"],
    "Manipur": ["Imphal", "Other"],
    "Meghalaya": ["Shillong", "Other"],
    "Mizoram": ["Aizawl", "Other"],
    "Nagaland": ["Kohima", "Dimapur", "Other"],
    "Odisha": ["Bhubaneswar", "Cuttack", "Rourkela", "Puri", "Other"],
    "Punjab": ["Ludhiana", "Amritsar", "Jalandhar", "Patiala", "Mohali", "Chandigarh", "Other"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Udaipur", "Kota", "Ajmer", "Bikaner", "Other"],
    "Sikkim": ["Gangtok", "Other"],
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem", "Other"],
    "Telangana": ["Hyderabad", "Warangal", "Nizamabad", "Karimnagar", "Other"],
    "Tripura": ["Agartala", "Other"],
    "Uttar Pradesh": ["Lucknow", "Kanpur", "Ghaziabad", "Noida", "Agra", "Varanasi", "Meerut", "Other"],
    "Uttarakhand": ["Dehradun", "Haridwar", "Haldwani", "Roorkee", "Other"],
    "West Bengal": ["Kolkata", "Howrah", "Durgapur", "Siliguri", "Asansol", "Other"],
    "Chandigarh": ["Chandigarh", "Other"],
    "Jammu and Kashmir": ["Srinagar", "Jammu", "Other"],
    "Ladakh": ["Leh", "Kargil", "Other"],
    "Puducherry": ["Puducherry", "Karaikal", "Other"],
}

STATES: list[str] = sorted(STATE_CITIES.keys())
DEFAULT_STATE = "Haryana"

STATE_ALIASES: dict[str, str] = {
    "up": "Uttar Pradesh",
    "mp": "Madhya Pradesh",
    "hp": "Himachal Pradesh",
    "wb": "West Bengal",
    "nct of delhi": "Delhi",
    "new delhi": "Delhi",
    "jk": "Jammu and Kashmir",
}

CITY_ALIASES: dict[str, str] = {
    "gurgaon": "Gurugram",
    "bangalore": "Bengaluru",
    "bombay": "Mumbai",
    "calcutta": "Kolkata",
    "madras": "Chennai",
    "mysore": "Mysuru",
    "baroda": "Vadodara",
}


def _clean(value: str) -> str:
    return " ".join(value.strip().split())


def cities_for_state(state: str) -> list[str]:
    return list(STATE_CITIES.get(state, STATE_CITIES[DEFAULT_STATE]))


def is_valid_state_city(state: str, city: str) -> bool:
    cities = STATE_CITIES.get(state)
    return bool(cities and city in cities)


def normalize_state(raw: str) -> str:
    cleaned = _clean(raw)
    if not cleaned:
        return DEFAULT_STATE
    lower = cleaned.lower()
    if lower in STATE_ALIASES:
        return STATE_ALIASES[lower]
    for state in STATES:
        if state.lower() == lower:
            return state
    for state in STATES:
        if lower in state.lower() or state.lower() in lower:
            return state
    return DEFAULT_STATE


def _find_state_for_city(city: str) -> str | None:
    lower = city.lower()
    for state, cities in STATE_CITIES.items():
        if any(c.lower() == lower for c in cities):
            return state
    return None


def normalize_city(state: str, raw: str) -> str:
    cities = cities_for_state(state)
    cleaned = _clean(raw)
    if not cleaned:
        return cities[-1]
    candidate = CITY_ALIASES.get(cleaned.lower(), cleaned)
    for city in cities:
        if city.lower() == candidate.lower():
            return city
    for city in cities:
        if candidate.lower() in city.lower() or city.lower() in candidate.lower():
            return city
    if _find_state_for_city(candidate):
        return candidate
    return "Other" if "Other" in cities else cities[0]


def normalize_state_city(state_raw: str, city_raw: str) -> tuple[str, str]:
    state = normalize_state(state_raw)
    city = normalize_city(state, city_raw)
    if not is_valid_state_city(state, city):
        inferred = _find_state_for_city(city)
        if inferred:
            state = inferred
        city = normalize_city(state, city_raw)
    if not is_valid_state_city(state, city):
        city = cities_for_state(state)[0]
    return state, city


def validate_state_city(state: str, city: str) -> tuple[str, str]:
    normalized = normalize_state_city(state, city)
    if not is_valid_state_city(normalized[0], normalized[1]):
        raise ValueError("Invalid state and city combination")
    return normalized
