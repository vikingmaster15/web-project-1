import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import people_place_search_app


class BuildFeatureTests(unittest.TestCase):
    def test_build_research_summary_includes_person_place_and_sources(self) -> None:
        results = {
            "Person search": "https://example.com/person",
            "Place search": "https://example.com/place",
        }

        summary = people_place_search_app.build_research_summary(
            "Ada Lovelace",
            "London",
            results,
        )

        self.assertIn("Ada Lovelace", summary)
        self.assertIn("London", summary)
        self.assertIn("2", summary)
        self.assertIn("Person search", summary)

    def test_build_report_content_contains_sections(self) -> None:
        results = {
            "Person search": "https://example.com/person",
            "Place search": "https://example.com/place",
        }

        report = people_place_search_app.build_report_content(
            "Ada Lovelace",
            "London",
            results,
        )

        self.assertIn("Research report", report)
        self.assertIn("Ada Lovelace", report)
        self.assertIn("London", report)
        self.assertIn("Person search", report)

    def test_build_pdf_report_writes_pdf_file(self) -> None:
        results = {
            "Person search": "https://example.com/person",
            "Place search": "https://example.com/place",
        }
        output_path = Path(__file__).resolve().parent / "sample_report.pdf"
        if output_path.exists():
            output_path.unlink()

        created_path = people_place_search_app.build_pdf_report(
            "Ada Lovelace",
            "London",
            results,
            output_path=str(output_path),
        )

        self.assertTrue(Path(created_path).exists())
        self.assertIn(b"%PDF", Path(created_path).read_bytes()[:8])


if __name__ == "__main__":
    unittest.main()
