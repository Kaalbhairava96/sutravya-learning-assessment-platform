"""PIN-code lookup and location matching using the public India Post directory interface."""
from __future__ import annotations

import json
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_CACHE_TTL_SECONDS = 6 * 60 * 60
_CACHE_LIMIT = 2048
_CACHE: dict[str, tuple[float, tuple[tuple[str, str], ...]]] = {}
_CACHE_LOCK = threading.Lock()


class PinCodeLookupUnavailable(RuntimeError):
    """Raised when the postal directory cannot be reached or returns an invalid response."""


def _normalise_location(value: str | None) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", (value or "").casefold()).strip()
    aliases = {
        "orissa": "odisha",
        "pondicherry": "puducherry",
        "uttaranchal": "uttarakhand",
        "gurugram": "gurgaon",
        "prayagraj": "allahabad",
        "bengaluru": "bangalore",
        "bengaluru urban": "bangalore urban",
        "mysuru": "mysore",
        "bellary": "ballari",
        "cuddapah": "ysr kadapa",
    }
    return aliases.get(cleaned, cleaned)


def lookup_pin_locations(pin_code: str) -> tuple[tuple[str, str], ...]:
    """Return all (state, district) pairs associated with a six-digit PIN.

    Only the PIN code is sent to the read-only directory service. Results are
    cached for six hours to avoid repeated lookups while candidates edit forms.
    """
    pin = (pin_code or "").strip()
    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(pin)
        if cached and now - cached[0] < _CACHE_TTL_SECONDS:
            return cached[1]

    request = Request(
        f"https://api.postalpincode.in/pincode/{pin}",
        headers={"Accept": "application/json", "User-Agent": "SUTRAVYA-Assessment-Platform/1.0"},
    )
    try:
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PinCodeLookupUnavailable("The postal PIN directory is temporarily unavailable.") from error

    if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
        raise PinCodeLookupUnavailable("The postal PIN directory returned an unexpected response.")

    result = payload[0]
    status = str(result.get("Status", "")).casefold()
    if status == "error":
        locations: tuple[tuple[str, str], ...] = ()
    elif status == "success" and isinstance(result.get("PostOffice"), list):
        locations = tuple(
            (str(office.get("State", "")).strip(), str(office.get("District", "")).strip())
            for office in result["PostOffice"]
            if isinstance(office, dict) and office.get("State") and office.get("District")
        )
    else:
        raise PinCodeLookupUnavailable("The postal PIN directory returned an incomplete response.")

    with _CACHE_LOCK:
        if len(_CACHE) >= _CACHE_LIMIT:
            expired = [key for key, (created, _value) in _CACHE.items() if now - created >= _CACHE_TTL_SECONDS]
            for key in expired:
                _CACHE.pop(key, None)
            if len(_CACHE) >= _CACHE_LIMIT:
                _CACHE.pop(next(iter(_CACHE)))
        _CACHE[pin] = (now, locations)
    return locations


def matching_pin_locations(pin_code: str, state: str, district: str) -> tuple[tuple[str, str], ...]:
    """Return directory records matching both the selected state and district."""
    wanted_state = _normalise_location(state)
    wanted_district = _normalise_location(district)
    return tuple(
        (found_state, found_district)
        for found_state, found_district in lookup_pin_locations(pin_code)
        if _normalise_location(found_state) == wanted_state
        and _normalise_location(found_district) == wanted_district
    )
