"""Validation tests for QualiNova category and UG/PG registration."""
from __future__ import annotations

import unittest
from types import SimpleNamespace

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
    def test_nursing_programmes_and_fee(self):
        bsc = build_registration_details(payload())
        self.assertEqual(bsc["registration_fee_paise"], 25000)
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
            self.assertEqual(details["registration_fee_paise"], 25000)
            self.assertEqual(details["programme"], programme)
            self.assertEqual(details["stream"], "paramedical")

    def test_paramedical_requires_academic_stage(self):
        with self.assertRaises(HTTPException) as rejected:
            build_registration_details(payload(
                category="paramedical", programme="bmlt", year=None, academic_stage="",
            ))
        self.assertEqual(rejected.exception.status_code, 422)

    def test_mbbs_ug_and_pg_are_distinct_subcategories_and_exam_streams(self):
        for year in range(1, 6):
            details = build_registration_details(payload(
                category="mbbs", programme="mbbs_ug", year=year,
            ))
            self.assertEqual(details["category"], "mbbs")
            self.assertEqual(details["subcategory"], "UG")
            self.assertEqual(details["stream"], "mbbs_ug")
            self.assertEqual(details["registration_fee_paise"], 50000)
            self.assertEqual(details["academic_stage"], f"Year {year}")
        for year in range(1, 4):
            details = build_registration_details(payload(
                category="mbbs", programme="mbbs_pg", year=year,
            ))
            self.assertEqual(details["subcategory"], "PG")
            self.assertEqual(details["stream"], "mbbs_pg")
            self.assertEqual(details["registration_fee_paise"], 50000)
        with self.assertRaises(HTTPException):
            build_registration_details(payload(category="mbbs", programme="mbbs_ug", year=6))
        with self.assertRaises(HTTPException):
            build_registration_details(payload(category="mbbs", programme="mbbs_pg", year=4))

    def test_jdn_is_rejected_for_new_registrations(self):
        with self.assertRaises(HTTPException) as rejected:
            build_registration_details(payload(category="jdn", programme="junior_doctor_network", year=None))
        self.assertEqual(rejected.exception.status_code, 422)

    def test_declaration_and_address_are_required(self):
        with self.assertRaises(HTTPException):
            build_registration_details(payload(declaration_accepted=False))
        with self.assertRaises(HTTPException):
            build_registration_details(payload(pin_code="12345"))

    def test_category_controls_fee_not_client_values(self):
        with self.assertRaises(HTTPException):
            build_registration_details(payload(category="other", programme="mbbs"))


if __name__ == "__main__":
    unittest.main()
