#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import math
import re
import shutil
import time
from dataclasses import dataclass, field
from itertools import combinations, product
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

BASE_URL = "https://www.jra.go.jp"
ACCESS_D_URL = f"{BASE_URL}/JRADB/accessD.html"
JST = ZoneInfo("Asia/Tokyo")
SITE_TITLE = "TOKYO12R by ZIN"
USER_AGENT = "TOKYO12R-by-ZIN/0.1 (+official-source-check)"
BANNER_ASSET_NAME = "tokyo12r-paddock-banner.jpg"
MARKS = ["◎", "○", "▲", "△", "☆"]


@dataclass
class InternalHorse:
    number: str
    name: str
    sex_age: str = ""
    jockey: str = ""
    record: str = ""
    prize_yen: int = 0
    past_texts: list[str] = field(default_factory=list)
    score: float = 0.0


@dataclass
class PublicPick:
    mark: str
    name: str
    score: float
    note: str


@dataclass
class PublicRace:
    venue: str
    race_no: int
    start_time: str
    title: str
    course: str
    official_url: str
    picks: list[PublicPick] = field(default_factory=list)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def jra_post(cname: str) -> str:
    body = f"cname={cname}".encode("ascii")
    last_error: Exception | None = None
    for attempt in range(5):
        request = Request(
            ACCESS_D_URL,
            data=body,
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": f"{BASE_URL}/keiba/",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read()
            return raw.decode("shift_jis", errors="replace")
        except HTTPError as exc:
            last_error = exc
            if exc.code not in {429, 500, 502, 503, 504}:
                raise
        except URLError as exc:
            last_error = exc
        time.sleep(1.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


def extract_cname(href: str) -> str:
    if not href:
        return ""
    parsed = urlparse(urljoin(BASE_URL, href))
    return parse_qs(parsed.query).get("CNAME", [""])[0]


def fetch_meetings(target_date: dt.date) -> list[tuple[str, str]]:
    date_key = target_date.strftime("%Y%m%d")
    soup = BeautifulSoup(jra_post("pw01dli00/F3"), "html.parser")
    meetings: list[tuple[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", onclick=True):
        onclick = anchor.get("onclick", "")
        match = re.search(r"doAction\('/JRADB/accessD\.html',\s*'([^']+)'\)", onclick)
        if not match:
            continue
        cname = match.group(1)
        if not cname.startswith("pw01drl") or date_key not in cname or cname in seen:
            continue
        text = normalize_text(anchor.get_text(" ", strip=True)).replace("馬番確定", "").strip()
        if text:
            meetings.append((text, cname))
            seen.add(cname)
    return meetings


def parse_race_list(venue: str, cname: str) -> list[PublicRace]:
    soup = BeautifulSoup(jra_post(cname), "html.parser")
    races: list[PublicRace] = []
    for row in soup.select("table tr"):
        link = row.select_one("td.syutsuba a[href*='CNAME='], th.race_num a[href*='CNAME=']")
        if not link:
            continue
        detail_cname = extract_cname(link.get("href", ""))
        if not detail_cname.startswith("pw01dde"):
            continue
        race_no = len(races) + 1
        img = row.select_one("th.race_num img[alt]")
        if img:
            no_match = re.search(r"(\d+)", img.get("alt", ""))
            if no_match:
                race_no = int(no_match.group(1))
        start_time = normalize_text(row.select_one("td.time").get_text(" ", strip=True) if row.select_one("td.time") else "")
        title = normalize_text(row.select_one("td.race_name").get_text(" ", strip=True) if row.select_one("td.race_name") else "")
        course = normalize_text(row.select_one("td.dist").get_text(" ", strip=True) if row.select_one("td.dist") else "")
        races.append(
            PublicRace(
                venue=venue,
                race_no=race_no,
                start_time=start_time,
                title=title or f"{race_no}R",
                course=course,
                official_url=f"{ACCESS_D_URL}?CNAME={detail_cname}",
            )
        )
    return races


def fetch_detail_html(official_url: str) -> str:
    cname = extract_cname(official_url)
    if not cname:
        return ""
    return jra_post(cname)


def yen_value(text: str) -> int:
    cleaned = text.replace(",", "")
    if "億" in cleaned:
        match = re.search(r"([\d.]+)億", cleaned)
        return int(float(match.group(1)) * 100_000_000) if match else 0
    match = re.search(r"([\d.]+)万", cleaned)
    return int(float(match.group(1)) * 10_000) if match else 0


def parse_horses(detail_html: str) -> list[InternalHorse]:
    soup = BeautifulSoup(detail_html, "html.parser")
    table = soup.find("table", class_="basic") or soup.find("table")
    if table is None:
        return []
    horses: list[InternalHorse] = []
    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) < 8:
            continue
        number = normalize_text(cells[1].get_text(" ", strip=True))
        if not number.isdigit():
            continue
        horse_cell = cells[2]
        name_node = horse_cell.select_one(".name a") or horse_cell.select_one("a")
        name = normalize_text(name_node.get_text(" ", strip=True) if name_node else "")
        if not name:
            continue
        win_node = horse_cell.select_one(".cell.win")
        prize_text = win_node.get("title") if win_node and win_node.get("title") else (win_node.get_text(" ", strip=True) if win_node else "")
        result_node = horse_cell.select_one(".cell.result")
        jockey_text = normalize_text(cells[3].get_text(" ", strip=True))
        sex_age = jockey_text.split("kg", 1)[0].strip() if "kg" in jockey_text else jockey_text
        jockey = jockey_text.split("kg", 1)[1].strip() if "kg" in jockey_text else ""
        horses.append(
            InternalHorse(
                number=number,
                name=name,
                sex_age=sex_age,
                jockey=jockey,
                record=normalize_text(result_node.get_text(" ", strip=True) if result_node else ""),
                prize_yen=yen_value(prize_text),
                past_texts=[normalize_text(cell.get_text(" ", strip=True)) for cell in cells[4:8]],
            )
        )
    return horses


def score_horse(horse: InternalHorse) -> float:
    score = math.log10(max(horse.prize_yen, 1)) * 2.1 if horse.prize_yen else 0.0
    record_numbers = [int(value) for value in re.findall(r"\d+", horse.record)]
    if len(record_numbers) >= 4:
        wins, seconds, thirds, starts = record_numbers[:4]
        score += wins * 3.4 + seconds * 2.0 + thirds * 1.2 - starts * 0.16
    weights = [1.0, 0.72, 0.52, 0.36]
    for weight, text in zip(weights, horse.past_texts):
        place_match = re.search(r"(\d+)\s*着", text)
        field_match = re.search(r"(\d+)\s*頭", text)
        pop_match = re.search(r"(\d+)\s*番人気", text)
        diff_match = re.search(r"\(([-+]?\d+(?:\.\d+)?)\)", text)
        if place_match and field_match:
            place = int(place_match.group(1))
            field = max(int(field_match.group(1)), 1)
            score += max(0.0, (field + 1 - place) / field) * 8.0 * weight
            if place <= 3:
                score += (4 - place) * 1.4 * weight
        if pop_match:
            pop = int(pop_match.group(1))
            score += max(0.0, 18 - pop) * 0.12 * weight
        if diff_match:
            margin = float(diff_match.group(1))
            if margin >= 0:
                score += max(0.0, 2.0 - margin) * 0.75 * weight
    score += (19 - int(horse.number)) * 0.015
    return round(score, 3)


def make_picks(horses: list[InternalHorse]) -> list[PublicPick]:
    for horse in horses:
        horse.score = score_horse(horse)
    ranked = sorted(horses, key=lambda item: (-item.score, int(item.number), item.name))[:5]
    picks: list[PublicPick] = []
    for mark, horse in zip(MARKS, ranked):
        note = "近走・実績指数"
        if horse.record:
            note = f"近走・実績指数 / {horse.record}"
        picks.append(PublicPick(mark=mark, name=horse.name, score=horse.score, note=note))
    return picks


def fetch_official_races(target_date: dt.date, delay_seconds: float = 0.45) -> list[PublicRace]:
    meetings = fetch_meetings(target_date)
    races: list[PublicRace] = []
    for venue, meeting_cname in meetings:
        time.sleep(delay_seconds)
        venue_races = parse_race_list(venue, meeting_cname)
        for race in venue_races:
            time.sleep(delay_seconds)
            horses = parse_horses(fetch_detail_html(race.official_url))
            race.picks = make_picks(horses)
        races.extend(venue_races)
    return races


def fetch_next_available_races(start_date: dt.date, delay_seconds: float = 0.45, days: int = 4) -> tuple[dt.date, list[PublicRace]]:
    last_races: list[PublicRace] = []
    for offset in range(days):
        candidate = start_date + dt.timedelta(days=offset)
        races = fetch_official_races(candidate, delay_seconds)
        if races:
            return candidate, races
        last_races = races
    return start_date, last_races


def pick_lookup(picks: list[PublicPick]) -> dict[str, PublicPick]:
    return {pick.mark: pick for pick in picks}


def format_formula(marks: list[str], lookup: dict[str, PublicPick]) -> str:
    return " / ".join(f"{mark} {lookup[mark].name}" for mark in marks if mark in lookup)


def bet_sections(picks: list[PublicPick]) -> list[dict[str, object]]:
    lookup = pick_lookup(picks)
    if len(lookup) < 5:
        return []
    umaren = []
    for left in ["◎", "○"]:
        for right in ["○", "▲", "△", "☆"]:
            if left != right:
                pair = tuple(sorted((left, right), key=MARKS.index))
                if pair not in umaren:
                    umaren.append(pair)
    trio_box = list(combinations(MARKS, 3))
    trifecta = [
        combo
        for combo in product(["◎", "○"], ["◎", "○", "▲"], MARKS)
        if len(set(combo)) == 3
    ]
    exacta = [("☆", mark) for mark in ["◎", "○", "▲", "△"]]
    return [
        {"label": "馬連フォーメーション", "formula": "◎○ - ○▲△☆", "count": len(umaren), "tickets": umaren},
        {"label": "3連複BOX", "formula": "◎○▲△☆", "count": len(trio_box), "tickets": trio_box},
        {"label": "3連単フォーメーション", "formula": "◎○ - ◎○▲ - ◎○▲△☆", "count": len(trifecta), "tickets": trifecta},
        {"label": "穴狙い馬単", "formula": "☆ - ◎○▲△", "count": len(exacta), "tickets": exacta},
    ]


def public_payload(date: dt.date, generated_at: str, races: list[PublicRace]) -> dict[str, object]:
    return {
        "date": date.isoformat(),
        "generated_at": generated_at,
        "source": "JRA official race card HTML",
        "races": [
            {
                "venue": race.venue,
                "race_no": race.race_no,
                "start_time": race.start_time,
                "title": race.title,
                "course": race.course,
                "picks": [{"mark": pick.mark, "name": pick.name} for pick in race.picks],
                "bets": bet_sections(race.picks),
            }
            for race in races
        ],
    }


def load_public_payload(input_path: Path | None, target_date: dt.date) -> tuple[list[PublicRace], str]:
    if input_path is None:
        return [], ""
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    races: list[PublicRace] = []
    for item in payload.get("races", []):
        picks = [PublicPick(mark=str(pick.get("mark", "")), name=str(pick.get("name", "")), score=0.0, note="") for pick in item.get("picks", [])]
        races.append(
            PublicRace(
                venue=str(item.get("venue", "")),
                race_no=int(item.get("race_no", 0)),
                start_time=str(item.get("start_time", "")),
                title=str(item.get("title", "")),
                course=str(item.get("course", "")),
                official_url=str(item.get("official_url", "")),
                picks=picks,
            )
        )
    return races, str(payload.get("generated_at", ""))


def favicon_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="14" fill="#004b2b"/>
  <path d="M16 44c8-15 19-24 34-29" fill="none" stroke="#c8a342" stroke-width="7" stroke-linecap="round"/>
  <path d="M14 33c13 2 25-2 37-12" fill="none" stroke="#ffffff" stroke-width="5" stroke-linecap="round"/>
  <circle cx="20" cy="43" r="5" fill="#16a05d"/>
</svg>
"""


def render_picks(race: PublicRace) -> str:
    if not race.picks:
        return '<div class="picks muted">予想は準備中です。</div>'
    items = []
    for pick in race.picks:
        items.append(
            f"""
            <li>
              <span class="mark">{html.escape(pick.mark)}</span>
              <b>{html.escape(pick.name)}</b>
            </li>
            """
        )
    return f'<ol class="picks">{"".join(items)}</ol>'


def render_bets(race: PublicRace) -> str:
    sections = bet_sections(race.picks)
    if not sections:
        return ""
    rows = []
    for section in sections:
        rows.append(
            f"""
            <li>
              <strong>{html.escape(str(section["label"]))}</strong>
              <span>{html.escape(str(section["formula"]))}</span>
              <em>{int(section["count"])}点</em>
            </li>
            """
        )
    return f'<ul class="bets">{"".join(rows)}</ul>'


def render_index(date_label: str, date_key: str, races: list[PublicRace], generated_at: str) -> str:
    venues = list(dict.fromkeys(race.venue for race in races if race.venue))
    if not races:
        body = '<section class="empty">開催情報はまだ取得できていません。</section>'
    else:
        sections = []
        for venue in venues:
            cards = []
            for race in sorted([item for item in races if item.venue == venue], key=lambda item: item.race_no):
                cards.append(
                    f"""
                    <article class="race-card">
                      <div class="race-head">
                        <span class="race-no">{race.race_no}R</span>
                        <div>
                          <h3>{html.escape(race.title)}</h3>
                          <p>{html.escape(race.course)}</p>
                        </div>
                        <time>{html.escape(race.start_time)}</time>
                      </div>
                      {render_picks(race)}
                      {render_bets(race)}
                    </article>
                    """
                )
            sections.append(
                f"""
                <section class="venue">
                  <header><h2>{html.escape(venue)}</h2><span>{len(cards)} races</span></header>
                  <div class="race-list">{"".join(cards)}</div>
                </section>
                """
            )
        body = "".join(sections)
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{SITE_TITLE}</title>
  <meta name="description" content="中央競馬の予想印と買い目を公開するTOKYO12R by ZINです。">
  <link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="/assets/site.css">
</head>
<body>
  <header class="topbar">
    <a class="brand" href="/">{SITE_TITLE}</a>
    <nav><a href="https://byzin.win/">by ZIN</a><a href="https://nar.byzin.win/">NAR</a></nav>
  </header>
  <main>
    <section class="hero-banner" aria-label="TOKYO12R paddock banner">
      <img src="/assets/{BANNER_ASSET_NAME}" alt="">
      <div class="hero-shade"></div>
      <div class="hero-copy">
        <span>JRA Forecast</span>
        <strong>{SITE_TITLE}</strong>
      </div>
    </section>
    <section class="summary">
      <div>
        <span class="date">{html.escape(date_label)}</span>
        <p>毎開催ごとに予想情報を掲載しています。</p>
      </div>
      <div class="badge">更新 {html.escape(generated_at)}</div>
    </section>
    {body}
  </main>
  <footer>
    馬券は20歳になってから。
  </footer>
</body>
</html>
"""


def write_assets(output: Path) -> None:
    assets = output / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    banner_source = Path(__file__).resolve().parent.parent / "assets" / BANNER_ASSET_NAME
    if banner_source.exists():
        shutil.copy2(banner_source, assets / BANNER_ASSET_NAME)
    (assets / "favicon.svg").write_text(favicon_svg(), encoding="utf-8")
    (assets / "site.css").write_text(
        """
:root { --ink:#122019; --muted:#617167; --line:#dbe6df; --panel:#fff; --bg:#f4f8f3; --green:#007a3d; --deep:#004b2b; --gold:#c8a342; --accent:#16a05d; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; letter-spacing:0; }
a { color:inherit; }
.topbar { position:sticky; top:0; z-index:2; display:flex; justify-content:space-between; align-items:center; gap:16px; padding:14px 20px; background:var(--deep); color:white; border-bottom:3px solid var(--gold); }
.brand { font-weight:800; text-decoration:none; font-size:21px; }
nav { display:flex; gap:8px; }
nav a { text-decoration:none; border:1px solid rgba(255,255,255,.65); border-radius:6px; padding:7px 10px; font-size:13px; }
main { width:min(1180px, calc(100vw - 24px)); margin:16px auto 40px; }
.hero-banner { position:relative; min-height:210px; max-height:300px; aspect-ratio:3 / 1; overflow:hidden; border-radius:8px; border:1px solid var(--line); background:#0d3f24; }
.hero-banner img { position:absolute; inset:0; width:100%; height:100%; object-fit:cover; object-position:center 48%; }
.hero-shade { position:absolute; inset:0; background:linear-gradient(90deg, rgba(0,24,12,.76), rgba(0,24,12,.16) 58%, rgba(0,24,12,.42)); }
.hero-copy { position:absolute; left:22px; bottom:20px; display:grid; gap:6px; color:white; }
.hero-copy span { color:rgba(255,255,255,.72); font-size:12px; font-weight:800; text-transform:uppercase; }
.hero-copy strong { font-size:clamp(28px, 5vw, 54px); line-height:1; }
.summary { display:flex; justify-content:space-between; align-items:center; gap:16px; padding:16px; background:var(--panel); border:1px solid var(--line); border-radius:8px; }
.summary p { margin:4px 0 0; color:var(--muted); }
.date { font-weight:800; font-size:22px; }
.badge { white-space:nowrap; border-radius:999px; padding:8px 10px; background:#edf8ef; color:var(--deep); font-size:13px; border:1px solid #cce8d5; }
.venue { margin-top:14px; background:var(--panel); border:1px solid var(--line); border-radius:8px; overflow:hidden; }
.venue > header { display:flex; justify-content:space-between; align-items:center; padding:12px 14px; border-bottom:1px solid var(--line); background:#f9fcfa; }
.venue h2 { margin:0; font-size:18px; }
.venue header span { color:var(--muted); font-size:13px; }
.race-list { display:grid; grid-template-columns:repeat(auto-fit, minmax(310px, 1fr)); gap:1px; background:var(--line); }
.race-card { padding:13px; background:white; min-height:246px; }
.race-head { display:grid; grid-template-columns:auto 1fr auto; gap:9px; align-items:start; }
.race-no { display:inline-grid; place-items:center; min-width:38px; height:30px; border-radius:6px; background:var(--green); color:white; font-weight:800; }
.race-head h3 { margin:0; font-size:15px; line-height:1.35; }
.race-head p { margin:4px 0 0; color:var(--muted); font-size:12px; line-height:1.4; }
.race-head time { color:var(--deep); font-weight:800; white-space:nowrap; }
.picks { display:grid; gap:6px; margin:12px 0 0; padding:0; list-style:none; }
.picks li { display:grid; grid-template-columns:30px minmax(0,1fr); gap:7px; align-items:center; padding:7px; border:1px solid #d6eadc; border-radius:7px; background:#f8fcf9; }
.picks b { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.mark { display:grid; place-items:center; width:28px; height:28px; border-radius:50%; background:var(--green); color:white; font-weight:900; }
.bets { display:grid; gap:6px; margin:10px 0 0; padding:0; list-style:none; }
.bets li { display:grid; grid-template-columns:1fr auto; gap:5px 8px; padding:7px; border-radius:7px; background:#fff8e5; border:1px solid #f0deb0; font-size:12px; }
.bets strong { color:#4d3a05; }
.bets span { color:#665526; }
.bets em { grid-row:1 / 3; grid-column:2; align-self:center; color:var(--deep); font-style:normal; font-weight:800; }
.muted, .empty { color:var(--muted); }
.empty { margin-top:14px; padding:28px; background:white; border:1px solid var(--line); border-radius:8px; text-align:center; }
footer { width:min(1180px, calc(100vw - 24px)); margin:0 auto 32px; color:var(--muted); font-size:12px; line-height:1.7; }
@media (max-width:640px) { .topbar,.summary { align-items:flex-start; flex-direction:column; } nav { width:100%; } nav a { flex:1; text-align:center; } .hero-banner { min-height:180px; aspect-ratio:16 / 9; } .hero-copy { left:16px; bottom:16px; } .race-list { grid-template-columns:1fr; } }
""".strip()
        + "\n",
        encoding="utf-8",
    )


def generate(output: Path, target_date: dt.date, races: list[PublicRace], generated_at: str) -> None:
    date_label = target_date.strftime("%Y/%m/%d")
    date_key = target_date.strftime("%Y%m%d")
    if output.exists():
        for child in output.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    output.mkdir(parents=True, exist_ok=True)
    write_assets(output)
    payload = public_payload(target_date, generated_at, races)
    (output / "index.html").write_text(render_index(date_label, date_key, races, generated_at), encoding="utf-8")
    (output / f"public-data{date_key}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
    (output / "sitemap.xml").write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://tokyo12r.byzin.win/</loc>
    <lastmod>{target_date.isoformat()}</lastmod>
  </url>
</urlset>
""",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="site-dist")
    parser.add_argument("--date", default=dt.datetime.now(JST).date().isoformat())
    parser.add_argument("--input", type=Path, help="sanitized public JSON generated earlier")
    parser.add_argument("--fetch-official", action="store_true", help="fetch current JRA official race card HTML")
    parser.add_argument("--delay", type=float, default=0.45, help="seconds between official JRA requests")
    args = parser.parse_args()

    target_date = dt.date.fromisoformat(args.date)
    generated_at = dt.datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST")
    if args.fetch_official:
        target_date, races = fetch_next_available_races(target_date, args.delay)
    else:
        races, loaded_generated_at = load_public_payload(args.input, target_date)
        generated_at = loaded_generated_at or generated_at
    generate(Path(args.output), target_date, races, generated_at)
    print(f"Generated {len(races)} races into {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
