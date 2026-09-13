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

import jra_site_updater as updater
from jra_site_updater import (
    InternalHorse,
    JST,
    PublicPick,
    PublicRace,
    PublicResultRow,
    PublicRunner,
    adjusted_race_class_score,
    adjusted_recent_weight,
    apply_class_rank_bonuses,
    bet_definitions,
    freeze_started_predictions,
    is_winning_ticket,
    load_public_payload,
    parse_past_course_values,
    public_payload,
    render_picks,
    render_result_button,
    render_results,
    render_scores,
)
from jra_oci_batch import all_race_results_confirmed, generation_inputs_newer_than


class JraPredictionFreezeTests(unittest.TestCase):
    def test_race_heading_uses_venue_without_meeting_numbers(self):
        race = self.race("12:00", "1")
        race.venue = "4回中山1日"
        race.race_no = 12
        race.result_rows = [PublicResultRow("1", "1", "Test")]
        args = ("2026/09/05", "20260905", [race], "2026-09-05 12:00:00 JST")
        for render in (updater.render_index, render_results, render_scores):
            with self.subTest(page=render.__name__):
                page = render(*args)
                self.assertIn('class="race-no">中山12R</span>', page)
                self.assertIn(updater.race_anchor_id(race), page)

    def test_parses_adjacent_surface_and_finish_time(self):
        distance, surface, seconds = parse_past_course_values("2着 12頭 1200芝1:08.9 34.1")

        self.assertEqual(distance, 1200)
        self.assertEqual(surface, "芝")
        self.assertEqual(seconds, 68.9)

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
        race = self.race("12:00", "1")
        race.result_rows = [PublicResultRow(rank="1", horse_number="1", horse_name="Horse1")]
        html = render_result_button("20260715", race)

        self.assertIn("/result20260715.html#race-", html)
        self.assertIn("/scores20260715.html#race-", html)
        self.assertLess(html.index("レース結果"), html.index("全頭指数"))

    def test_race_actions_disable_result_link_without_confirmed_rows(self):
        html = render_result_button("20260715", self.race("12:00", "1"))

        self.assertIn('result-link disabled', html)
        self.assertNotIn('/result20260715.html#race-', html)
        self.assertIn('/scores20260715.html#race-', html)

    def test_results_page_omits_races_without_confirmed_rows(self):
        confirmed = self.race("12:00", "1")
        confirmed.result_rows = [PublicResultRow(rank="1", horse_number="1", horse_name="Confirmed")]
        pending = self.race("12:30", "2")
        pending.title = "Pending race"

        html = render_results("2026/08/08", "20260808", [confirmed, pending], "2026-08-08 12:00:00 JST")

        self.assertIn("Confirmed", html)
        self.assertNotIn("Pending race", html)

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
    def test_wide_and_trio_box_definitions(self):
        wide = next(section for section in bet_definitions() if section["label"] == "ワイドBOX")
        trio = next(section for section in bet_definitions() if section["label"] == "3連複BOX")

        self.assertEqual(wide["formula"], "○▲△ BOX")
        self.assertEqual(wide["count"], 3)
        self.assertEqual(wide["tickets"], [("○", "▲"), ("○", "△"), ("▲", "△")])
        self.assertEqual(trio["formula"], "◎○▲△☆ BOX")
        self.assertEqual(trio["count"], 10)
        self.assertEqual(
            trio["tickets"],
            [
                ("◎", "○", "▲"),
                ("◎", "○", "△"),
                ("◎", "○", "☆"),
                ("◎", "▲", "△"),
                ("◎", "▲", "☆"),
                ("◎", "△", "☆"),
                ("○", "▲", "△"),
                ("○", "▲", "☆"),
                ("○", "△", "☆"),
                ("▲", "△", "☆"),
            ],
        )

    def test_pre_august_second_bets_remain_legacy_definitions(self):
        sections = bet_definitions(dt.date(2026, 8, 1))

        self.assertEqual(sections[0]["label"], "馬連フォーメーション")
        self.assertEqual(sections[1]["label"], "3連複フォーメーション")
        self.assertEqual(sections[1]["count"], 7)

    def test_august_second_to_seventh_bets_remain_single_win(self):
        sections = bet_definitions(dt.date(2026, 8, 7))

        self.assertEqual(sections[0]["label"], "単勝")
        self.assertEqual(sections[0]["count"], 1)

    def test_august_fourteenth_keeps_umaren_before_wide_start(self):
        sections = bet_definitions(dt.date(2026, 8, 14))

        self.assertEqual(sections[0]["label"], "馬連フォーメーション")
        self.assertEqual(sections[0]["count"], 4)

    def test_wide_and_trio_result_check_use_the_new_ticket_sets(self):
        wide = next(section for section in bet_definitions() if section["label"] == "ワイドBOX")
        trio = next(section for section in bet_definitions() if section["label"] == "3連複BOX")
        tickets = {tuple(ticket) for ticket in trio["tickets"]}

        self.assertTrue(is_winning_ticket(str(wide["label"]), ("○", "▲"), ("○", "◎", "▲")))
        self.assertTrue(is_winning_ticket(str(wide["label"]), ("○", "△"), ("○", "△", "▲")))
        self.assertTrue(is_winning_ticket(str(wide["label"]), ("▲", "△"), (None, "△", "▲")))
        self.assertFalse(is_winning_ticket(str(wide["label"]), ("○", "△"), ("○", "◎", "▲")))
        self.assertEqual(updater.section_payout_type(str(wide["label"])), "ワイド")
        self.assertTrue(any(is_winning_ticket(str(trio["label"]), ticket, ("○", "☆", "▲")) for ticket in tickets))
        self.assertTrue(any(is_winning_ticket(str(trio["label"]), ticket, ("▲", "△", "☆")) for ticket in tickets))

    def test_wide_outcome_lists_each_winning_combination_and_payout(self):
        race = PublicRace(
            venue="Tokyo",
            race_no=1,
            start_time="12:00",
            title="Test",
            course="Turf 1600m",
            official_url="https://example.test",
            picks=[
                PublicPick("◎", "Top", None, "", 80.0, "", "1"),
                PublicPick("○", "Second", None, "", 79.0, "", "2"),
                PublicPick("▲", "Third", None, "", 78.0, "", "3"),
                PublicPick("△", "Fourth", None, "", 77.0, "", "4"),
                PublicPick("☆", "Fifth", None, "", 76.0, "", "5"),
            ],
            result_rows=[
                PublicResultRow("1", "2", "Second"),
                PublicResultRow("2", "3", "Third"),
                PublicResultRow("3", "4", "Fourth"),
            ],
            payouts=[
                updater.PublicPayout("ワイド", "2-3", "240円"),
                updater.PublicPayout("ワイド", "2-4", "310円"),
                updater.PublicPayout("ワイド", "3-4", "420円"),
            ],
        )

        outcome = updater.bet_outcomes(race, dt.date(2026, 8, 15))[0]

        self.assertEqual(outcome["status"], "hit")
        self.assertEqual(
            outcome["payout_details"],
            [
                {"ticket": "○-▲", "amount": "240円"},
                {"ticket": "○-△", "amount": "310円"},
                {"ticket": "▲-△", "amount": "420円"},
            ],
        )


class MuddySireBonusTests(unittest.TestCase):
    @staticmethod
    def race(course: str, going: str) -> PublicRace:
        return PublicRace(
            venue="東京",
            race_no=1,
            start_time="12:00",
            title="テスト競走",
            course=course,
            official_url="https://example.test/race",
            going=going,
        )

    def test_heavy_or_sloppy_going_adds_the_capped_sire_bonus(self):
        self.assertEqual(updater.muddy_sire_bonus("キズナ", "牡4", self.race("芝1600m", "重")), 1.8)
        self.assertEqual(updater.muddy_sire_bonus("マジェスティックウォリアー", "牡4", self.race("ダート1400m", "不良")), 1.8)

    def test_slightly_heavy_or_wrong_surface_does_not_add_the_bonus(self):
        self.assertEqual(updater.muddy_sire_bonus("キズナ", "牡4", self.race("芝1600m", "稍重")), 0.0)
        self.assertEqual(updater.muddy_sire_bonus("キズナ", "牡4", self.race("ダート1400m", "重")), 0.0)

    def test_sex_restricted_sires_require_the_matching_sex(self):
        race = self.race("ダート1400m", "重")
        self.assertEqual(updater.muddy_sire_bonus("キンシャサノキセキ", "牡4", race), 1.8)
        self.assertEqual(updater.muddy_sire_bonus("キンシャサノキセキ", "牝4", race), 0.0)

    def test_bonus_is_added_directly_to_the_unified_score(self):
        horse = InternalHorse(number="1", name="Boosted", sire_name="キズナ", sex_age="牡4", past_texts=["5着 10頭"])

        updater.make_picks([horse], race=self.race("芝1600m", "良"))
        dry_score = horse.score
        updater.make_picks([horse], race=self.race("芝1600m", "重"))

        self.assertAlmostEqual(horse.score - dry_score, 1.8)

    def test_detail_going_parser_uses_the_current_surface(self):
        detail = "天候：雨 芝：重 ダート：良"
        self.assertEqual(updater.parse_going_from_detail(detail, "芝1600m"), "重")
        self.assertEqual(updater.parse_going_from_detail(detail, "ダート1400m"), "良")


class JraClassTests(unittest.TestCase):
    def test_recent_weight_no_longer_adds_absolute_class_bonus(self):
        self.assertEqual(adjusted_recent_weight(1.0, "GI 1着"), 1.0)

    def test_class_score_is_halved_for_sixth_or_worse(self):
        self.assertEqual(adjusted_race_class_score("GI 5着"), 0.60)
        self.assertEqual(adjusted_race_class_score("GI 6着"), 0.30)
        self.assertEqual(adjusted_race_class_score("GI 9着"), 0.30)


class JraUnifiedScoreTests(unittest.TestCase):
    def test_prize_money_does_not_change_base_score(self):
        no_prize = InternalHorse(number="1", name="No prize", sex_age="牡3 56.0", past_texts=["2着 10頭 3番人気"])
        high_prize = InternalHorse(
            number="1",
            name="High prize",
            sex_age="牡8 56.0",
            prize_yen=2_000_000_000,
            past_texts=["2着 10頭 3番人気"],
        )

        self.assertEqual(updater.score_horse(no_prize), updater.score_horse(high_prize))

    def test_four_run_cards_use_the_unified_score_path(self):
        horses = [
            InternalHorse(number=str(number), name=f"Horse {number}", past_texts=["1着 10頭 1番人気"] * 4)
            for number in range(1, 6)
        ]
        race = PublicRace(
            venue="東京",
            race_no=1,
            start_time="12:00",
            title="Test",
            course="芝1600m",
            official_url="https://example.test",
        )

        picks = updater.make_picks(horses, race=race)

        self.assertEqual([pick.horse_number for pick in picks], ["1", "2", "3", "4", "5"])
        self.assertAlmostEqual(horses[0].score, updater.score_horse(horses[0]) + horses[0].sire_fit_score * 0.08)

    def test_class_rank_bonus_uses_race_relative_best_class(self):
        horses = [
            InternalHorse(number="1", name="A", past_texts=["GI 9着"]),
            InternalHorse(number="2", name="B", past_texts=["OP 1着"]),
            InternalHorse(number="3", name="C", past_texts=["GIII 2着"]),
            InternalHorse(number="4", name="D", past_texts=["1勝クラス 1着"]),
        ]

        apply_class_rank_bonuses(horses)

        self.assertEqual([horse.class_rank_bonus for horse in horses], [4.0, 4.0, 6.0, 0.0])

    def test_grade_target_ignores_two_and_three_win_class_scores(self):
        horses = [
            InternalHorse(number="1", name="ThreeWins", past_texts=["3勝クラス 1着"]),
            InternalHorse(number="2", name="TwoWins", past_texts=["2勝クラス 1着"]),
            InternalHorse(number="3", name="Open", past_texts=["OP 1着"]),
            InternalHorse(number="4", name="GradeTwo", past_texts=["GII 1着"]),
        ]
        grade_race = PublicRace(
            venue="東京",
            race_no=11,
            start_time="15:45",
            title="テストステークス GIII",
            course="芝1600m",
            official_url="https://example.test/race",
        )

        apply_class_rank_bonuses(horses, grade_race)

        self.assertTrue(updater.is_grade_race(grade_race))
        self.assertEqual(adjusted_race_class_score("3勝クラス 1着", grade_target=True), 0.0)
        self.assertEqual(adjusted_race_class_score("2勝クラス 1着", grade_target=True), 0.0)
        self.assertEqual(adjusted_race_class_score("OP 1着", grade_target=True), 0.3)
        self.assertEqual([horse.class_rank_bonus for horse in horses], [0.0, 0.0, 4.0, 6.0])

    def test_grade_detection_supports_roman_grade_notation(self):
        for title in ("テスト GI", "テスト GII", "テスト GIII", "テスト G1", "テスト G2", "テスト G3", "テスト GⅢ"):
            race = PublicRace(
                venue="東京",
                race_no=11,
                start_time="15:45",
                title=title,
                course="芝1600m",
                official_url="https://example.test/race",
            )
            self.assertTrue(updater.is_grade_race(race))


class CourseBiasTests(unittest.TestCase):
    @staticmethod
    def race(course: str, venue: str = "阪神", title: str = "テスト競走") -> PublicRace:
        return PublicRace(
            venue=venue,
            race_no=1,
            start_time="12:00",
            title=title,
            course=course,
            official_url="https://example.test/race",
        )

    @staticmethod
    def horse(
        number: str,
        frame: str,
        *,
        past: str = "",
        sire: str = "",
    ) -> InternalHorse:
        return InternalHorse(
            number=number,
            name=f"馬{number}",
            frame_number=frame,
            past_texts=[past] if past else [],
            sire_name=sire,
        )

    def test_hanshin_dirt_1400_strongly_favors_outer_frame(self):
        inner = self.horse("1", "1")
        outer = self.horse("16", "8")
        updater.apply_course_bias([inner, outer], self.race("ダート 1,400 m"))

        self.assertEqual(inner.course_bias_score, -5.0)
        self.assertEqual(outer.course_bias_score, 5.0)

    def test_hanshin_turf_2000_favors_inside_frame(self):
        inside_front = self.horse("1", "1")
        outside_closer = self.horse("16", "8")
        updater.apply_course_bias([inside_front, outside_closer], self.race("芝 2,000 m"))

        self.assertEqual(inside_front.course_bias_score, 3.0)
        self.assertEqual(outside_closer.course_bias_score, -3.0)

    def test_hanshin_turf_1400_shortener_requires_many_sprint_extenders(self):
        shortener = self.horse("1", "1", past="1着 12頭 1600芝1:34.0")
        sprinter_one = self.horse("2", "2", past="1着 12頭 1200芝1:08.9")
        sprinter_two = self.horse("3", "2", past="2着 12頭 1200芝1:09.0")
        updater.apply_course_bias([shortener, sprinter_one, sprinter_two], self.race("芝 1,400 m"))

        self.assertEqual(shortener.course_bias_score, 2.0)

        updater.apply_course_bias([shortener, self.horse("2", "2", past="1着 12頭 1400芝1:21.0")], self.race("芝 1,400 m"))
        self.assertEqual(shortener.course_bias_score, 0.0)

    def test_kyoto_dirt_1900_favors_inside_frame(self):
        inside_closer = self.horse("1", "1")
        outer_fader = self.horse("16", "8")
        updater.apply_course_bias([inside_closer, outer_fader], self.race("ダート 1,900 m", venue="京都"))

        self.assertEqual(inside_closer.course_bias_score, 2.0)
        self.assertEqual(outer_fader.course_bias_score, -2.0)

    def test_kyoto_turf_1600_favors_shortener(self):
        shortener = self.horse("1", "1", past="1着 12頭 1800芝1:46.0")
        extender = self.horse("2", "2", past="1着 12頭 1200芝1:08.9")
        updater.apply_course_bias([shortener, extender], self.race("芝 1,600 m", venue="京都"))

        self.assertEqual(shortener.course_bias_score, 1.2)
        self.assertEqual(extender.course_bias_score, 0.0)

    def test_fukushima_turf_2000_rewards_kizuna(self):
        kizuna = self.horse("1", "1", sire="キズナ")
        other = self.horse("2", "2", sire="その他")
        updater.apply_course_bias([kizuna, other], self.race("芝 2,000 m", venue="福島"))

        self.assertEqual(kizuna.course_bias_score, 1.5)
        self.assertEqual(other.course_bias_score, 0.0)

    def test_fukushima_turf_1200_reverses_with_explicit_course_layout(self):
        inner_front = self.horse("1", "1")
        outer_closer = self.horse("16", "8")
        updater.apply_course_bias([inner_front, outer_closer], self.race("芝 1,200 m Aコース", venue="福島"))
        self.assertEqual(inner_front.course_bias_score, 2.0)

        updater.apply_course_bias([inner_front, outer_closer], self.race("芝 1,200 m Bコース", venue="福島"))
        self.assertEqual(outer_closer.course_bias_score, 2.0)

    def test_fukushima_turf_1200_is_neutral_without_explicit_course_layout(self):
        inner_front = self.horse("1", "1")
        outer_closer = self.horse("16", "8")
        updater.apply_course_bias([inner_front, outer_closer], self.race("芝 1,200 m", venue="福島"))

        self.assertEqual(inner_front.course_bias_score, 0.0)
        self.assertEqual(outer_closer.course_bias_score, 0.0)


if __name__ == "__main__":
    unittest.main()
