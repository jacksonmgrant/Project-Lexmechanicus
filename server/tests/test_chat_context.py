from __future__ import annotations

import os
from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from app.services.chat_context import build_contextual_question, sanitize_chat_history


class ChatContextTests(unittest.TestCase):
    def test_sanitize_chat_history_strips_citations_and_invalid_roles(self):
        sanitized = sanitize_chat_history(
            [
                {"role": "system", "content": "ignore me"},
                {"role": "user", "content": "What is the benefit of cover?"},
                {"role": "assistant", "content": "It adds 1 to saves [[c0]]."},
            ]
        )

        self.assertEqual(
            sanitized,
            [
                {"role": "user", "content": "What is the benefit of cover?"},
                {"role": "assistant", "content": "It adds 1 to saves."},
            ],
        )

    def test_build_contextual_question_keeps_self_contained_question(self):
        history = [
            {"role": "user", "content": "Tell me about cover."},
            {"role": "assistant", "content": "Cover improves armour saves."},
        ]

        self.assertEqual(
            build_contextual_question("What is the benefit of cover?", history),
            "What is the benefit of cover?",
        )

    def test_build_contextual_question_expands_follow_up(self):
        history = [
            {"role": "user", "content": "What is the benefit of cover?"},
            {"role": "assistant", "content": "It adds 1 to armour saving throws against ranged attacks."},
        ]

        rewritten = build_contextual_question("What about in ruins?", history)

        self.assertIn("What is the benefit of cover?", rewritten)
        self.assertIn("What about in ruins?", rewritten)

    def test_build_contextual_question_uses_last_answer_for_short_follow_up(self):
        history = [
            {"role": "user", "content": "Can a unit shoot after advancing?"},
            {"role": "assistant", "content": "Normally no, unless a rule says it can."},
        ]

        rewritten = build_contextual_question("Why?", history)

        self.assertIn("Can a unit shoot after advancing?", rewritten)
        self.assertIn("Normally no, unless a rule says it can.", rewritten)
        self.assertTrue(rewritten.endswith("Why?"))


if __name__ == "__main__":
    unittest.main()
