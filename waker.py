#!/usr/bin/env python3
"""
Claude Waker - 自動喚醒 Claude 賬號以優化5小時限額窗口
"""

import asyncio
import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from reset_time_fetcher import ClaudeResetTimeError, fetch_reset_times

# 設置日誌
LOG_FILE = Path(__file__).parent / "waker.log"
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

DEFAULT_WAKE_PROMPT = (
    "In one short sentence, confirm this scheduled Claude Code session is active and ready for use."
)
DEFAULT_WAKE_MAX_BUDGET_USD = 0.02
WAKE_COMMAND_TIMEOUT_SECONDS = 60
WAKE_SUBPROCESS_TIMEOUT_SECONDS = 70
ACCOUNT_DELAY_SECONDS = 2
PLACEHOLDER_TOKENS = {"your-oauth-token-here-1", "your-oauth-token-here-2"}


def redact_sensitive(text):
    """避免 token 出現在日誌中。"""
    if not text:
        return ''
    return text.replace('sk-ant-', 'sk-ant-[redacted]-')


def parse_reset_time(value):
    """解析 reset_time_fetcher 回傳的 ISO 時間字串。"""
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


def has_configured_token(token):
    """判斷 OAuth token 是否已填入真實值。"""
    return bool(token) and token not in PLACEHOLDER_TOKENS


def find_prefixed_line(lines, prefix):
    """從子程序輸出中找出指定 prefix 的第一個值。"""
    return next((line.split(prefix, 1)[1] for line in lines if line.startswith(prefix)), None)


def parse_wake_subprocess_output(output, stderr_output):
    """解析喚醒子程序 stdout/stderr，回傳狀態與相關欄位。"""
    output_lines = output.splitlines()
    result = {
        "status": "fail",
        "success_type": None,
        "error_msg": None,
        "cost_usd": find_prefixed_line(output_lines, "COST_USD:"),
        "session_id": find_prefixed_line(output_lines, "SESSION_ID:"),
        "model_name": find_prefixed_line(output_lines, "MODEL_NAME:"),
    }

    if "SUCCESS:" in output:
        result["status"] = "success"
        result["success_type"] = output.split("SUCCESS:")[-1].splitlines()[0]
        return result

    if "TIMEOUT:" in output:
        result["status"] = "timeout"
        return result

    error_msg = find_prefixed_line(output_lines, "CLAUDE_ERROR:")
    if error_msg is None and "ERROR:" in output:
        error_msg = output.split("ERROR:", 1)[1]
    if not error_msg and stderr_output:
        error_msg = stderr_output

    budget_details = find_prefixed_line(output_lines, "BUDGET_DETAILS:")
    if budget_details:
        error_msg = f"{error_msg} ({budget_details})"

    result["error_msg"] = error_msg or output
    return result


def should_wake_account(account_name, session_key):
    """回傳是否需要喚醒；只有 reset time 明確尚未到期時才跳過。"""
    if not session_key:
        logger.warning(f"⚠️  {account_name} - session_key 未配置，直接執行喚醒")
        return True

    try:
        reset_times = fetch_reset_times(session_key, timeout_s=30)
    except ClaudeResetTimeError as e:
        logger.warning(f"⚠️  {account_name} - reset time API 無法正常回應，直接執行喚醒: {e}")
        return True

    five_hour_resets_at = reset_times.five_hour_resets_at
    if not five_hour_resets_at:
        logger.warning(f"⚠️  {account_name} - API 回應缺少 five_hour_resets_at，直接執行喚醒")
        return True

    reset_at = parse_reset_time(five_hour_resets_at)
    if reset_at is None:
        logger.warning(
            f"⚠️  {account_name} - five_hour_resets_at 無法解析，直接執行喚醒: {five_hour_resets_at}"
        )
        return True

    now = datetime.now(timezone.utc)
    if now < reset_at:
        logger.info(
            f"⏭️  {account_name} - five_hour_resets_at 尚未到期 ({five_hour_resets_at})，跳過喚醒"
        )
        return False

    logger.info(f"⏰ {account_name} - five_hour_resets_at 已到期 ({five_hour_resets_at})，執行喚醒")
    return True


def build_wake_subprocess_script(oauth_token, wake_prompt, wake_max_budget_usd, wake_model, claude_cli_path):
    """建立隔離 token 的子程序腳本。"""
    command_timeout = WAKE_COMMAND_TIMEOUT_SECONDS
    max_budget = float(wake_max_budget_usd)
    return f'''
import os
import asyncio
import json
import subprocess
import tempfile

async def run():
    os.environ['CLAUDE_CODE_OAUTH_TOKEN'] = {repr(oauth_token)}
    claude_cli_path = {repr(claude_cli_path)}
    requested_wake_model = {repr(wake_model)}
    requested_max_budget_usd = {repr(max_budget)}

    def first_present(*values):
        for value in values:
            if value is not None and value != '':
                return value
        return None

    def print_budget_details(source, payload=None):
        payload = payload or {{}}
        cost = first_present(
            payload.get('total_cost_usd'),
            payload.get('cost_usd'),
            payload.get('cost'),
            payload.get('estimated_cost_usd'),
        )
        parts = [f"max_budget_usd={{requested_max_budget_usd}}"]
        if cost is not None:
            parts.append(f"reported_cost_usd={{cost}}")
        parts.append(f"source={{source}}")
        print(f"BUDGET_DETAILS:{{', '.join(parts)}}")

    def run_claude_json(prompt, timeout={command_timeout}, use_model=True):
        command = [
            claude_cli_path or 'claude',
            '-p',
            prompt,
            '--output-format',
            'json',
            '--no-session-persistence',
            '--effort',
            'low',
            '--max-budget-usd',
            str(requested_max_budget_usd),
        ]
        if use_model and requested_wake_model:
            command.extend(['--model', requested_wake_model])
        try:
            result = subprocess.run(
                command,
                text=True,
                capture_output=True,
                timeout=timeout,
                env=os.environ.copy(),
            )
            payload = json.loads(result.stdout) if result.stdout.strip() else {{}}
            if result.returncode != 0 or payload.get('is_error'):
                error = payload.get('result') or payload.get('subtype') or result.stderr.strip() or result.stdout.strip()
                print(f"CLAUDE_ERROR:{{error}}")
                if 'max_budget' in str(error):
                    print_budget_details('claude-cli', payload)
                return None
            return payload
        except Exception as e:
            print(f"CLAUDE_ERROR:{{e}}")
            return None

    def wake_with_cli():
        payload = run_claude_json({repr(wake_prompt)})
        if not payload:
            return False
        print(f"COST_USD:{{payload.get('total_cost_usd', 'unknown')}}")
        print(f"SESSION_ID:{{payload.get('session_id', '')}}")
        print(f"MODEL_NAME:{{payload.get('model', '') or requested_wake_model or ''}}")
        print("SUCCESS:ResultMessage")
        return True

    if wake_with_cli():
        return

    # Fallback to the SDK for environments where `claude -p` cannot run.
    try:
        from claude_agent_sdk import query, ClaudeAgentOptions

        async with asyncio.timeout({command_timeout}):
            with tempfile.TemporaryDirectory() as tmp_dir:
                options = ClaudeAgentOptions(
                    cwd=tmp_dir,
                    tools=[],
                    max_turns=1,
                    max_budget_usd={repr(max_budget)},
                    model={repr(wake_model)},
                    setting_sources=[],
                    cli_path=claude_cli_path,
                )
                gen = query(prompt={repr(wake_prompt)}, options=options)
                assistant_seen = False
                wake_success = False
                wake_error = None
                wake_cost = None
                wake_error_cost = None
                async for msg in gen:
                    msg_type = type(msg).__name__
                    if msg_type == 'AssistantMessage':
                        assistant_seen = True
                    if msg_type == 'ResultMessage':
                        subtype = getattr(msg, 'subtype', '')
                        result = getattr(msg, 'result', None)
                        if getattr(msg, 'is_error', False):
                            wake_error = result or subtype or 'result_error'
                            wake_error_cost = getattr(msg, 'total_cost_usd', None)
                        else:
                            wake_success = True
                            wake_cost = getattr(msg, 'total_cost_usd', 'unknown')
                if wake_error:
                    print(f"ERROR:{{wake_error}}")
                    if 'max_budget' in str(wake_error):
                        print_budget_details('claude-agent-sdk', {{'total_cost_usd': wake_error_cost}})
                    return
                if wake_success:
                    print(f"COST_USD:{{wake_cost}}")
                    print(f"MODEL_NAME:{{requested_wake_model or ''}}")
                    print("SUCCESS:ResultMessage")
                    return
                if assistant_seen:
                    print(f"MODEL_NAME:{{requested_wake_model or ''}}")
                    print("SUCCESS:AssistantMessage")
                    return
            print("ERROR:未收到有效響應")
    except asyncio.TimeoutError:
        print("TIMEOUT:響應超時")
    except Exception as e:
        print(f"ERROR:{{e}}")

asyncio.run(run())
'''


def load_config():
    """加載配置文件"""
    config_file = Path(__file__).parent / "config.yaml"

    if not config_file.exists():
        logger.error(f"❌ 配置文件不存在: {config_file}")
        logger.error("請複製 config.yaml.example 為 config.yaml 並填入配置")
        sys.exit(1)

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # 驗證配置
        if not config.get('accounts'):
            logger.error("❌ 配置文件缺少 accounts 字段")
            sys.exit(1)

        if not config.get('wake_hours'):
            logger.error("❌ 配置文件缺少 wake_hours 字段")
            sys.exit(1)

        if not config.get('wake_prompt'):
            config['wake_prompt'] = DEFAULT_WAKE_PROMPT

        if not config.get('wake_max_budget_usd'):
            config['wake_max_budget_usd'] = DEFAULT_WAKE_MAX_BUDGET_USD

        if 'wake_model' not in config:
            config['wake_model'] = None

        return config
    except Exception as e:
        logger.error(f"❌ 讀取配置文件失敗: {e}")
        sys.exit(1)


async def wake_account_subprocess(account_name, oauth_token, wake_prompt, wake_max_budget_usd, wake_model):
    """在子進程中喚醒單個賬號，確保 token 完全隔離"""
    try:
        logger.info(f"正在喚醒賬號: {account_name}")
        claude_cli_path = shutil.which('claude') or shutil.which('claude-bun')
        script = build_wake_subprocess_script(
            oauth_token,
            wake_prompt,
            wake_max_budget_usd,
            wake_model,
            claude_cli_path,
        )

        # 運行子進程
        process = await asyncio.create_subprocess_exec(
            sys.executable, '-c', script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=WAKE_SUBPROCESS_TIMEOUT_SECONDS,
            )
            output = stdout.decode('utf-8').strip()
            stderr_output = stderr.decode('utf-8', errors='replace').strip()
            parsed = parse_wake_subprocess_output(output, stderr_output)

            if parsed["status"] == "success":
                cost_text = f"，成本: ${parsed['cost_usd']}" if parsed["cost_usd"] else ""
                logger.info(
                    f"✅ {account_name} - 喚醒成功，收到響應: {parsed['success_type']}{cost_text}"
                )
                return "success"

            if parsed["status"] == "timeout":
                logger.warning(
                    f"⚠️  {account_name} - 響應超時（{WAKE_COMMAND_TIMEOUT_SECONDS}秒），但喚醒請求已發送"
                )
                return "success"

            if stderr_output and parsed["error_msg"] != stderr_output:
                logger.error(f"❌ {account_name} - 子進程錯誤輸出: {redact_sensitive(stderr_output)}")
            logger.error(f"❌ {account_name} - 喚醒失敗: {redact_sensitive(parsed['error_msg'])}")
            return "fail"

        except asyncio.TimeoutError:
            process.kill()
            logger.warning(f"⚠️  {account_name} - 子進程超時")
            return "fail"

    except Exception as e:
        logger.error(f"❌ {account_name} - 喚醒失敗: {e}")
        return "fail"


async def main():
    """主函數"""
    logger.info("=" * 60)
    logger.info("Claude Waker 開始運行")

    # 加載配置
    config = load_config()

    logger.info(f"開始喚醒任務，共 {len(config['accounts'])} 個賬號")

    # 統計結果
    success_count = 0
    fail_count = 0
    skip_count = 0

    # 遍歷所有賬號
    for idx, account in enumerate(config['accounts']):
        account_name = account.get('name', '未命名賬號')
        oauth_token = account.get('token', '')
        session_key = account.get('session_key', '')

        if not has_configured_token(oauth_token):
            logger.warning(f"⚠️  {account_name} - Token 未配置，跳過")
            fail_count += 1
            continue

        try:
            if not should_wake_account(account_name, session_key):
                skip_count += 1
                continue

            status = await wake_account_subprocess(
                account_name,
                oauth_token,
                config['wake_prompt'],
                config['wake_max_budget_usd'],
                config['wake_model'],
            )
            if status == "success":
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            logger.error(f"❌ {account_name} - 任務執行失敗: {e}")
            fail_count += 1

        # 賬號之間間隔，避免多帳號同時打到 Claude CLI。
        if idx < len(config['accounts']) - 1:
            await asyncio.sleep(ACCOUNT_DELAY_SECONDS)

    # 輸出統計
    logger.info("-" * 60)
    logger.info(f"喚醒任務完成: 成功 {success_count} 個，略過 {skip_count} 個，失敗 {fail_count} 個")
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n程序被用戶中斷")
    except Exception as e:
        logger.error(f"程序異常: {e}")
        sys.exit(1)
