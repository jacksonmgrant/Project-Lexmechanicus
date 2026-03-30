from __future__ import annotations

import os
from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from app.services.openai_llm import _build_context_brief
from app.services.retrieval import (
    _build_excerpt,
    _dedupe_and_focus_rows,
    _extract_best_quotes,
    _extract_focus_phrase,
    estimate_retrieval_quality,
)


class RulesAnsweringTests(unittest.TestCase):
    def test_extract_focus_phrase_strips_question_wrapper(self):
        self.assertEqual(_extract_focus_phrase("What is the benefit of cover?"), "benefit of cover")
        self.assertEqual(_extract_focus_phrase('How does "Fights First" work?'), "fights first")

    def test_build_excerpt_centers_rule_text(self):
        snippet = (
            "Introductory text that does not matter. "
            "BENEFIT OF COVER Each time a ranged attack is allocated to a model that has the Benefit of Cover, "
            "add 1 to the saving throw made for that attack. Multiple instances are not cumulative. "
            "Additional trailing text that is less important."
        )
        excerpt = _build_excerpt(snippet, "benefit of cover", ["benefit", "cover"])
        self.assertIn("BENEFIT OF COVER", excerpt)
        self.assertIn("add 1 to the saving throw", excerpt)

    def test_extract_best_quotes_prefers_operative_rule_over_flavor(self):
        snippet = (
            "Shattered ruins and twisted wreckage afford much-needed shelter from enemy salvoes. "
            "Each time a ranged attack is allocated to a model that has the Benefit of Cover, "
            "add 1 to the saving throw made for that attack. "
            "Models with a Save characteristic of 3+ or better cannot have the Benefit of Cover against attacks with an AP of 0."
        )
        quotes = _extract_best_quotes(snippet, "benefit of cover", ["benefit", "cover"])

        self.assertTrue(quotes)
        self.assertIn("Each time a ranged attack is allocated", quotes[0][0])
        self.assertNotIn("twisted wreckage", quotes[0][0].lower())

    def test_dedupe_and_focus_rows_prefers_exact_rule_match(self):
        rows = [
            {
                "id": 1,
                "file_id": 10,
                "title": None,
                "section": None,
                "snippet": "General terrain notes that mention visibility but not the actual cover benefit.",
                "file_title": "Core Rules",
                "filename": "core_rules.pdf",
                "source_title": "Core Rules",
                "rank": 0.35,
            },
            {
                "id": 2,
                "file_id": 10,
                "title": None,
                "section": None,
                "snippet": (
                    "BENEFIT OF COVER Each time a ranged attack is allocated to a model that has the Benefit of Cover, "
                    "add 1 to the saving throw made for that attack."
                ),
                "file_title": "Core Rules",
                "filename": "core_rules.pdf",
                "source_title": "Core Rules",
                "rank": 0.22,
            },
        ]

        focused = _dedupe_and_focus_rows(rows, "What is the benefit of cover?", k=2)

        self.assertEqual(focused[0]["id"], 2)
        self.assertIn("Benefit of Cover", focused[0]["excerpt"])
        self.assertIn("Benefit of Cover", focused[0]["key_quote"])
        self.assertGreater(focused[0]["match_score"], focused[1]["match_score"])

    def test_context_brief_uses_readable_rules_packet(self):
        brief = _build_context_brief(
            "What is the benefit of cover?",
            [
                {
                    "source_title": "Warhammer 40,000 Core Rules",
                    "section": "Terrain Features",
                    "excerpt": "Benefit of Cover: Add 1 to armour saving throws against ranged attacks.",
                    "key_quote": "Benefit of Cover: Add 1 to armour saving throws against ranged attacks.",
                    "filename": "core_rules.pdf",
                }
            ],
        )

        self.assertIn("User question:", brief)
        self.assertIn("Primary evidence", brief)
        self.assertIn("[c0] Source: Warhammer 40,000 Core Rules", brief)
        self.assertIn("Section: Terrain Features", brief)
        self.assertIn('Key quote: "Benefit of Cover: Add 1 to armour saving throws against ranged attacks."', brief)
        self.assertIn("Context excerpt: Benefit of Cover", brief)
        self.assertIn("Answer expectations:", brief)

    def test_context_brief_includes_recent_conversation(self):
        brief = _build_context_brief(
            "What about in ruins?",
            [
                {
                    "source_title": "Warhammer 40,000 Core Rules",
                    "section": "Terrain Features",
                    "excerpt": "Ruins can grant the Benefit of Cover to models obscured by terrain.",
                    "key_quote": "Ruins can grant the Benefit of Cover to models obscured by terrain.",
                    "filename": "core_rules.pdf",
                }
            ],
            [
                {"role": "user", "content": "What is the benefit of cover?"},
                {"role": "assistant", "content": "It adds 1 to armour saving throws against ranged attacks [[c0]]."},
            ],
        )

        self.assertIn("Recent conversation:", brief)
        self.assertIn("User: What is the benefit of cover?", brief)
        self.assertIn("Assistant: It adds 1 to armour saving throws", brief)

    def test_estimate_retrieval_quality_averages_top_chunks(self):
        quality = estimate_retrieval_quality(
            [
                {"match_score": 0.9},
                {"match_score": 0.6},
                {"match_score": 0.3},
                {"match_score": 0.1},
            ]
        )
        self.assertAlmostEqual(quality, 0.6)


if __name__ == "__main__":
    unittest.main()
