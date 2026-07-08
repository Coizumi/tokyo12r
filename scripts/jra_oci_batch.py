#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")


def run_command(command: list[str], cwd: Path) -> None:
    printable = " ".join(command)
    print(f"+ {printable}", flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def latest_public_data(output_dir: Path) -> Path:
    candidates = sorted(output_dir.glob("public-data*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(f"No public-data*.json was generated in {output_dir}")
    return candidates[0]


def github_dispatch(repository: str, workflow: str, token: str, date_value: str | None) -> None:
    payload: dict[str, object] = {"ref": "main"}
    if date_value:
        payload["inputs"] = {"date": date_value}
    request = Request(
        f"https://api.github.com/repos/{repository}/actions/workflows/{workflow}/dispatches",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "tokyo12r-oci-batch",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            if response.status not in {204, 201, 200}:
                raise RuntimeError(f"Unexpected GitHub dispatch status: {response.status}")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub workflow dispatch failed: {exc.code} {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"GitHub workflow dispatch failed: {exc}") from exc
    print(f"Dispatched {workflow} for {repository}.", flush=True)


def should_dispatch(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def should_deploy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def should_archive(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def cloudflare_pages_deploy(output_dir: Path, cwd: Path) -> None:
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("CLOUDFLARE_PAGES_DEPLOY is enabled but CLOUDFLARE_API_TOKEN is empty.")
    project_name = os.environ.get("CLOUDFLARE_PAGES_PROJECT_NAME", "tokyo12r").strip() or "tokyo12r"
    branch = os.environ.get("CLOUDFLARE_PAGES_BRANCH", "main").strip() or "main"
    command = [
        "npx",
        "--yes",
        "wrangler@latest",
        "pages",
        "deploy",
        str(output_dir),
        f"--project-name={project_name}",
        f"--branch={branch}",
    ]
    run_command(command, cwd)


def archive_public_data_to_r2(public_data: Path, cwd: Path) -> None:
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    if not token:
        raise RuntimeError("TOKYO12R_R2_ARCHIVE is enabled but CLOUDFLARE_API_TOKEN is empty.")
    if not account_id:
        raise RuntimeError("TOKYO12R_R2_ARCHIVE is enabled but CLOUDFLARE_ACCOUNT_ID is empty.")

    bucket = (
        os.environ.get("TOKYO12R_R2_BUCKET")
        or os.environ.get("R2_BUCKET")
        or os.environ.get("CLOUDFLARE_R2_BUCKET")
        or "byzin-nar-results"
    ).strip()
    filename = public_data.name
    if not filename.startswith("public-data") or not filename.endswith(".json"):
        raise ValueError(f"Unexpected public data filename for R2 archive: {filename}")
    date_key = filename.removeprefix("public-data").removesuffix(".json")
    if len(date_key) != 8 or not date_key.isdigit():
        raise ValueError(f"Unexpected public data date key for R2 archive: {filename}")

    year, month, day = date_key[:4], date_key[4:6], date_key[6:8]
    daily_key = f"{bucket}/jra/daily/{year}/{month}/{day}/public-data{date_key}.json"
    latest_key = f"{bucket}/jra/latest/public-data.json"
    for object_path in (daily_key, latest_key):
        command = [
            "npx",
            "--yes",
            "wrangler@latest",
            "r2",
            "object",
            "put",
            object_path,
            "--remote",
            "--file",
            str(public_data),
            "--content-type",
            "application/json; charset=utf-8",
        ]
        for attempt in range(1, 4):
            try:
                run_command(command, cwd)
                break
            except subprocess.CalledProcessError:
                if attempt >= 3:
                    raise
                print(f"R2 archive upload failed for {object_path}; retrying ({attempt}/3).", flush=True)
                time.sleep(5)


def default_fetch_days(target_date: dt.date) -> int:
    # Explicit Friday runs keep the legacy "next available racing day" behavior.
    # Normal daytime update slots only inspect the target date.
    return 4 if target_date.weekday() == 4 else 1


def is_next_day_prep_slot(now: dt.datetime) -> bool:
    return now.weekday() in {4, 5} and now.time() >= dt.time(22, 0)


def default_target_date(now: dt.datetime) -> dt.date:
    if is_next_day_prep_slot(now):
        return now.date() + dt.timedelta(days=1)
    return now.date()


def default_fetch_days_for_run(target_date: dt.date, next_day_prep_slot: bool) -> int:
    if next_day_prep_slot:
        return 4
    return default_fetch_days(target_date)


def no_race_marker(repo_dir: Path, target_date: dt.date) -> Path:
    return repo_dir / "var" / f"no-race-{target_date.isoformat()}.marker"


def should_use_no_race_marker(target_date: dt.date) -> bool:
    return target_date.weekday() in {0, 1}


def public_race_count(public_data: Path) -> int:
    if not public_data.exists():
        return 0
    payload = json.loads(public_data.read_text(encoding="utf-8"))
    return len(payload.get("races", []))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the TOKYO12R OCI-side JRA batch.")
    parser.add_argument("--repo-dir", type=Path, default=Path("/opt/tokyo12r"))
    parser.add_argument("--output", type=Path, default=Path("/opt/tokyo12r/site-dist"))
    parser.add_argument("--db", type=Path, default=Path("/opt/tokyo12r/var/jra_features.sqlite3"))
    parser.add_argument("--sire-data", type=Path, default=Path("/opt/tokyo12r/data/Sire_data.csv"))
    parser.add_argument("--public-output", type=Path, default=Path("/opt/tokyo12r/site-dist/features-jra.json"))
    parser.add_argument("--oci-data", type=Path, default=Path("/opt/tokyo12r/var/oci-data.json"))
    parser.add_argument("--date", help="target date in YYYY-MM-DD. Defaults to current JST date, except Fri/Sat night prep slots use the next day.")
    parser.add_argument("--delay", type=float, default=0.45)
    parser.add_argument("--fetch-days", type=int, help="number of days to scan for official race cards")
    parser.add_argument("--ignore-no-race-marker", action="store_true")
    parser.add_argument("--skip-pull", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_dir = args.repo_dir.resolve()
    output_dir = args.output.resolve()
    now = dt.datetime.now(JST)
    next_day_prep_slot = args.date is None and is_next_day_prep_slot(now)
    target_date = dt.date.fromisoformat(args.date) if args.date else default_target_date(now)
    date_value = target_date.isoformat()
    marker = no_race_marker(repo_dir, target_date)

    if should_use_no_race_marker(target_date) and marker.exists() and not args.ignore_no_race_marker:
        print(f"No-race marker exists for {target_date}; skipping update.", flush=True)
        return 0

    if not args.skip_pull and (repo_dir / ".git").exists():
        run_command(["git", "pull", "--ff-only"], repo_dir)

    fetch_days = args.fetch_days if args.fetch_days is not None else default_fetch_days_for_run(target_date, next_day_prep_slot)
    run_command(
        [
            "python3",
            str(repo_dir / "scripts" / "jra_site_updater.py"),
            "--output",
            str(output_dir),
            "--date",
            date_value,
            "--fetch-official",
            "--fetch-days",
            str(fetch_days),
            "--delay",
            str(args.delay),
            "--oci-data-output",
            str(args.oci_data),
        ],
        repo_dir,
    )
    generated_public_data = latest_public_data(output_dir)
    public_data_for_features = args.oci_data if args.oci_data.exists() else generated_public_data
    race_count = public_race_count(public_data_for_features)
    if should_use_no_race_marker(target_date) and race_count == 0:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(f"{dt.datetime.now(JST).isoformat()} no races for {target_date}\n", encoding="utf-8")
        print(f"No races found for {target_date}; wrote {marker} and stopped before feature export/dispatch.", flush=True)
        return 0
    if marker.exists() and race_count > 0:
        marker.unlink()
    print(f"Using OCI data: {public_data_for_features}", flush=True)
    run_command(
        [
            "python3",
            str(repo_dir / "scripts" / "jra_feature_pipeline.py"),
            "--db",
            str(args.db),
            "--sire-data",
            str(args.sire_data),
            "--public-output",
            str(args.public_output),
            "--public-data",
            str(public_data_for_features),
        ],
        repo_dir,
    )

    if should_archive(os.environ.get("TOKYO12R_R2_ARCHIVE")):
        try:
            archive_public_data_to_r2(generated_public_data, repo_dir)
        except Exception as exc:
            print(f"R2 public data archive failed; continuing deploy: {exc}", flush=True)
    else:
        print("R2 public data archive is disabled.", flush=True)

    if should_deploy(os.environ.get("CLOUDFLARE_PAGES_DEPLOY")):
        cloudflare_pages_deploy(output_dir, repo_dir)
    else:
        print("Cloudflare Pages direct deploy is disabled.", flush=True)

    if should_dispatch(os.environ.get("TOKYO12R_DISPATCH_WORKFLOW")):
        token = os.environ.get("GITHUB_TOKEN", "").strip()
        if not token:
            raise RuntimeError("TOKYO12R_DISPATCH_WORKFLOW is enabled but GITHUB_TOKEN is empty.")
        github_dispatch(
            os.environ.get("GITHUB_REPOSITORY", "Coizumi/tokyo12r"),
            os.environ.get("GITHUB_WORKFLOW", "deploy-tokyo12r.yml"),
            token,
            date_value,
        )
    else:
        print("GitHub workflow dispatch is disabled.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
