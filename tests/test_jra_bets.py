import unittest
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

bs4_stub = types.ModuleType("bs4")
bs4_stub.BeautifulSoup = object
sys.modules.setdefault("bs4", bs4_stub)

from jra_site_updater import bet_definitions, closing_3f_score, is_winning_ticket, parse_closing_3f


class JraBetDefinitionTests(unittest.TestCase):
    def test_trio_formation_is_seven_unique_unordered_tickets(self):
        trio = next(section for section in bet_definitions() if section["label"] == "3連複フォーメーション")

        self.assertEqual(trio["formula"], "◎○ - ◎○▲ - ◎○▲△☆")
        self.assertEqual(trio["count"], 7)
        self.assertEqual(
            trio["tickets"],
            [
                ("◎", "○", "▲"),
                ("◎", "○", "△"),
                ("◎", "○", "☆"),
                ("◎", "▲", "△"),
                ("◎", "▲", "☆"),
                ("○", "▲", "△"),
                ("○", "▲", "☆"),
            ],
        )

    def test_trio_result_check_uses_the_seven_ticket_set(self):
        trio = next(section for section in bet_definitions() if section["label"] == "3連複フォーメーション")
        tickets = {tuple(ticket) for ticket in trio["tickets"]}

        self.assertTrue(any(is_winning_ticket(str(trio["label"]), ticket, ("○", "☆", "▲")) for ticket in tickets))
        self.assertFalse(any(is_winning_ticket(str(trio["label"]), ticket, ("▲", "△", "☆")) for ticket in tickets))


class JraClosingIndexTests(unittest.TestCase):
    def test_parse_closing_3f_from_past_text(self):
        self.assertEqual(parse_closing_3f("東京 芝1600 1:33.2 3F 34.1 1着 16頭"), 34.1)

    def test_front_runner_fast_closing_is_scored(self):
        front_runner = closing_3f_score(34.0, 1, 12, [1, 1, 1, 1])
        slower_front_runner = closing_3f_score(35.0, 1, 12, [1, 1, 1, 1])

        self.assertGreater(front_runner, slower_front_runner)

    def test_sixth_or_worse_is_discounted(self):
        placed = closing_3f_score(34.0, 2, 12, [4, 4, 3, 2])
        sixth = closing_3f_score(34.0, 6, 12, [4, 4, 3, 6])

        self.assertLess(sixth, placed)


if __name__ == "__main__":
    unittest.main()
