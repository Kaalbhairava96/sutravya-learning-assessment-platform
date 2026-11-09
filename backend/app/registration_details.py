"""Server-side validation and pricing for the four QualiNova registration categories."""
from __future__ import annotations

import re
from fastapi import HTTPException

CATEGORY_FEES = {"nursing": 25000, "paramedical": 25000, "mbbs": 50000, "jdn": 100000}
CATEGORY_STREAMS = {
    "nursing": "nursing", "paramedical": "paramedical",
    "mbbs": "mbbs_1st_year", "jdn": "jdn",
}
PROGRAMMES = {
    "nursing": {"bsc_nursing": "B.Sc Nursing", "msc_nursing": "M.Sc Nursing"},
    "paramedical": {"bmlt": "BMLT", "bott": "BOTT", "bhm": "BHM", "bopt": "B.Opt", "brit": "BRIT"},
    "mbbs": {"mbbs": "MBBS"},
    "jdn": {"junior_doctor_network": "Junior Doctor Network"},
}
_MOBILE = re.compile(r"^[6-9][0-9]{9}$")


def _required(value: str | None, label: str, maximum: int = 240) -> str:
    cleaned = " ".join((value or "").split())
    if not cleaned or len(cleaned) > maximum:
        raise HTTPException(status_code=422, detail=f"Enter a valid {label}.")
    return cleaned


def build_registration_details(payload, session=None) -> dict:
    """Validate candidate details and calculate the fee; never trust client-supplied pricing."""
    category = (payload.category or "").strip().lower()
    if category not in CATEGORY_FEES:
        raise HTTPException(status_code=422, detail="Choose one of the four registration categories.")
    programme = (payload.programme or "").strip().lower()
    if programme not in PROGRAMMES[category]:
        raise HTTPException(status_code=422, detail="Choose a valid programme for the selected category.")
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
    district = _required(payload.district, "district", 120)
    state = _required(payload.state, "state", 120)
    pin = (payload.pin_code or "").strip()
    if not re.fullmatch(r"[1-9][0-9]{5}", pin):
        raise HTTPException(status_code=422, detail="Enter a valid six-digit PIN code.")

    year = payload.year
    academic_stage = (payload.academic_stage or "").strip()
    professional = {}
    if category == "nursing":
        allowed = {1, 2, 3, 4} if programme == "bsc_nursing" else {1, 2}
        if year not in allowed:
            raise HTTPException(status_code=422, detail="Select the current year for the selected Nursing programme.")
        academic_stage = f"Year {year}"
    elif category == "mbbs":
        if year not in {1, 2, 3, 4, 5}:
            raise HTTPException(status_code=422, detail="Select your current MBBS year (1st to 5th).")
        academic_stage = f"Year {year}"
    elif category == "paramedical":
        academic_stage = _required(academic_stage, "current year / semester / internship details", 120)
    else:
        professional = {
            "professional_qualification": _required(payload.professional_qualification, "professional qualification", 160),
            "designation": _required(payload.designation, "professional role / designation", 120),
            "institution": _required(payload.institution, "hospital / clinic / institution", 180),
            "council_name": " ".join((payload.council_name or "").split())[:160],
            "council_registration_number": " ".join((payload.council_registration_number or "").split())[:100],
            "years_of_experience": " ".join((payload.years_of_experience or "").split())[:40],
        }
        academic_stage = "Professional network"

    labels = {"nursing": "Nursing", "paramedical": "Paramedical", "mbbs": "MBBS", "jdn": "Junior Doctor Network (JDN)"}
    return {
        "category": category, "category_label": labels[category],
        "programme": programme, "programme_label": PROGRAMMES[category][programme],
        "year": year if category in {"nursing", "mbbs"} else None,
        "academic_stage": academic_stage, "stream": CATEGORY_STREAMS[category],
        "registration_fee_paise": CATEGORY_FEES[category], "currency": "INR",
        "payment_status": "pending",
        "house_number": house, "address_line1": address1, "address_line2": address2,
        "district": district, "state": state, "pin_code": pin, **professional,
    }
