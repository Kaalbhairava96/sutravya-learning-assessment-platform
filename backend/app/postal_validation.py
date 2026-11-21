"""Server-side Indian PIN-code lookup and State/District matching.

The lookup source is a third-party API backed by India's published postal directory.
Results are cached per PIN so repeated registrations do not repeatedly call the provider.
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_API_BASE = "https://api.pincodeapi.in/api/v1/pincode/"
_CACHE_TTL_SECONDS = 24 * 60 * 60
_CACHE_MAX_ENTRIES = 20_000
_cache: dict[str, tuple[float, tuple[tuple[str, str], ...]]] = {}
_cache_lock = Lock()


class PostalLookupUnavailable(RuntimeError):
    """Raised when the postal lookup provider cannot be reached or trusted."""


_STATE_ALIASES = {
    "orissa": "odisha",
    "pondicherry": "puducherry",
    "uttaranchal": "uttarakhand",
}
_DISTRICT_ALIASES = {
    "allahabad": "prayagraj",
    "faizabad": "ayodhya",
    "gurgaon": "gurugram",
    "bangalore": "bengaluru",
    "mysore": "mysuru",
    "gulbarga": "kalaburagi",
    "bellary": "ballari",
    "belgaum": "belagavi",
}


def _key(value: str) -> str:
    folded = unicodedata.normalize("NFKD", str(value or ""))
    plain = "".join(char for char in folded if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", plain.casefold())


def _state_key(value: str) -> str:
    key = _key(value)
    return _key(_STATE_ALIASES.get(key, key))


def _district_key(value: str) -> str:
    key = _key(value)
    return _key(_DISTRICT_ALIASES.get(key, key))


def _fetch_postal_locations(pin_code: str) -> tuple[tuple[str, str], ...]:
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(pin_code)
        if cached and cached[0] > now:
            return cached[1]
        if cached:
            _cache.pop(pin_code, None)

    request = Request(
        _API_BASE + pin_code,
        headers={
            "Accept": "application/json",
            "User-Agent": "SUTRAVYA-Assessment-Platform/1.0",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=7) as response:
            if response.status != 200:
                raise PostalLookupUnavailable("The postal lookup service returned an unexpected response.")
            payload = json.loads(response.read(1_000_000).decode("utf-8"))
    except HTTPError as error:
        if error.code == 404:
            locations: tuple[tuple[str, str], ...] = ()
        else:
            raise PostalLookupUnavailable("The postal lookup service is temporarily unavailable.") from error
    except (URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PostalLookupUnavailable("The postal lookup service is temporarily unavailable.") from error

    if "locations" not in locals():
        if not isinstance(payload, dict) or payload.get("success") is not True:
            raise PostalLookupUnavailable("The postal lookup service returned incomplete data.")
        data = payload.get("data")
        offices = data.get("post_offices") if isinstance(data, dict) else None
        if not isinstance(offices, list):
            raise PostalLookupUnavailable("The postal lookup service returned incomplete data.")
        found: set[tuple[str, str]] = set()
        for office in offices:
            if not isinstance(office, dict):
                continue
            district = " ".join(str(office.get("district") or "").split())
            state = " ".join(str(office.get("state") or "").split())
            if district and state:
                found.add((district, state))
        locations = tuple(sorted(found, key=lambda item: (item[1], item[0])))

    with _cache_lock:
        if len(_cache) >= _CACHE_MAX_ENTRIES:
            _cache.clear()
        _cache[pin_code] = (time.monotonic() + _CACHE_TTL_SECONDS, locations)
    return locations


def validate_pin_location(pin_code: str, state: str, district: str) -> dict[str, object]:
    """Return whether a PIN code is associated with the selected district and state."""
    pin = (pin_code or "").strip()
    if not re.fullmatch(r"[1-9][0-9]{5}", pin):
        return {"valid": False, "detail": "Enter a valid six-digit Indian PIN code."}

    selected_state = _state_key(state)
    selected_district = _district_key(district)
    if not selected_state or not selected_district:
        return {"valid": False, "detail": "Choose the State and District before validating the PIN code."}

    locations = _fetch_postal_locations(pin)
    if not locations:
        return {"valid": False, "detail": "This PIN code was not found in the Indian postal directory. Check the six digits and try again."}

    for office_district, office_state in locations:
        if (
            _state_key(office_state) == selected_state
            and _district_key(office_district) == selected_district
        ):
            return {"valid": True, "detail": "PIN code matches the selected State and District."}

    actual = ", ".join(f"{office_district}, {office_state}" for office_district, office_state in locations[:3])
    if len(locations) > 3:
        actual += ", and other postal areas"
    return {
        "valid": False,
        "detail": f"This PIN code is registered for {actual}, not the selected {district}, {state}. Correct the PIN code or your address selection.",
        "matched_locations": [{"district": d, "state": s} for d, s in locations[:10]],
    }
