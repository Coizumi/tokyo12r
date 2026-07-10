import unittest
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

bs4_stub = types.ModuleType("bs4")
bs4_stub.BeautifulSoup = object
sys.modules.setdefault("bs4", bs4_stub)

from jra_site_updater import bet_definitions, is_winning_ticket


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


if __name__ == "__main__":
    unittest.main()
