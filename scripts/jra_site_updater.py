#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
SITE_TITLE = "TOKYO12R by ZIN"


@dataclass
class Horse:
    number: str
    name: str


@dataclass
class Prediction:
    mark: str
    number: str
    name: str
    total_index: str = ""
    odds: str = ""


@dataclass
class Race:
    venue: str
    race_no: int
    start_time: str
    title: str
    course: str = ""
    weather: str = ""
    going: str = ""
    runners: str = ""
    official_url: str = ""
    horses: list[Horse] = field(default_factory=list)
    predictions: list[Prediction] = field(default_factory=list)


def clean_str(value: object) -> str:
    return str(value or "").strip()


def parse_races(payload: dict[str, object]) -> list[Race]:
    races: list[Race] = []
    for venue in payload.get("venues", []):
        if not isinstance(venue, dict):
            continue
        venue_name = clean_str(venue.get("name"))
        for race in venue.get("races", []):
            if not isinstance(race, dict):
                continue
            horses = [
                Horse(number=clean_str(horse.get("number")), name=clean_str(horse.get("name")))
                for horse in race.get("horses", [])
                if isinstance(horse, dict)
            ]
            predictions = [
                Prediction(
                    mark=clean_str(pred.get("mark")),
                    number=clean_str(pred.get("number")),
                    name=clean_str(pred.get("name")),
                    total_index=clean_str(pred.get("total_index")),
                    odds=clean_str(pred.get("odds")),
                )
                for pred in race.get("predictions", [])
                if isinstance(pred, dict)
            ]
            races.append(
                Race(
                    venue=venue_name,
                    race_no=int(race.get("race_no") or 0),
                    start_time=clean_str(race.get("start_time")),
                    title=clean_str(race.get("title")),
                    course=clean_str(race.get("course")),
                    weather=clean_str(race.get("weather")),
                    going=clean_str(race.get("going")),
                    runners=clean_str(race.get("runners")),
                    official_url=clean_str(race.get("official_url")),
                    horses=horses,
                    predictions=predictions,
                )
            )
    return races


def load_races(input_path: Path | None) -> list[Race]:
    if input_path is None:
        return []
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return parse_races(payload)
    return []


def render_prediction(race: Race) -> str:
    if not race.predictions:
        return '<div class="prediction muted">予想情報は準備中です。</div>'
    items = []
    for pred in race.predictions[:4]:
        index = f"<em>指数 {html.escape(pred.total_index)}</em>" if pred.total_index else "<em>指数 未確定</em>"
        odds = html.escape(pred.odds or "未確定")
        items.append(
            f"""
            <li>
              <span class="mark">{html.escape(pred.mark)}</span>
              <span class="horse-no">{html.escape(pred.number)}</span>
              <b>{html.escape(pred.name)}</b>
              {index}
              <small>現在オッズ {odds}</small>
            </li>
            """
        )
    return f"""
    <div class="prediction">
      <h3>勝ち馬予想</h3>
      <ol>{''.join(items)}</ol>
    </div>
    """


def render_index(date_label: str, date_key: str, races: list[Race], generated_at: str) -> str:
    venues = sorted({race.venue for race in races if race.venue})
    sections = []
    if not races:
        sections.append('<section class="empty">開催無し</section>')
    for venue in venues:
        venue_races = sorted([race for race in races if race.venue == venue], key=lambda race: race.race_no)
        race_cards = []
        for race in venue_races:
            meta = [
                race.course,
                f"天候 {race.weather}" if race.weather else "",
                f"馬場 {race.going}" if race.going else "",
                race.runners,
            ]
            meta_html = "".join(f"<span>{html.escape(value)}</span>" for value in meta if value)
            horse_html = "".join(
                f"<li><span>{html.escape(horse.number)}</span>{html.escape(horse.name)}</li>"
                for horse in race.horses
            )
            source_link = (
                f'<a class="source-link" href="{html.escape(race.official_url)}">公式出馬表</a>'
                if race.official_url
                else ""
            )
            race_cards.append(
                f"""
                <article class="race-card">
                  <div class="race-head">
                    <span class="race-no">{race.race_no}R</span>
                    <strong>{html.escape(race.title)}</strong>
                    <time>{html.escape(race.start_time)}</time>
                  </div>
                  <div class="race-meta">{meta_html}</div>
                  <ol class="horses">{horse_html}</ol>
                  {source_link}
                  {render_prediction(race)}
                </article>
                """
            )
        sections.append(
            f"""
            <section class="venue">
              <header><h2>{html.escape(venue)}</h2><span>{len(venue_races)} races</span></header>
              <div class="race-list">{''.join(race_cards)}</div>
            </section>
            """
        )
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{SITE_TITLE}</title>
  <link rel="stylesheet" href="/assets/site.css">
</head>
<body>
  <header class="topbar">
    <div><h1>{SITE_TITLE}</h1></div>
    <nav>
      <a href="/">本日</a>
      <a href="/result{html.escape(date_key)}.html">結果</a>
    </nav>
  </header>
  <main>
    <section class="summary">
      <div>
        <span class="date">{html.escape(date_label)}</span>
        <p>JRA公式発表に基づく開催情報と予想情報を表示します。</p>
      </div>
      <div class="badge">更新 {html.escape(generated_at)}</div>
    </section>
    {''.join(sections)}
  </main>
  <footer>
    データ出典: JRA公式発表。馬券は20歳になってから。表示内容は主催者発表と照合してください。
  </footer>
</body>
</html>
"""


def render_results(date_key: str, generated_at: str) -> str:
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{SITE_TITLE} Results</title>
  <link rel="stylesheet" href="/assets/site.css">
</head>
<body>
  <header class="topbar">
    <div><h1>結果 {html.escape(date_key)}</h1></div>
    <nav><a href="/">本日</a></nav>
  </header>
  <main>
    <section class="summary">
      <p>結果情報は準備中です。</p>
      <div class="badge">更新 {html.escape(generated_at)}</div>
    </section>
  </main>
</body>
</html>
"""


def write_assets(output: Path) -> None:
    assets = output / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "site.css").write_text(
        """
:root { --ink:#132018; --muted:#64746b; --line:#dce6df; --panel:#ffffff; --bg:#f3f8f4; --green:#007a3d; --deep:#004b2b; --gold:#c8a342; --accent:#16a05d; }
* { box-sizing: border-box; }
body { margin:0; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:var(--bg); color:var(--ink); letter-spacing:0; }
a { color: inherit; }
.topbar { position:sticky; top:0; z-index:2; display:flex; justify-content:space-between; align-items:center; gap:16px; padding:14px 20px; background:var(--deep); color:white; border-bottom:3px solid var(--gold); }
.topbar h1 { margin:0; font-size:22px; line-height:1.1; }
nav { display:flex; gap:8px; }
nav a, .source-link { text-decoration:none; border:1px solid currentColor; border-radius:6px; padding:7px 10px; font-size:13px; }
main { width:min(1180px, calc(100vw - 24px)); margin:16px auto 40px; }
.summary { display:flex; justify-content:space-between; align-items:center; gap:16px; padding:16px; background:var(--panel); border:1px solid var(--line); border-radius:8px; }
.summary p { margin:4px 0 0; color:var(--muted); }
.date { font-weight:700; font-size:22px; }
.badge { white-space:nowrap; border-radius:999px; padding:8px 10px; background:#edf8ef; color:var(--deep); font-size:13px; border:1px solid #cce8d5; }
.venue { margin-top:14px; background:var(--panel); border:1px solid var(--line); border-radius:8px; overflow:hidden; }
.venue > header { display:flex; justify-content:space-between; align-items:center; padding:12px 14px; border-bottom:1px solid var(--line); background:#f9fcfa; }
.venue h2 { margin:0; font-size:18px; }
.race-list { display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap:1px; background:var(--line); }
.race-card { min-height:172px; padding:13px; background:white; }
.race-head { display:grid; grid-template-columns:auto 1fr auto; gap:8px; align-items:start; }
.race-no { display:inline-grid; place-items:center; min-width:38px; height:28px; border-radius:6px; background:var(--green); color:white; font-weight:700; }
.race-head strong { font-size:15px; line-height:1.35; }
.race-head time { color:var(--deep); font-weight:800; }
.race-meta { display:flex; flex-wrap:wrap; gap:6px; margin:10px 0; color:var(--muted); font-size:12px; }
.race-meta span { border:1px solid var(--line); border-radius:999px; padding:4px 7px; background:#fafdfa; }
.horses { display:grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap:4px 8px; margin:10px 0; padding:0; list-style:none; font-size:13px; }
.horses li { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.horses span { display:inline-grid; place-items:center; width:22px; height:22px; margin-right:5px; border-radius:4px; background:#edf6ef; color:#193d27; font-weight:700; }
.source-link { display:inline-block; color:var(--green); margin-top:4px; }
.prediction { margin-top:10px; padding:10px; border:1px solid #cce8d5; border-radius:8px; background:#f7fcf8; }
.prediction h3 { margin:0 0 8px; font-size:13px; color:var(--deep); }
.prediction ol { display:grid; gap:6px; margin:0; padding:0; list-style:none; }
.prediction li { display:grid; grid-template-columns:28px 24px minmax(0, 1fr) auto; gap:6px; align-items:center; font-size:13px; }
.prediction b { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.prediction em { color:var(--deep); font-style:normal; font-weight:800; }
.prediction small { grid-column:3 / 5; color:var(--muted); line-height:1.3; }
.mark { display:grid; place-items:center; width:26px; height:26px; border-radius:50%; background:var(--green); color:white; font-weight:800; }
.horse-no { display:grid; place-items:center; width:22px; height:22px; border-radius:4px; background:var(--deep); color:white; font-weight:800; }
.muted { color:var(--muted); font-size:13px; }
.empty { margin-top:14px; padding:28px; background:white; border:1px solid var(--line); border-radius:8px; text-align:center; color:var(--muted); }
footer { width:min(1180px, calc(100vw - 24px)); margin:0 auto 32px; color:var(--muted); font-size:12px; line-height:1.7; }
@media (max-width: 640px) { .topbar, .summary { align-items:flex-start; flex-direction:column; } nav { width:100%; } nav a { flex:1; text-align:center; } .race-list { grid-template-columns: 1fr; } }
""".strip()
        + "\n",
        encoding="utf-8",
    )


def generate(output: Path, date: dt.date, input_path: Path | None) -> int:
    now = dt.datetime.now(JST)
    date_label = date.strftime("%Y/%m/%d")
    date_key = date.strftime("%Y%m%d")
    generated_at = now.strftime("%Y-%m-%d %H:%M:%S")
    races = load_races(input_path)

    output.mkdir(parents=True, exist_ok=True)
    write_assets(output)
    (output / "index.html").write_text(render_index(date_label, date_key, races, generated_at), encoding="utf-8")
    (output / f"result{date_key}.html").write_text(render_results(date_key, generated_at), encoding="utf-8")
    (output / f"data{date_key}.json").write_text(
        json.dumps({"generated_at": generated_at, "races": [race.__dict__ for race in races]}, ensure_ascii=False, default=lambda value: value.__dict__, indent=2),
        encoding="utf-8",
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="site-dist")
    parser.add_argument("--date", default=dt.datetime.now(JST).date().isoformat())
    parser.add_argument("--input", type=Path, help="officially fetched JRA race JSON")
    args = parser.parse_args()
    target_date = dt.date.fromisoformat(args.date)
    return generate(Path(args.output), target_date, args.input)


if __name__ == "__main__":
    raise SystemExit(main())
