#!/usr/bin/env python3
"""Fetch Claude reset times with a claude.ai sessionKey.

This module uses the same private claude.ai endpoints that the macOS Claude
Usage Tracker relies on:

    GET https://claude.ai/api/organizations
    GET https://claude.ai/api/organizations/{org_id}/usage

The usage response contains reset timestamps for the 5-hour and 7-day windows:
    five_hour.resets_at
    seven_day.resets_at
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml


CLAUDE_API_BASE = "https://claude.ai/api"
DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.yaml"
DISPLAY_TIMEZONE = timezone(timedelta(hours=8))


class ClaudeResetTimeError(RuntimeError):
    """Raised when reset-time lookup fails."""


@dataclass
class ConfigAccount:
    name: str
    session_key: str


@dataclass
class ClaudeOrganization:
    uuid: str
    name: str = ""


@dataclass
class ClaudeResetTimes:
    organization_id: str
    organization_name: str
    five_hour_resets_at: str | None
    seven_day_resets_at: str | None
    five_hour_resets_in_seconds: int | None
    seven_day_resets_in_seconds: int | None
    fetched_at: str
    raw_usage: dict[str, Any] | None = None

    def to_dict(self, *, include_raw: bool = False) -> dict[str, Any]:
        payload = asdict(self)
        if not include_raw:
            payload.pop("raw_usage", None)
        return payload


def fetch_reset_times(
    session_key: str,
    *,
    organization_id: str | None = None,
    timeout_s: int = 30,
    include_raw: bool = False,
) -> ClaudeResetTimes:
    """Fetch five-hour and seven-day reset timestamps for a claude.ai account.

    If organization_id is omitted, the first organization returned by
    /organizations is used. Claude personal accounts generally still appear as
    an organization record in this endpoint.
    """
    clean_session_key = session_key.strip()
    if not clean_session_key:
        raise ClaudeResetTimeError("session_key is required")

    organizations = fetch_organizations(clean_session_key, timeout_s=timeout_s)
    selected_org = select_organization(organizations, organization_id)
    usage = fetch_usage(clean_session_key, selected_org.uuid, timeout_s=timeout_s)

    five_hour = usage.get("five_hour") if isinstance(usage.get("five_hour"), dict) else {}
    seven_day = usage.get("seven_day") if isinstance(usage.get("seven_day"), dict) else {}

    five_hour_resets_at = _format_display_time(_string_or_none(five_hour.get("resets_at")))
    seven_day_resets_at = _format_display_time(_string_or_none(seven_day.get("resets_at")))

    return ClaudeResetTimes(
        organization_id=selected_org.uuid,
        organization_name=selected_org.name,
        five_hour_resets_at=five_hour_resets_at,
        seven_day_resets_at=seven_day_resets_at,
        five_hour_resets_in_seconds=_seconds_until(five_hour_resets_at),
        seven_day_resets_in_seconds=_seconds_until(seven_day_resets_at),
        fetched_at=datetime.now(timezone.utc).isoformat(),
        raw_usage=usage if include_raw else None,
    )


def load_config_accounts(config_path: str | Path = DEFAULT_CONFIG_PATH) -> list[ConfigAccount]:
    """Load accounts with session_key from config.yaml."""
    path = Path(config_path)
    if not path.exists():
        raise ClaudeResetTimeError(f"Config file not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as fh:
            config = yaml.safe_load(fh) or {}
    except OSError as exc:
        raise ClaudeResetTimeError(f"Failed to read config file: {path}") from exc
    except yaml.YAMLError as exc:
        raise ClaudeResetTimeError(f"Failed to parse config file: {path}") from exc

    raw_accounts = config.get("accounts") or []
    if not isinstance(raw_accounts, list):
        raise ClaudeResetTimeError("config.yaml field 'accounts' must be a list")

    accounts: list[ConfigAccount] = []
    for index, account in enumerate(raw_accounts, start=1):
        if not isinstance(account, dict):
            continue
        name = str(account.get("name") or f"account-{index}")
        session_key = str(account.get("session_key") or "").strip()
        if session_key:
            accounts.append(ConfigAccount(name=name, session_key=session_key))

    if not accounts:
        raise ClaudeResetTimeError("No accounts with session_key found in config.yaml")
    return accounts


def fetch_reset_times_from_config(
    *,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    account_name: str | None = None,
    timeout_s: int = 30,
    include_raw: bool = False,
) -> list[dict[str, Any]]:
    """Fetch reset times for all config accounts, or one named account."""
    accounts = load_config_accounts(config_path)
    if account_name:
        accounts = [account for account in accounts if account.name == account_name]
        if not accounts:
            raise ClaudeResetTimeError(f"Account not found in config.yaml: {account_name}")

    results: list[dict[str, Any]] = []
    for account in accounts:
        try:
            reset_times = fetch_reset_times(
                account.session_key,
                timeout_s=timeout_s,
                include_raw=include_raw,
            )
            payload = reset_times.to_dict(include_raw=include_raw)
            payload["account_name"] = account.name
            payload["ok"] = True
        except ClaudeResetTimeError as exc:
            payload = {
                "account_name": account.name,
                "ok": False,
                "error": str(exc),
            }
        results.append(payload)
    return results


def fetch_organizations(session_key: str, *, timeout_s: int = 30) -> list[ClaudeOrganization]:
    """Return organizations visible to the provided claude.ai sessionKey."""
    payload = _get_json("/organizations", session_key=session_key, timeout_s=timeout_s)
    if not isinstance(payload, list):
        raise ClaudeResetTimeError("/organizations returned a non-list response")

    organizations: list[ClaudeOrganization] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        uuid = _string_or_none(item.get("uuid"))
        if not uuid:
            continue
        organizations.append(
            ClaudeOrganization(
                uuid=uuid,
                name=_string_or_none(item.get("name")) or "",
            )
        )

    if not organizations:
        raise ClaudeResetTimeError("No organizations found for this sessionKey")
    return organizations


def fetch_usage(session_key: str, organization_id: str, *, timeout_s: int = 30) -> dict[str, Any]:
    """Return the raw /usage payload for an organization."""
    payload = _get_json(
        f"/organizations/{organization_id}/usage",
        session_key=session_key,
        timeout_s=timeout_s,
    )
    if not isinstance(payload, dict):
        raise ClaudeResetTimeError("/usage returned a non-object response")
    return payload


def select_organization(
    organizations: list[ClaudeOrganization],
    organization_id: str | None,
) -> ClaudeOrganization:
    """Select an organization by id, or default to the first visible org."""
    if not organization_id:
        return organizations[0]

    for organization in organizations:
        if organization.uuid == organization_id:
            return organization

    available = ", ".join(org.uuid for org in organizations)
    raise ClaudeResetTimeError(
        f"organization_id not found: {organization_id}. Available organizations: {available}"
    )


def _get_json(path: str, *, session_key: str, timeout_s: int) -> Any:
    url = f"{CLAUDE_API_BASE}{path}"
    request = urllib.request.Request(
        url,
        headers={
            "Cookie": f"sessionKey={session_key}",
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/17.0 Safari/605.1.15"
            ),
            "Referer": "https://claude.ai",
            "Origin": "https://claude.ai",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code in (401, 403):
            raise ClaudeResetTimeError("Unauthorized. The sessionKey may be expired.") from exc
        raise ClaudeResetTimeError(f"Claude API returned HTTP {exc.code}: {body[:300]}") from exc
    except urllib.error.URLError as exc:
        raise ClaudeResetTimeError(f"Failed to connect to Claude API: {exc}") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ClaudeResetTimeError(f"Claude API returned invalid JSON: {body[:300]}") from exc


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _seconds_until(value: str | None) -> int | None:
    parsed = _parse_iso_datetime(value)
    if parsed is None:
        return None
    return max(0, int((parsed - datetime.now(timezone.utc)).total_seconds()))


def _format_display_time(value: str | None) -> str | None:
    parsed = _parse_iso_datetime(value)
    if parsed is None:
        return None
    return parsed.astimezone(DISPLAY_TIMEZONE).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch Claude five_hour/seven_day reset times with a claude.ai sessionKey."
    )
    parser.add_argument(
        "--session-key",
        default=os.environ.get("CLAUDE_SESSION_KEY"),
        help="claude.ai sessionKey cookie value. Defaults to CLAUDE_SESSION_KEY. If omitted, config.yaml is used.",
    )
    parser.add_argument(
        "--organization-id",
        default=os.environ.get("CLAUDE_ORGANIZATION_ID"),
        help="Optional Claude organization UUID. Only applies with --session-key.",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to config.yaml when --session-key is omitted.",
    )
    parser.add_argument(
        "--account",
        help="Only fetch the named account from config.yaml.",
    )
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--include-raw", action="store_true")
    args = parser.parse_args()

    try:
        if args.session_key:
            reset_times = fetch_reset_times(
                args.session_key,
                organization_id=args.organization_id,
                timeout_s=args.timeout,
                include_raw=args.include_raw,
            )
            output: Any = reset_times.to_dict(include_raw=args.include_raw)
        else:
            output = fetch_reset_times_from_config(
                config_path=args.config,
                account_name=args.account,
                timeout_s=args.timeout,
                include_raw=args.include_raw,
            )
    except ClaudeResetTimeError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
