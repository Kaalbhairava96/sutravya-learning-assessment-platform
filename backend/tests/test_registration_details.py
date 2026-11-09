"""Validation tests for category-specific QualiNova registration."""
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
        "professional_qualification": None,
        "designation": None,
        "institution": None,
        "council_name": None,
        "council_registration_number": None,
        "years_of_experience": None,
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
        self.assertEqual(msc["academic_stage"], "Year 2")

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
            self.assertEqual(details["academic_stage"], "Semester 4 / Internship")
            self.assertEqual(details["stream"], "paramedical")

    def test_paramedical_requires_academic_stage(self):
        with self.assertRaises(HTTPException) as rejected:
            build_registration_details(payload(
                category="paramedical", programme="bmlt", year=None, academic_stage="",
            ))
        self.assertEqual(rejected.exception.status_code, 422)

    def test_mbbs_years_one_through_five_and_fee(self):
        for year in range(1, 6):
            details = build_registration_details(payload(category="mbbs", programme="mbbs", year=year))
            self.assertEqual(details["registration_fee_paise"], 50000)
            self.assertEqual(details["stream"], "mbbs_1st_year")
            self.assertEqual(details["academic_stage"], f"Year {year}")
        with self.assertRaises(HTTPException):
            build_registration_details(payload(category="mbbs", programme="mbbs", year=6))

    def test_jdn_is_a_professional_category_not_an_exam_stream(self):
        details = build_registration_details(payload(
            category="jdn", programme="junior_doctor_network", year=None,
            professional_qualification="MBBS",
            designation="Resident Doctor",
            institution="District Hospital",
        ))
        self.assertEqual(details["registration_fee_paise"], 100000)
        self.assertEqual(details["stream"], "jdn")
        self.assertEqual(details["category_label"], "Junior Doctor Network (JDN)")
        self.assertNotIn("year", details)
        self.assertNotIn("registration_id", details)

    def test_jdn_requires_qualification_designation_and_institution(self):
        for key in ("professional_qualification", "designation", "institution"):
            with self.subTest(field=key):
                values = {
                    "category": "jdn",
                    "programme": "junior_doctor_network",
                    "year": None,
                    "professional_qualification": "MBBS",
                    "designation": "Resident Doctor",
                    "institution": "District Hospital",
                }
                values[key] = ""
                with self.assertRaises(HTTPException) as rejected:
                    build_registration_details(payload(**values))
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
