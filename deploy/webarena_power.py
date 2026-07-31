#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_BASE = "https://api.customer.jp"
DEFAULT_INSTANCE_NAME = "tokyo12r-batch-01"


class WebArenaApiError(RuntimeError):
    def __init__(self, status_code: int, detail: str):
        super().__init__(f"WebARENA API HTTP {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail
        try:
            payload = json.loads(detail)
        except json.JSONDecodeError:
            payload = {}
        self.payload = payload if isinstance(payload, dict) else {}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_key_path() -> Path:
    return repo_root() / "xtra" / "WebARENA" / "webarena_apikey.txt"


def default_secret_path() -> Path:
    return repo_root() / "xtra" / "WebARENA" / "webarena_apisecret.txt"


def read_secret_file(path: Path) -> str:
    value = path.read_text(encoding="utf-8").strip()
    if ":" in value:
        _, possible_secret = value.split(":", 1)
        value = possible_secret.strip()
    if not value:
        raise ValueError(f"secret file is empty: {path}")
    return value


def api_request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    body: dict[str, object] | None = None,
    timeout: int = 30,
) -> object:
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    request = Request(f"{API_BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise WebArenaApiError(exc.code, detail) from exc
    except URLError as exc:
        raise RuntimeError(f"WebARENA API request failed: {exc}") from exc
    return json.loads(text) if text.strip() else {}


def access_token(client_id: str, client_secret: str) -> str:
    response = api_request(
        "POST",
        "/oauth/v1/accesstokens",
        body={
            "grantType": "client_credentials",
            "clientId": client_id,
            "clientSecret": client_secret,
            "code": "",
        },
    )
    if not isinstance(response, dict):
        raise RuntimeError("unexpected access token response")
    token = str(response.get("accessToken") or "")
    if not token:
        raise RuntimeError("access token was not returned")
    return token


def instance_list(token: str) -> list[dict[str, object]]:
    response = api_request("GET", "/webarenaIndigo/v1/vm/getinstancelist", token=token)
    if isinstance(response, list):
        return [item for item in response if isinstance(item, dict)]
    if isinstance(response, dict):
        for key in ("vms", "instances", "data"):
            value = response.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise RuntimeError("unexpected instance list response")


def instance_name(instance: dict[str, object]) -> str:
    return str(instance.get("instance_name") or instance.get("instanceName") or "")


def instance_status(instance: dict[str, object]) -> str:
    return str(instance.get("instanceStatus") or instance.get("status") or "")


def instance_id(instance: dict[str, object]) -> str:
    value = instance.get("id") or instance.get("instanceId")
    if value is None:
        raise RuntimeError(f"instance id was not found for {instance_name(instance) or '<unknown>'}")
    return str(value)


def select_instance(instances: list[dict[str, object]], name: str | None, instance_id_value: str | None) -> dict[str, object]:
    if instance_id_value:
        matches = [item for item in instances if instance_id(item) == str(instance_id_value)]
    elif name:
        matches = [item for item in instances if instance_name(item) == name]
    else:
        matches = instances
    if not matches:
        selector = f"id={instance_id_value}" if instance_id_value else f"name={name}"
        raise RuntimeError(f"WebARENA instance not found: {selector}")
    if len(matches) > 1:
        names = ", ".join(f"{instance_id(item)}:{instance_name(item)}" for item in matches)
        raise RuntimeError(f"multiple WebARENA instances matched; specify --instance-id. matches={names}")
    return matches[0]


def update_status(token: str, target_id: str, status: str) -> dict[str, object]:
    try:
        response = api_request(
            "POST",
            "/webarenaIndigo/v1/vm/instance/statusupdate",
            token=token,
            body={"instanceId": target_id, "status": status},
        )
    except WebArenaApiError as exc:
        message = str(exc.payload.get("errorMessage") or "").lower()
        if status == "start" and "already running" in message:
            return {"success": True, "message": "Instance is already running.", "instanceStatus": "running"}
        if status in {"stop", "forcestop"} and ("already stopped" in message or "already shutoff" in message):
            return {"success": True, "message": "Instance is already stopped.", "instanceStatus": "shutoff"}
        raise
    if not isinstance(response, dict):
        raise RuntimeError("unexpected status update response")
    return response


def tcp_port_open(host: str, port: int, timeout: float = 5.0) -> bool:
    if not host:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def print_instance(instance: dict[str, object]) -> None:
    print(
        json.dumps(
            {
                "id": instance_id(instance),
                "name": instance_name(instance),
                "status": instance_status(instance),
                "ip": instance.get("ip"),
                "service_id": instance.get("service_id"),
                "plan": instance.get("plan"),
            },
            ensure_ascii=False,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Control the WebARENA Indigo TOKYO12R instance power state.")
    parser.add_argument("action", choices=["list", "status", "start", "stop", "forcestop", "reset"])
    parser.add_argument("--api-key-file", type=Path, default=default_key_path())
    parser.add_argument("--api-secret-file", type=Path, default=default_secret_path())
    parser.add_argument("--instance-name", default=DEFAULT_INSTANCE_NAME)
    parser.add_argument("--instance-id", default="")
    parser.add_argument("--wait", action="store_true", help="poll instance status after start/stop")
    parser.add_argument("--ssh-port", type=int, default=22)
    parser.add_argument("--poll-seconds", type=int, default=15)
    parser.add_argument("--max-wait-seconds", type=int, default=600)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client_id = read_secret_file(args.api_key_file)
    client_secret = read_secret_file(args.api_secret_file)
    token = access_token(client_id, client_secret)

    instances = instance_list(token)
    if args.action == "list":
        for item in instances:
            print_instance(item)
        return 0

    target = select_instance(instances, args.instance_name, args.instance_id or None)
    target_id = instance_id(target)
    print_instance(target)
    if args.action == "status":
        return 0

    response = update_status(token, target_id, args.action)
    print(json.dumps({"action": args.action, "response": response}, ensure_ascii=False))

    if args.wait:
        deadline = time.monotonic() + args.max_wait_seconds
        target_ip = str(target.get("ip") or "")
        while time.monotonic() < deadline:
            time.sleep(args.poll_seconds)
            refreshed = select_instance(instance_list(token), None, target_id)
            print_instance(refreshed)
            target_ip = str(refreshed.get("ip") or target_ip)
            if args.action == "start" and tcp_port_open(target_ip, args.ssh_port):
                print(json.dumps({"wait": "ssh-ready", "ip": target_ip, "port": args.ssh_port}, ensure_ascii=False))
                return 0
            if args.action in {"stop", "forcestop"} and target_ip and not tcp_port_open(target_ip, args.ssh_port):
                print(json.dumps({"wait": "ssh-closed", "ip": target_ip, "port": args.ssh_port}, ensure_ascii=False))
                return 0
            status = instance_status(refreshed).lower()
            if args.action == "start" and status in {"running", "active", "started"}:
                return 0
            if args.action in {"stop", "forcestop"} and status in {"shutoff", "stopped", "stop"}:
                return 0
        raise RuntimeError(f"timed out waiting for {args.action}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
