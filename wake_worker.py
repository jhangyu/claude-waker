#!/usr/bin/env python3
"""Isolated Claude wake worker.

The parent process sends configuration through stdin as JSON so the OAuth token
does not appear in command-line arguments.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from typing import Any


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def print_budget_details(source: str, max_budget_usd: float, payload: dict[str, Any] | None = None) -> None:
    payload = payload or {}
    cost = first_present(
        payload.get("total_cost_usd"),
        payload.get("cost_usd"),
        payload.get("cost"),
        payload.get("estimated_cost_usd"),
    )
    parts = [f"max_budget_usd={max_budget_usd}"]
    if cost is not None:
        parts.append(f"reported_cost_usd={cost}")
    parts.append(f"source={source}")
    print(f"BUDGET_DETAILS:{', '.join(parts)}")


def run_claude_json(
    *,
    claude_cli_path: str | None,
    prompt: str,
    max_budget_usd: float,
    wake_model: str | None,
    timeout_s: int,
) -> dict[str, Any] | None:
    command = [
        claude_cli_path or "claude",
        "-p",
        prompt,
        "--output-format",
        "json",
        "--no-session-persistence",
        "--effort",
        "low",
        "--max-budget-usd",
        str(max_budget_usd),
    ]
    if wake_model:
        command.extend(["--model", wake_model])

    try:
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=timeout_s,
            env=os.environ.copy(),
        )
        payload = json.loads(result.stdout) if result.stdout.strip() else {}
        if result.returncode != 0 or payload.get("is_error"):
            error = payload.get("result") or payload.get("subtype") or result.stderr.strip() or result.stdout.strip()
            print(f"CLAUDE_ERROR:{error}")
            if "max_budget" in str(error):
                print_budget_details("claude-cli", max_budget_usd, payload)
            return None
        return payload
    except Exception as exc:
        print(f"CLAUDE_ERROR:{exc}")
        return None


def wake_with_cli(config: dict[str, Any]) -> bool:
    payload = run_claude_json(
        claude_cli_path=config.get("claude_cli_path"),
        prompt=config["wake_prompt"],
        max_budget_usd=config["wake_max_budget_usd"],
        wake_model=config.get("wake_model"),
        timeout_s=config["command_timeout_s"],
    )
    if not payload:
        return False

    requested_wake_model = config.get("wake_model")
    print(f"COST_USD:{payload.get('total_cost_usd', 'unknown')}")
    print(f"SESSION_ID:{payload.get('session_id', '')}")
    print(f"MODEL_NAME:{payload.get('model', '') or requested_wake_model or ''}")
    print("SUCCESS:ResultMessage")
    return True


async def wake_with_sdk(config: dict[str, Any]) -> None:
    try:
        from claude_agent_sdk import ClaudeAgentOptions, query

        async with asyncio.timeout(config["command_timeout_s"]):
            with tempfile.TemporaryDirectory() as tmp_dir:
                options = ClaudeAgentOptions(
                    cwd=tmp_dir,
                    tools=[],
                    max_turns=1,
                    max_budget_usd=config["wake_max_budget_usd"],
                    model=config.get("wake_model"),
                    setting_sources=[],
                    cli_path=config.get("claude_cli_path"),
                )
                gen = query(prompt=config["wake_prompt"], options=options)
                assistant_seen = False
                wake_success = False
                wake_error = None
                wake_cost = None
                wake_error_cost = None

                async for msg in gen:
                    msg_type = type(msg).__name__
                    if msg_type == "AssistantMessage":
                        assistant_seen = True
                    if msg_type == "ResultMessage":
                        subtype = getattr(msg, "subtype", "")
                        result = getattr(msg, "result", None)
                        if getattr(msg, "is_error", False):
                            wake_error = result or subtype or "result_error"
                            wake_error_cost = getattr(msg, "total_cost_usd", None)
                        else:
                            wake_success = True
                            wake_cost = getattr(msg, "total_cost_usd", "unknown")

                if wake_error:
                    print(f"ERROR:{wake_error}")
                    if "max_budget" in str(wake_error):
                        print_budget_details(
                            "claude-agent-sdk",
                            config["wake_max_budget_usd"],
                            {"total_cost_usd": wake_error_cost},
                        )
                    return
                if wake_success:
                    print(f"COST_USD:{wake_cost}")
                    print(f"MODEL_NAME:{config.get('wake_model') or ''}")
                    print("SUCCESS:ResultMessage")
                    return
                if assistant_seen:
                    print(f"MODEL_NAME:{config.get('wake_model') or ''}")
                    print("SUCCESS:AssistantMessage")
                    return
            print("ERROR:未收到有效響應")
    except asyncio.TimeoutError:
        print("TIMEOUT:響應超時")
    except Exception as exc:
        print(f"ERROR:{exc}")


async def run() -> None:
    config = json.loads(sys.stdin.read() or "{}")
    config["wake_max_budget_usd"] = float(config["wake_max_budget_usd"])
    config["command_timeout_s"] = int(config["command_timeout_s"])
    os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = config["oauth_token"]

    if wake_with_cli(config):
        return
    await wake_with_sdk(config)


if __name__ == "__main__":
    asyncio.run(run())
