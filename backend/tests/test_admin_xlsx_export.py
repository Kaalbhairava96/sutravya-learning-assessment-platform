"""Focused tests for the native Excel registration workbook."""
from __future__ import annotations

import io
import unittest
import xml.etree.ElementTree as ET
import zipfile

from app.admin_router import _registrations_xlsx, _spreadsheet_safe


class RegistrationWorkbookTests(unittest.TestCase):
    def test_xlsx_contains_workbook_and_registration_worksheet(self):
        workbook = _registrations_xlsx([
            ("registration_id", "full_name", "pin_code"),
            ("HTSE-00001", "A Candidate", "847211"),
        ])

        with zipfile.ZipFile(io.BytesIO(workbook)) as archive:
            self.assertIn("[Content_Types].xml", archive.namelist())
            self.assertIn("xl/workbook.xml", archive.namelist())
            self.assertIn("xl/worksheets/sheet1.xml", archive.namelist())

            main_ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            worksheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
            rows = worksheet.findall(".//x:sheetData/x:row", main_ns)
            self.assertEqual(len(rows), 2)
            values = [
                cell.find("x:is/x:t", main_ns).text
                for cell in rows[1].findall("x:c", main_ns)
            ]
            self.assertEqual(values, ["HTSE-00001", "A Candidate", "847211"])

    def test_candidate_values_are_safe_as_excel_text(self):
        self.assertEqual(_spreadsheet_safe("=HYPERLINK(1)"), "'=HYPERLINK(1)")
        self.assertEqual(_spreadsheet_safe("  +1+1"), "'  +1+1")
        self.assertEqual(_spreadsheet_safe("A Candidate"), "A Candidate")


if __name__ == "__main__":
    unittest.main()
