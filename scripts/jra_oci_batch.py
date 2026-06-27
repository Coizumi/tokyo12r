#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the TOKYO12R OCI-side JRA batch.")
    parser.add_argument("--repo-dir", type=Path, default=Path("/opt/tokyo12r"))
    parser.add_argument("--output", type=Path, default=Path("/opt/tokyo12r/site-dist"))
    parser.add_argument("--db", type=Path, default=Path("/opt/tokyo12r/var/jra_features.sqlite3"))
    parser.add_argument("--sire-data", type=Path, default=Path("/opt/tokyo12r/data/Sire_data.csv"))
    parser.add_argument("--public-output", type=Path, default=Path("/opt/tokyo12r/site-dist/features-jra.json"))
    parser.add_argument("--oci-data", type=Path, default=Path("/opt/tokyo12r/var/oci-data.json"))
    parser.add_argument("--date", default=dt.datetime.now(JST).date().isoformat())
    parser.add_argument("--delay", type=float, default=0.45)
    parser.add_argument("--skip-pull", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_dir = args.repo_dir.resolve()
    output_dir = args.output.resolve()

    if not args.skip_pull and (repo_dir / ".git").exists():
        run_command(["git", "pull", "--ff-only"], repo_dir)

    run_command(
        [
            "python3",
            str(repo_dir / "scripts" / "jra_site_updater.py"),
            "--output",
            str(output_dir),
            "--date",
            args.date,
            "--fetch-official",
            "--delay",
            str(args.delay),
            "--oci-data-output",
            str(args.oci_data),
        ],
        repo_dir,
    )
    public_data = args.oci_data if args.oci_data.exists() else latest_public_data(output_dir)
    print(f"Using OCI data: {public_data}", flush=True)
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
            str(public_data),
        ],
        repo_dir,
    )

    if should_dispatch(os.environ.get("TOKYO12R_DISPATCH_WORKFLOW")):
        token = os.environ.get("GITHUB_TOKEN", "").strip()
        if not token:
            raise RuntimeError("TOKYO12R_DISPATCH_WORKFLOW is enabled but GITHUB_TOKEN is empty.")
        github_dispatch(
            os.environ.get("GITHUB_REPOSITORY", "Coizumi/tokyo12r"),
            os.environ.get("GITHUB_WORKFLOW", "deploy-tokyo12r.yml"),
            token,
            args.date,
        )
    else:
        print("GitHub workflow dispatch is disabled.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
