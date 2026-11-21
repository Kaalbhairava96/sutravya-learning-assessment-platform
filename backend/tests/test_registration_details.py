"""Validation tests for QualiNova category and UG/PG registration."""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from app.registration_details import build_registration_details


def payload(**overrides):
    values = {
        "full_name": "Synthetic Candidate",
        "email": "candidate@example.invalid",
        "mobile": "9876543210",
        "category": "nursing",
        "programme": "bsc_nursing",
        "year": 1,
        "academic_stage": None,
        "house_number": "12",
        "address_line1": "Main Road",
        "address_line2": "Near Market",
        "district": "Patna",
        "state": "Bihar",
        "pin_code": "800001",
        "declaration_accepted": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class RegistrationDetailsTests(unittest.TestCase):
    def setUp(self):
        self.pin_locations = {
            "800001": (("Patna", "Bihar"),),
            "852201": (("Saharsa", "Bihar"),),
            "847211": (("Madhubani", "Bihar"),),
            "560001": (("Bengaluru Urban", "Karnataka"),),
        }
        lookup = patch(
            "app.postal_validation._fetch_postal_locations",
            side_effect=lambda pin: self.pin_locations.get(pin, ()),
        )
        lookup.start()
        self.addCleanup(lookup.stop)

    def test_nursing_programmes(self):
        bsc = build_registration_details(payload())
        self.assertEqual(bsc["programme_label"], "B.Sc Nursing")
        self.assertEqual(bsc["academic_stage"], "Year 1")
        msc = build_registration_details(payload(programme="msc_nursing", year=2))
        self.assertEqual(msc["programme_label"], "M.Sc Nursing")

    def test_nursing_year_must_match_selected_programme(self):
        with self.assertRaises(HTTPException) as rejected:
            build_registration_details(payload(programme="msc_nursing", year=4))
        self.assertEqual(rejected.exception.status_code, 422)

    def test_paramedical_programmes_accept_institution_defined_academic_stage(self):
        for programme in ("bmlt", "bott", "bhm", "bopt", "brit"):
            details = build_registration_details(payload(
                category="paramedical", programme=programme, year=None,
                academic_stage="Semester 4 / Internship",
            ))
            self.assertEqual(details["programme"], programme)
            self.assertEqual(details["stream"], "paramedical")

    def test_paramedical_requires_academic_stage(self):
        with self.assertRaises(HTTPException) as rejected:
            build_registration_details(payload(
                category="paramedical", programme="bmlt", year=None, academic_stage="",
            ))
        self.assertEqual(rejected.exception.status_code, 422)

    def test_medical_ug_and_pg_are_distinct_programmes_and_exam_streams(self):
        for year in range(1, 6):
            details = build_registration_details(payload(
                category="medical", programme="medical_ug", year=year,
            ))
            self.assertEqual(details["category"], "medical")
            self.assertEqual(details["subcategory"], "UG")
            self.assertEqual(details["stream"], "mbbs_ug")
            self.assertEqual(details["academic_stage"], f"Year {year}")
        for year in range(1, 4):
            details = build_registration_details(payload(
                category="medical", programme="medical_pg", year=year,
            ))
            self.assertEqual(details["subcategory"], "PG")
            self.assertEqual(details["stream"], "mbbs_pg")
        with self.assertRaises(HTTPException):
            build_registration_details(payload(category="mbbs", programme="mbbs_ug", year=6))
        with self.assertRaises(HTTPException):
            build_registration_details(payload(category="mbbs", programme="mbbs_pg", year=4))

    def test_legacy_mbbs_api_values_are_normalised_to_medical_labels(self):
        ug = build_registration_details(payload(category="mbbs", programme="mbbs_ug", year=5))
        self.assertEqual(ug["category"], "medical")
        self.assertEqual(ug["category_label"], "Medical")
        self.assertEqual(ug["programme"], "medical_ug")
        self.assertEqual(ug["programme_label"], "Medical UG")
        self.assertEqual(ug["stream"], "mbbs_ug")

        pg = build_registration_details(payload(category="mbbs", programme="mbbs_pg", year=2))
        self.assertEqual(pg["category"], "medical")
        self.assertEqual(pg["category_label"], "Medical")
        self.assertEqual(pg["programme"], "medical_pg")
        self.assertEqual(pg["programme_label"], "Medical PG")
        self.assertEqual(pg["stream"], "mbbs_pg")

    def test_jdn_is_rejected_for_new_registrations(self):
        with self.assertRaises(HTTPException) as rejected:
            build_registration_details(payload(category="jdn", programme="junior_doctor_network", year=None))
        self.assertEqual(rejected.exception.status_code, 422)

    def test_declaration_and_address_are_required(self):
        with self.assertRaises(HTTPException):
            build_registration_details(payload(declaration_accepted=False))
        with self.assertRaises(HTTPException):
            build_registration_details(payload(pin_code="12345"))


    def test_pin_code_must_match_selected_state_and_district(self):
        madhubani = build_registration_details(payload(
            state="Bihar", district="Madhubani", pin_code="847211",
        ))
        self.assertEqual(madhubani["district"], "Madhubani")
        self.assertEqual(madhubani["state"], "Bihar")

        with self.assertRaises(HTTPException) as wrong_district:
            build_registration_details(payload(
                state="Bihar", district="Madhubani", pin_code="560001",
            ))
        self.assertEqual(wrong_district.exception.status_code, 422)
        self.assertIn("Madhubani, Bihar", wrong_district.exception.detail)

        with self.assertRaises(HTTPException) as wrong_state:
            build_registration_details(payload(
                state="Karnataka", district="Bengaluru Urban", pin_code="847211",
            ))
        self.assertEqual(wrong_state.exception.status_code, 422)

    def test_unknown_pin_code_is_rejected(self):
        with self.assertRaises(HTTPException) as rejected:
            build_registration_details(payload(pin_code="999999"))
        self.assertEqual(rejected.exception.status_code, 422)
        self.assertIn("not found", rejected.exception.detail.lower())

    def test_pin_lookup_outage_fails_closed_with_retryable_error(self):
        from app.postal_validation import PostalLookupUnavailable
        with patch(
            "app.postal_validation._fetch_postal_locations",
            side_effect=PostalLookupUnavailable("directory unavailable"),
        ):
            with self.assertRaises(HTTPException) as rejected:
                build_registration_details(payload())
        self.assertEqual(rejected.exception.status_code, 503)

    def test_category_controls_fee_not_client_values(self):
        with self.assertRaises(HTTPException):
            build_registration_details(payload(category="other", programme="mbbs"))



    def test_all_indian_states_and_districts_are_loaded(self):
        from app.registration_details import _STATE_DATA, _STATE_DISTRICTS
        self.assertEqual(len(_STATE_DATA["states"]), 36)
        self.assertEqual(sum(len(item["districts"]) for item in _STATE_DATA["states"]), 790)
        self.assertEqual(len(_STATE_DISTRICTS["bihar"]), 38)
        self.assertIn("saharsa", _STATE_DISTRICTS["bihar"])
        self.assertEqual(len(_STATE_DISTRICTS["ladakh"]), 8)
        self.assertIn("sankoo", _STATE_DISTRICTS["ladakh"])

    def test_state_and_district_must_be_a_valid_pair(self):
        valid = build_registration_details(payload(state="Bihar", district="Saharsa", pin_code="852201"))
        self.assertEqual(valid["state"], "Bihar")
        self.assertEqual(valid["district"], "Saharsa")
        with self.assertRaises(HTTPException) as rejected:
            build_registration_details(payload(state="Bihar", district="Leh"))
        self.assertEqual(rejected.exception.status_code, 422)
        with self.assertRaises(HTTPException) as rejected_state:
            build_registration_details(payload(state="Atlantis", district="Patna"))
        self.assertEqual(rejected_state.exception.status_code, 422)

if __name__ == "__main__":
    unittest.main()
