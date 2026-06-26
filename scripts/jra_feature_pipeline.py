#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
SCHEMA_VERSION = 2


@dataclass(frozen=True)
class SireAptitude:
    name: str
    surface_axis: int
    distance_m: int
    confidence: str
    source: str


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def init_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sire_aptitude (
            sire_name TEXT PRIMARY KEY,
            surface_axis INTEGER NOT NULL,
            distance_m INTEGER NOT NULL,
            confidence TEXT NOT NULL,
            source TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS races (
            race_id TEXT PRIMARY KEY,
            race_date TEXT NOT NULL,
            venue TEXT NOT NULL,
            race_no INTEGER NOT NULL,
            surface TEXT NOT NULL,
            distance_m INTEGER NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS race_entries (
            race_id TEXT NOT NULL,
            horse_id TEXT NOT NULL,
            horse_name TEXT NOT NULL,
            sire_name TEXT NOT NULL DEFAULT '',
            horse_number INTEGER,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (race_id, horse_id),
            FOREIGN KEY (race_id) REFERENCES races(race_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS past_performances (
            horse_id TEXT NOT NULL,
            race_date TEXT NOT NULL,
            surface TEXT NOT NULL,
            distance_m INTEGER NOT NULL,
            finish_time_seconds REAL,
            last3f_seconds REAL,
            field_size INTEGER,
            finish_position INTEGER,
            corner_positions TEXT,
            margin_seconds REAL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (horse_id, race_date, surface, distance_m)
        );

        CREATE TABLE IF NOT EXISTS runner_features (
            race_id TEXT NOT NULL,
            horse_id TEXT NOT NULL,
            sire_fit_score REAL,
            time_index REAL,
            closing_index REAL,
            pace_index REAL,
            generated_at TEXT NOT NULL,
            PRIMARY KEY (race_id, horse_id),
            FOREIGN KEY (race_id, horse_id)
                REFERENCES race_entries(race_id, horse_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS predictions (
            race_id TEXT NOT NULL,
            horse_id TEXT NOT NULL,
            mark TEXT NOT NULL,
            horse_number INTEGER,
            horse_name TEXT NOT NULL,
            popularity_rank INTEGER,
            popularity_status TEXT NOT NULL DEFAULT '',
            generated_at TEXT NOT NULL,
            PRIMARY KEY (race_id, mark),
            FOREIGN KEY (race_id) REFERENCES races(race_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS bet_tickets (
            race_id TEXT NOT NULL,
            bet_type TEXT NOT NULL,
            ticket_key TEXT NOT NULL,
            stake_yen INTEGER NOT NULL DEFAULT 100,
            generated_at TEXT NOT NULL,
            PRIMARY KEY (race_id, bet_type, ticket_key),
            FOREIGN KEY (race_id) REFERENCES races(race_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS race_results (
            race_id TEXT NOT NULL,
            finish_position INTEGER NOT NULL,
            horse_id TEXT NOT NULL DEFAULT '',
            horse_number INTEGER,
            horse_name TEXT NOT NULL,
            result_status TEXT NOT NULL DEFAULT 'confirmed',
            source_url TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            PRIMARY KEY (race_id, finish_position),
            FOREIGN KEY (race_id) REFERENCES races(race_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS payouts (
            race_id TEXT NOT NULL,
            bet_type TEXT NOT NULL,
            ticket_key TEXT NOT NULL,
            payout_yen INTEGER NOT NULL,
            popularity TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            PRIMARY KEY (race_id, bet_type, ticket_key),
            FOREIGN KEY (race_id) REFERENCES races(race_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS bet_outcomes (
            race_id TEXT NOT NULL,
            bet_type TEXT NOT NULL,
            ticket_key TEXT NOT NULL,
            is_hit INTEGER NOT NULL,
            stake_yen INTEGER NOT NULL,
            payout_yen INTEGER NOT NULL,
            profit_yen INTEGER NOT NULL,
            evaluated_at TEXT NOT NULL,
            PRIMARY KEY (race_id, bet_type, ticket_key),
            FOREIGN KEY (race_id) REFERENCES races(race_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS performance_summaries (
            period_type TEXT NOT NULL,
            period_key TEXT NOT NULL,
            bet_type TEXT NOT NULL,
            races INTEGER NOT NULL,
            tickets INTEGER NOT NULL,
            hits INTEGER NOT NULL,
            stake_yen INTEGER NOT NULL,
            payout_yen INTEGER NOT NULL,
            profit_yen INTEGER NOT NULL,
            hit_rate REAL NOT NULL,
            roi REAL NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (period_type, period_key, bet_type)
        );

        CREATE TABLE IF NOT EXISTS pipeline_runs (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            message TEXT NOT NULL DEFAULT ''
        );
        """
    )
    connection.execute(
        "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
        ("schema_version", str(SCHEMA_VERSION)),
    )
    connection.commit()


def load_sire_csv(path: Path) -> list[SireAptitude]:
    rows: list[SireAptitude] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for item in csv.DictReader(handle):
            rows.append(
                SireAptitude(
                    name=item["sire_name"],
                    surface_axis=int(item["surface_axis"]),
                    distance_m=int(item["distance_m"]),
                    confidence=item["confidence"],
                    source=item["source"],
                )
            )
    return rows


def import_sires(connection: sqlite3.Connection, sires: list[SireAptitude], updated_at: str) -> None:
    connection.executemany(
        """
        INSERT INTO sire_aptitude(
            sire_name, surface_axis, distance_m, confidence, source, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(sire_name) DO UPDATE SET
            surface_axis=excluded.surface_axis,
            distance_m=excluded.distance_m,
            confidence=excluded.confidence,
            source=excluded.source,
            updated_at=excluded.updated_at
        """,
        [
            (
                sire.name,
                sire.surface_axis,
                sire.distance_m,
                sire.confidence,
                sire.source,
                updated_at,
            )
            for sire in sires
        ],
    )
    connection.commit()


def surface_to_axis(surface: str) -> int:
    normalized = surface.strip().lower()
    if normalized in {"芝", "turf"}:
        return 100
    if normalized in {"ダート", "dirt"}:
        return -100
    return 0


def sire_fit_score(sire: SireAptitude | None, surface: str, distance_m: int) -> float:
    if sire is None:
        return 50.0
    target_axis = surface_to_axis(surface)
    surface_fit = 1.0 - min(abs(sire.surface_axis - target_axis), 200) / 200
    distance_fit = 1.0 - min(abs(sire.distance_m - distance_m), 600) / 600
    return round((surface_fit * 0.55 + distance_fit * 0.45) * 100, 3)


def fetch_sire(connection: sqlite3.Connection, sire_name: str) -> SireAptitude | None:
    row = connection.execute(
        """
        SELECT sire_name, surface_axis, distance_m, confidence, source
        FROM sire_aptitude
        WHERE sire_name = ?
        """,
        (sire_name,),
    ).fetchone()
    if row is None:
        return None
    return SireAptitude(
        name=str(row["sire_name"]),
        surface_axis=int(row["surface_axis"]),
        distance_m=int(row["distance_m"]),
        confidence=str(row["confidence"]),
        source=str(row["source"]),
    )


def refresh_runner_features(connection: sqlite3.Connection, generated_at: str) -> int:
    rows = connection.execute(
        """
        SELECT e.race_id, e.horse_id, e.sire_name, r.surface, r.distance_m
        FROM race_entries e
        JOIN races r ON r.race_id = e.race_id
        """
    ).fetchall()
    written = 0
    for row in rows:
        sire = fetch_sire(connection, str(row["sire_name"]))
        fit = sire_fit_score(sire, str(row["surface"]), int(row["distance_m"]))
        connection.execute(
            """
            INSERT INTO runner_features(
                race_id, horse_id, sire_fit_score, time_index,
                closing_index, pace_index, generated_at
            )
            VALUES (?, ?, ?, NULL, NULL, NULL, ?)
            ON CONFLICT(race_id, horse_id) DO UPDATE SET
                sire_fit_score=excluded.sire_fit_score,
                generated_at=excluded.generated_at
            """,
            (row["race_id"], row["horse_id"], fit, generated_at),
        )
        written += 1
    connection.commit()
    return written


def period_keys(race_date: str) -> dict[str, str]:
    parsed = dt.date.fromisoformat(race_date)
    iso_year, iso_week, _ = parsed.isocalendar()
    return {
        "weekly": f"{iso_year}-W{iso_week:02d}",
        "monthly": parsed.strftime("%Y-%m"),
        "yearly": parsed.strftime("%Y"),
    }


def refresh_performance_summaries(connection: sqlite3.Connection, updated_at: str) -> int:
    rows = connection.execute(
        """
        SELECT r.race_date, o.race_id, o.bet_type, o.is_hit,
               o.stake_yen, o.payout_yen, o.profit_yen
        FROM bet_outcomes o
        JOIN races r ON r.race_id = o.race_id
        """
    ).fetchall()
    aggregates: dict[tuple[str, str, str], dict[str, object]] = {}
    for row in rows:
        for period_type, period_key in period_keys(str(row["race_date"])).items():
            key = (period_type, period_key, str(row["bet_type"]))
            item = aggregates.setdefault(
                key,
                {
                    "tickets": 0,
                    "hits": 0,
                    "stake_yen": 0,
                    "payout_yen": 0,
                    "profit_yen": 0,
                    "race_ids": set(),
                },
            )
            item["tickets"] = int(item["tickets"]) + 1
            item["hits"] = int(item["hits"]) + int(row["is_hit"])
            item["stake_yen"] = int(item["stake_yen"]) + int(row["stake_yen"])
            item["payout_yen"] = int(item["payout_yen"]) + int(row["payout_yen"])
            item["profit_yen"] = int(item["profit_yen"]) + int(row["profit_yen"])
            race_ids = item["race_ids"]
            if isinstance(race_ids, set):
                race_ids.add(str(row["race_id"]))

    connection.execute("DELETE FROM performance_summaries")
    for (period_type, period_key, bet_type), item in aggregates.items():
        race_ids = item["race_ids"]
        race_count = len(race_ids) if isinstance(race_ids, set) else 0
        tickets = int(item["tickets"])
        hits = int(item["hits"])
        stake_yen = int(item["stake_yen"])
        payout_yen = int(item["payout_yen"])
        profit_yen = int(item["profit_yen"])
        hit_rate = hits / tickets if tickets else 0.0
        roi = payout_yen / stake_yen if stake_yen else 0.0
        connection.execute(
            """
            INSERT INTO performance_summaries(
                period_type, period_key, bet_type, races, tickets, hits,
                stake_yen, payout_yen, profit_yen, hit_rate, roi, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                period_type,
                period_key,
                bet_type,
                int(race_count),
                tickets,
                hits,
                stake_yen,
                payout_yen,
                profit_yen,
                round(hit_rate, 6),
                round(roi, 6),
                updated_at,
            ),
        )
    connection.commit()
    return len(aggregates)


def export_public_features(connection: sqlite3.Connection, output: Path, generated_at: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    sire_count = connection.execute("SELECT COUNT(*) AS count FROM sire_aptitude").fetchone()["count"]
    feature_count = connection.execute("SELECT COUNT(*) AS count FROM runner_features").fetchone()["count"]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "sire_aptitude_count": sire_count,
        "runner_feature_count": feature_count,
        "performance_summaries": [
            {
                "period_type": row["period_type"],
                "period_key": row["period_key"],
                "bet_type": row["bet_type"],
                "races": row["races"],
                "tickets": row["tickets"],
                "hits": row["hits"],
                "stake_yen": row["stake_yen"],
                "payout_yen": row["payout_yen"],
                "profit_yen": row["profit_yen"],
                "hit_rate": row["hit_rate"],
                "roi": row["roi"],
            }
            for row in connection.execute(
                """
                SELECT period_type, period_key, bet_type, races, tickets, hits,
                       stake_yen, payout_yen, profit_yen, hit_rate, roi
                FROM performance_summaries
                ORDER BY period_type, period_key, bet_type
                """
            )
        ],
        "features": [
            {
                "race_id": row["race_id"],
                "horse_id": row["horse_id"],
                "sire_fit_score": row["sire_fit_score"],
                "time_index": row["time_index"],
                "closing_index": row["closing_index"],
                "pace_index": row["pace_index"],
            }
            for row in connection.execute(
                """
                SELECT race_id, horse_id, sire_fit_score, time_index,
                       closing_index, pace_index
                FROM runner_features
                ORDER BY race_id, horse_id
                """
            )
        ],
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_pipeline(db_path: Path, sire_data: Path, public_output: Path) -> int:
    started_at = dt.datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST")
    connection = connect(db_path)
    try:
        init_schema(connection)
        run_id = connection.execute(
            "INSERT INTO pipeline_runs(started_at, status) VALUES (?, ?)",
            (started_at, "running"),
        ).lastrowid
        try:
            sires = load_sire_csv(sire_data)
            import_sires(connection, sires, started_at)
            feature_count = refresh_runner_features(connection, started_at)
            summary_count = refresh_performance_summaries(connection, started_at)
            export_public_features(connection, public_output, started_at)
            connection.execute(
                """
                UPDATE pipeline_runs
                SET finished_at = ?, status = ?, message = ?
                WHERE run_id = ?
                """,
                (started_at, "ok", f"sires={len(sires)} features={feature_count} summaries={summary_count}", run_id),
            )
            connection.commit()
            print(f"Imported {len(sires)} sires, wrote {feature_count} runner features and {summary_count} summaries.")
            return 0
        except Exception as exc:
            connection.execute(
                """
                UPDATE pipeline_runs
                SET finished_at = ?, status = ?, message = ?
                WHERE run_id = ?
                """,
                (started_at, "error", str(exc), run_id),
            )
            connection.commit()
            raise
    finally:
        connection.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build TOKYO12R JRA feature data on OCI.")
    parser.add_argument("--db", type=Path, default=Path("var/jra_features.sqlite3"))
    parser.add_argument("--sire-data", type=Path, default=Path("data/Sire_data.csv"))
    parser.add_argument("--public-output", type=Path, default=Path("site-dist/features-jra.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return run_pipeline(args.db, args.sire_data, args.public_output)


if __name__ == "__main__":
    raise SystemExit(main())
