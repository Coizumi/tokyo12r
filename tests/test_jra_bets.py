import datetime as dt
import json
import os
import tempfile
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
    PublicRunner,
    adjusted_race_class_score,
    adjusted_recent_weight,
    apply_class_rank_bonuses,
    bet_definitions,
    closing_3f_score,
    distance_adjustment_factor,
    freeze_started_predictions,
    is_winning_ticket,
    load_public_payload,
    parse_closing_3f,
    public_payload,
    render_picks,
    render_result_button,
    render_scores,
)
from jra_oci_batch import all_race_results_confirmed, generation_inputs_newer_than


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

    def test_render_picks_shows_score_between_name_and_popularity(self):
        race = PublicRace(
            venue="Tokyo",
            race_no=1,
            start_time="12:00",
            title="Test race",
            course="Turf 1600m",
            official_url="https://example.test/race",
            picks=[
                PublicPick(
                    mark="A",
                    name="Horse1",
                    popularity_rank=1,
                    popularity_status="mid",
                    score=80.0,
                    note="",
                    horse_number="1",
                )
            ],
        )

        html = render_picks(race)

        self.assertIn('class="pick-score"', html)
        self.assertIn(">80.0</span>", html)
        self.assertLess(html.index("Horse1"), html.index(">80.0</span>"))

    def test_public_payload_preserves_pick_score(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "public-data20260715.json"
            race = self.race("12:00", "1")
            race.runners = [
                PublicRunner(
                    number="1",
                    name="Horse1",
                    popularity_rank=2,
                    sire_name="",
                    dam_sire_name="",
                    score=72.4,
                )
            ]
            payload = public_payload(dt.date(2026, 7, 15), "2026-07-15 12:00:00 JST", [race])
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            races, _ = load_public_payload(path, dt.date(2026, 7, 15))

        self.assertEqual(races[0].picks[0].score, 80.0)
        self.assertEqual(races[0].runners[0].score, 72.4)

    def test_race_actions_include_score_link(self):
        html = render_result_button("20260715", self.race("12:00", "1"))

        self.assertIn("/result20260715.html#race-", html)
        self.assertIn("/scores20260715.html#race-", html)
        self.assertLess(html.index("レース結果"), html.index("全頭指数"))

    def test_render_scores_lists_all_runners_by_score(self):
        race = self.race("12:00", "1")
        race.runners = [
            PublicRunner("8", "Lower", 3, "", "", 31.2),
            PublicRunner("2", "Upper", 1, "", "", 88.8),
        ]

        html = render_scores("2026/07/15", "20260715", [race], "2026-07-15 12:00:00 JST")

        self.assertIn("全頭指数", html)
        self.assertIn('class="score-table"', html)
        self.assertIn(">88.8</span>", html)
        self.assertLess(html.index("Upper"), html.index("Lower"))


class JraBatchSkipTests(unittest.TestCase):
    def test_all_race_results_confirmed_requires_every_race_confirmed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            public_data = Path(temp_dir) / "public-data20260725.json"
            public_data.write_text(
                json.dumps(
                    {
                        "races": [
                            {"result_status": "確定", "result_rows": [{"rank": "1"}]},
                            {"result_status": "未確定", "result_rows": []},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            self.assertFalse(all_race_results_confirmed(public_data))

            public_data.write_text(
                json.dumps(
                    {
                        "races": [
                            {"result_status": "確定", "result_rows": [{"rank": "1"}]},
                            {"result_status": "確定", "result_rows": [{"rank": "1"}]},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            self.assertTrue(all_race_results_confirmed(public_data))

    def test_generation_inputs_newer_than_detects_script_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            generated = root / "site-dist" / "public-data20260725.json"
            source = root / "scripts" / "jra_site_updater.py"
            generated.parent.mkdir()
            source.parent.mkdir()
            generated.write_text("{}", encoding="utf-8")
            source.write_text("print('old')\n", encoding="utf-8")
            old_time = 1_700_000_000
            new_time = old_time + 100
            os.utime(source, (old_time, old_time))
            os.utime(generated, (new_time, new_time))

            self.assertFalse(generation_inputs_newer_than(root, generated))

            os.utime(source, (new_time + 100, new_time + 100))
            self.assertTrue(generation_inputs_newer_than(root, generated))


class JraBetDefinitionTests(unittest.TestCase):
    def test_trio_formation_is_seven_unique_unordered_tickets(self):
        trio = next(section for section in bet_definitions() if section["label"] == "3連複フォーメーション")

        self.assertEqual(trio["formula"], "◎○ - ◎○▲ - ▲△☆")
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
