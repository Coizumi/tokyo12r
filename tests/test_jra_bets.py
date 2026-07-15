import datetime as dt
import unittest
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

bs4_stub = types.ModuleType("bs4")
bs4_stub.BeautifulSoup = object
sys.modules.setdefault("bs4", bs4_stub)

from jra_site_updater import (
    InternalHorse,
    JST,
    PublicPick,
    PublicRace,
    adjusted_race_class_score,
    adjusted_recent_weight,
    apply_class_rank_bonuses,
    bet_definitions,
    closing_3f_score,
    distance_adjustment_factor,
    freeze_started_predictions,
    is_winning_ticket,
    parse_closing_3f,
)


class JraPredictionFreezeTests(unittest.TestCase):
    @staticmethod
    def race(start_time: str, horse_number: str) -> PublicRace:
        return PublicRace(
            venue="東京",
            race_no=1,
            start_time=start_time,
            title="テスト競走",
            course="芝1600m",
            official_url="https://example.test/race",
            picks=[
                PublicPick(
                    mark="◎",
                    name=f"馬{horse_number}",
                    popularity_rank=1,
                    popularity_status="中間",
                    score=80.0,
                    note="",
                    horse_number=horse_number,
                )
            ],
        )

    def test_last_published_picks_are_kept_at_start_time(self):
        previous = self.race("12時00分", "1")
        refreshed = self.race("12時00分", "9")

        freeze_started_predictions(
            [refreshed],
            [previous],
            dt.date(2026, 7, 15),
            dt.datetime(2026, 7, 15, 12, 0, tzinfo=JST),
        )

        self.assertEqual(refreshed.picks[0].horse_number, "1")

    def test_picks_can_still_update_before_start_time(self):
        previous = self.race("12時00分", "1")
        refreshed = self.race("12時00分", "9")

        freeze_started_predictions(
            [refreshed],
            [previous],
            dt.date(2026, 7, 15),
            dt.datetime(2026, 7, 15, 11, 59, tzinfo=JST),
        )

        self.assertEqual(refreshed.picks[0].horse_number, "9")


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


class JraDistanceAndClassTests(unittest.TestCase):
    def test_distance_extension_and_shortening_factors(self):
        self.assertEqual(distance_adjustment_factor(1400, 1700), 0.985)
        self.assertEqual(distance_adjustment_factor(1200, 1700), 0.970)
        self.assertEqual(distance_adjustment_factor(1000, 1700), 0.955)
        self.assertEqual(distance_adjustment_factor(2100, 1700), 1.008)
        self.assertEqual(distance_adjustment_factor(2300, 1700), 1.015)
        self.assertEqual(distance_adjustment_factor(2400, 1700), 1.020)
        self.assertEqual(distance_adjustment_factor(1800, 1700), 1.0)

    def test_recent_weight_no_longer_adds_absolute_class_bonus(self):
        self.assertEqual(adjusted_recent_weight(1.0, "GI 1着"), 1.0)

    def test_class_score_is_halved_for_sixth_or_worse(self):
        self.assertEqual(adjusted_race_class_score("GI 5着"), 0.60)
        self.assertEqual(adjusted_race_class_score("GI 6着"), 0.30)
        self.assertEqual(adjusted_race_class_score("GI 9着"), 0.30)

    def test_class_rank_bonus_uses_race_relative_best_class(self):
        horses = [
            InternalHorse(number="1", name="A", past_texts=["GI 9着"]),
            InternalHorse(number="2", name="B", past_texts=["OP 1着"]),
            InternalHorse(number="3", name="C", past_texts=["GIII 2着"]),
            InternalHorse(number="4", name="D", past_texts=["1勝クラス 1着"]),
        ]

        apply_class_rank_bonuses(horses)

        self.assertEqual([horse.class_rank_bonus for horse in horses], [4.0, 4.0, 6.0, 0.0])


if __name__ == "__main__":
    unittest.main()
