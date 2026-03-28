from __future__ import annotations

from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.parsers import extract_document_title, should_replace_with_extracted_title, _pick_title_from_lines


class ParserTitleTests(unittest.TestCase):
    def test_pick_title_from_lines_prefers_multiline_title_over_boilerplate(self):
        title = _pick_title_from_lines(
            [
                "Games Workshop Ltd.",
                "Warhammer 40,000",
                "Core Rules",
                "Introduction",
            ],
            default_title="warhammer core rules",
        )
        self.assertEqual(title, "Warhammer 40,000 Core Rules")

    def test_markdown_title_uses_heading_after_frontmatter(self):
        content = b"---\nauthor: Someone\n---\n# Benefit of Cover\n\nRules text"
        title = extract_document_title("text/markdown", content, "benefit_of_cover.md")
        self.assertEqual(title, "Benefit of Cover")

    def test_text_title_skips_page_markers_and_urls(self):
        content = b"Page 1 of 2\nwww.example.com\nCodex: Space Marines\nRules follow here"
        title = extract_document_title("text/plain", content, "codex_space_marines.txt")
        self.assertEqual(title, "Codex: Space Marines")

    def test_blank_title_still_replaced(self):
        self.assertTrue(should_replace_with_extracted_title("", "core_rules.pdf"))


if __name__ == "__main__":
    unittest.main()
