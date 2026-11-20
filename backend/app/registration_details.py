"""Server-side validation for free QualiNova registration categories."""
from __future__ import annotations

import re
import json
from pathlib import Path
from fastapi import HTTPException

PROGRAMMES = {
    "nursing": {"bsc_nursing": "B.Sc Nursing", "msc_nursing": "M.Sc Nursing"},
    "paramedical": {
        "bmlt": "BMLT", "bott": "BOTT", "bhm": "BHM",
        "bopt": "B.Opt", "brit": "BRIT",
    },
    "medical": {
        "medical_ug": "Medical UG",
        "medical_pg": "Medical PG",
    },
}
_MOBILE = re.compile(r"^[6-9][0-9]{9}$")

_STATE_DATA_PATH = Path(__file__).resolve().parent / "data" / "india-states-districts.json"
with _STATE_DATA_PATH.open("r", encoding="utf-8") as _state_file:
    _STATE_DATA = json.load(_state_file)


def _location_key(value: str) -> str:
    return " ".join(value.split()).casefold()


_STATE_DISTRICTS = {
    _location_key(state["name"]): {
        _location_key(district): (state["name"], district)
        for district in state["districts"]
    }
    for state in _STATE_DATA["states"]
}


def _required(value: str | None, label: str, maximum: int = 240) -> str:
    cleaned = " ".join((value or "").split())
    if not cleaned or len(cleaned) > maximum:
        raise HTTPException(status_code=422, detail=f"Enter a valid {label}.")
    return cleaned


def build_registration_details(payload, session=None) -> dict:
    """Validate the selected category and academic pathway."""
    raw_category = (payload.category or "").strip().lower()
    # Backward compatibility for older API clients sending the retired MBBS labels.
    # Persisted details and all new public-facing records use canonical Medical labels.
    category = "medical" if raw_category == "mbbs" else raw_category
    if category not in PROGRAMMES:
        raise HTTPException(status_code=422, detail="Choose Nursing, Paramedical or Medical.")
    raw_programme = (payload.programme or "").strip().lower()
    legacy_programmes = {"mbbs_ug": "medical_ug", "mbbs_pg": "medical_pg"}
    programme = legacy_programmes.get(raw_programme, raw_programme) if category == "medical" else raw_programme
    if programme not in PROGRAMMES[category]:
        raise HTTPException(status_code=422, detail="Choose a valid programme or Medical sub-category.")
    _required(payload.full_name, "full name", 200)
    _required(payload.email, "email address", 320)
    if payload.declaration_accepted is not True:
        raise HTTPException(status_code=422, detail="Accept the candidate declaration before continuing.")
    digits = re.sub(r"[^0-9]", "", payload.mobile or "")
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if not _MOBILE.fullmatch(digits):
        raise HTTPException(status_code=422, detail="Enter a valid 10-digit Indian mobile number.")
    house = _required(payload.house_number, "house / flat number", 100)
    address1 = _required(payload.address_line1, "address line 1", 240)
    address2 = " ".join((payload.address_line2 or "").split())[:240]
    district_input = _required(payload.district, "district", 120)
    state_input = _required(payload.state, "state / Union Territory", 120)
    state_entry = _STATE_DISTRICTS.get(_location_key(state_input))
    if state_entry is None:
        raise HTTPException(status_code=422, detail="Select a valid Indian State or Union Territory.")
    district_entry = state_entry.get(_location_key(district_input))
    if district_entry is None:
        raise HTTPException(status_code=422, detail="Select a district that belongs to the selected State or Union Territory.")
    state, district = district_entry
    pin = (payload.pin_code or "").strip()
    if not re.fullmatch(r"[1-9][0-9]{5}", pin):
        raise HTTPException(status_code=422, detail="Enter a valid six-digit PIN code.")

    year = payload.year
    academic_stage = (payload.academic_stage or "").strip()
    subcategory = None
    if category == "nursing":
        allowed = {1, 2, 3, 4} if programme == "bsc_nursing" else {1, 2}
        if year not in allowed:
            raise HTTPException(status_code=422, detail="Select the current year for the selected Nursing programme.")
        academic_stage = f"Year {year}"
        stream = "nursing"
    elif category == "medical":
        subcategory = "UG" if programme == "medical_ug" else "PG"
        allowed = set(range(1, 6)) if subcategory == "UG" else {1, 2, 3}
        if year not in allowed:
            stage = "1st to 5th" if subcategory == "UG" else "1st to 3rd"
            raise HTTPException(status_code=422, detail=f"Select your current Medical {subcategory} year ({stage}).")
        academic_stage = f"Year {year}"
        stream = "mbbs_ug" if programme == "medical_ug" else "mbbs_pg"
    else:
        academic_stage = _required(academic_stage, "current year / semester / internship details", 120)
        stream = "paramedical"

    labels = {"nursing": "Nursing", "paramedical": "Paramedical", "medical": "Medical"}
    details = {
        "category": category,
        "category_label": labels[category],
        "programme": programme,
        "programme_label": PROGRAMMES[category][programme],
        "academic_stage": academic_stage,
        "stream": stream,
        "house_number": house,
        "address_line1": address1,
        "address_line2": address2,
        "district": district,
        "state": state,
        "pin_code": pin,
    }
    if category in {"nursing", "medical"}:
        details["year"] = year
    if category == "medical":
        details["subcategory"] = subcategory
        details["subcategory_label"] = f"Medical {subcategory}"
    return details
