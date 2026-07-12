#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


DEFAULT_HOST = "161.34.66.248"
DEFAULT_REMOTE_USER = "ubuntu"
DEFAULT_REMOTE_DIR = "/opt/tokyo12r"
DEFAULT_SERVICE = "tokyo12r-feature-update.service"
DEFAULT_VERIFY_URL = "https://tokyo12r.byzin.win/"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_key_path() -> Path:
    return repo_root() / "xtra" / "WebARENA" / "webarena_indigo_id_ed25519"


def run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(shlex.quote(arg) for arg in args), flush=True)
    return subprocess.run(args, text=True, check=check)


def windows_account_name() -> str:
    domain = os.environ.get("USERDOMAIN")
    username = os.environ.get("USERNAME")
    if domain and username:
        return f"{domain}\\{username}"
    if username:
        return username
    return os.getlogin()


def prepare_temp_key(source_key: Path) -> tuple[Path, Path]:
    if not source_key.exists():
        raise FileNotFoundError(f"SSH key not found: {source_key}")

    temp_dir = Path(tempfile.mkdtemp(prefix="tokyo12r-deploy-"))
    temp_key = temp_dir / source_key.name
    shutil.copy2(source_key, temp_key)

    if os.name == "nt":
        account = windows_account_name()
        run(["icacls", str(temp_key), "/inheritance:r", "/grant:r", f"{account}:F"])
    else:
        temp_key.chmod(0o600)

    return temp_dir, temp_key


def ssh_command(args: argparse.Namespace, temp_key: Path) -> list[str]:
    return [
        args.ssh_path,
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={args.connect_timeout}",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "IdentitiesOnly=yes",
        "-i",
        str(temp_key),
        f"{args.remote_user}@{args.host}",
    ]


def remote_script(args: argparse.Namespace) -> str:
    remote_dir = shlex.quote(args.remote_dir)
    service = shlex.quote(args.service)
    lines = [
        "set -eu",
        f"echo '[tokyo12r] remote repository: {remote_dir}'",
        f"sudo -u tokyo12r git -C {remote_dir} rev-parse --short HEAD",
        f"sudo -u tokyo12r git -C {remote_dir} status --short",
    ]
    if not args.skip_pull:
        lines.append(f"sudo -u tokyo12r git -C {remote_dir} pull --ff-only origin main")
    lines.extend(
        [
            "start_status=0",
            f"sudo systemctl start {service} || start_status=$?",
            "while true; do",
            f"  state=$(systemctl show -p ActiveState --value {service})",
            "  if [ \"$state\" != active ] && [ \"$state\" != activating ]; then break; fi",
            "  sleep 2",
            "done",
            f"systemctl show -p ActiveState -p Result -p ExecMainStatus {service}",
            f"journalctl -u {service} -n {args.journal_lines} --no-pager",
            "test \"$start_status\" = 0",
            f"test \"$(systemctl show -p Result --value {service})\" = success",
            f"test \"$(systemctl show -p ExecMainStatus --value {service})\" = 0",
            f"sudo -u tokyo12r git -C {remote_dir} rev-parse --short HEAD",
        ]
    )
    return "\n".join(lines)


def run_remote_deploy(args: argparse.Namespace, temp_key: Path) -> None:
    script = remote_script(args)
    command = ssh_command(args, temp_key) + ["bash", "-lc", shlex.quote(script)]
    run(command)


def verify_public_page(url: str) -> None:
    separator = "&" if "?" in url else "?"
    verify_url = f"{url}{separator}v={int(time.time())}"
    print(f"+ verify {verify_url}", flush=True)
    try:
        with urlopen(verify_url, timeout=30) as response:
            html = response.read().decode("utf-8", errors="replace")
    except URLError as exc:
        raise RuntimeError(f"public page verification failed: {exc}") from exc

    match = re.search(r"更新\s+([0-9:-]+\s+[0-9:]+\s+JST)", html)
    if match:
        print(f"[tokyo12r] public page updated: {match.group(1)}", flush=True)
    else:
        print("[tokyo12r] public page fetched, but update badge was not found.", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the TOKYO12R manual deploy on the WebARENA VPS."
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--remote-user", default=DEFAULT_REMOTE_USER)
    parser.add_argument("--remote-dir", default=DEFAULT_REMOTE_DIR)
    parser.add_argument("--service", default=DEFAULT_SERVICE)
    parser.add_argument("--key", type=Path, default=default_key_path())
    parser.add_argument("--ssh-path", default="ssh")
    parser.add_argument("--connect-timeout", type=int, default=15)
    parser.add_argument("--journal-lines", type=int, default=60)
    parser.add_argument("--skip-pull", action="store_true")
    parser.add_argument("--no-verify", action="store_true")
    parser.add_argument("--verify-url", default=DEFAULT_VERIFY_URL)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    temp_dir: Path | None = None
    try:
        temp_dir, temp_key = prepare_temp_key(args.key)
        run_remote_deploy(args, temp_key)
        if not args.no_verify:
            verify_public_page(args.verify_url)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        if temp_dir is not None:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
