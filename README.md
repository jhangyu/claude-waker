# Claude Waker

Schedule low-cost Claude Code wake-up requests so Claude Pro/Max 5-hour usage windows line up better with your working day.

> This repository is a fork of [weidwonder/claude-waker](https://github.com/weidwonder/claude-waker). This fork adds reset-time lookup, conditional wake-up, an isolated wake worker, request budget limits, model selection, and safer cron management.
>
> English | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md)

## What It Does

Claude Pro/Max usage windows are usually counted from the first use in a window. If that first use happens at an awkward time, the next reset can land in the middle of your workday.

Claude Waker runs from cron at the hours you configure. On each run, it:

1. Reads each account from `config.yaml`.
2. Uses `session_key`, when configured, to query claude.ai for `five_hour_resets_at`.
3. Skips the account when the current 5-hour window has not reset yet.
4. Sends a low-cost Claude Code request when the window has reset, or when reset-time lookup fails.

This keeps the schedule fixed while avoiding unnecessary wake-up requests whenever the current usage window is still active.

## Features

- Handles multiple Claude accounts sequentially.
- Looks up 5-hour and 7-day reset times with a claude.ai `sessionKey`.
- Wakes only after the 5-hour window has reset; falls back to waking when lookup fails.
- Runs Claude requests in `wake_worker.py` so OAuth tokens are not exposed in command-line arguments.
- Supports custom wake hours, prompt, model, and per-request budget.
- Installs a local `.venv`, dependencies, a Claude CLI symlink, and a managed crontab block.
- Supports macOS and Linux.

## Recommended Deployment

Use an always-on machine, such as:

- Home NAS
- VPS or cloud server
- Always-on Mac or Linux computer
- Raspberry Pi or another small server

Claude Waker relies on cron. If the machine is shut down or asleep, scheduled runs will not happen.

## Requirements

1. Python 3.8+
2. [uv](https://github.com/astral-sh/uv)

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. Claude Code CLI

   ```bash
   npm install -g @anthropic-ai/claude-code
   ```

   Verify it is available:

   ```bash
   claude --version
   ```

## Installation

### 1. Get Claude Code OAuth tokens

Each account needs a Claude Code OAuth token:

```bash
claude setup-token
```

After browser authentication, the terminal prints a token like:

```text
Your OAuth token: sk-ant-oat03-...
```

Copy it into the `token` field in `config.yaml`.

For multiple Claude accounts, switch or sign out in the browser, then run `claude setup-token` again.

### 2. Get claude.ai sessionKey values

`session_key` is used to query the current reset time. Claude Waker still works without it, but each scheduled run will directly attempt a wake-up request.

To get it:

1. Sign in to [claude.ai](https://claude.ai).
2. Open your browser developer tools.
3. Find the `sessionKey` cookie for claude.ai.
4. Copy the value into the `session_key` field in `config.yaml`.

The `session_key` can expire. When that happens, Claude Waker logs a warning and falls back to waking directly.

### 3. Create config.yaml

Run the setup script once to create `config.yaml` from the example:

```bash
./setup.sh
```

Then edit `config.yaml`:

```yaml
accounts:
  - name: "Main Account"
    token: "sk-ant-oat03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    session_key: "sk-ant-sid01-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  - name: "Backup Account"
    token: "sk-ant-oat03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    session_key: "sk-ant-sid01-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# Scheduled hours. Cron always runs at minute 05 of each hour.
wake_hours: "7,12,17"

# Prompt used for the low-cost wake request.
wake_prompt: "In one short sentence, confirm this scheduled Claude Code session is active and ready for use."

# Maximum budget for one wake request.
wake_max_budget_usd: 0.02

# Claude Code CLI model alias or full model name. Leave empty to use the CLI default.
wake_model: "haiku"
```

### 4. Finish setup and install cron

Run setup again:

```bash
./setup.sh
```

The script will:

- Create `.venv`
- Install `requirements.txt`
- Link the available `claude` or `claude-bun` command to `.venv/bin/claude`
- Validate `config.yaml`
- Create or replace the managed `Claude Waker` crontab block

## Usage

### Run once manually

```bash
./.venv/bin/python3 ./waker.py
```

### Query reset times

Query all configured accounts with `session_key`:

```bash
./.venv/bin/python3 ./reset_time_fetcher.py
```

Query one account:

```bash
./.venv/bin/python3 ./reset_time_fetcher.py --account "Main Account"
```

Or provide a sessionKey directly:

```bash
CLAUDE_SESSION_KEY="sk-ant-sid01-..." ./.venv/bin/python3 ./reset_time_fetcher.py
```

### View logs

Application log:

```bash
tail -f waker.log
```

Cron stdout/stderr:

```bash
tail -f waker.cron.log
```

### View the crontab block

```bash
crontab -l | grep -A 2 -B 1 "Claude Waker"
```

### Change wake hours

1. Edit `wake_hours` in `config.yaml`.
2. Run `./setup.sh` again.
3. Replace the existing Claude Waker cron task when prompted.

## Configuration

| Field | Required | Description |
| --- | --- | --- |
| `accounts` | Yes | Claude account list. Each account needs at least `name` and `token`. |
| `accounts[].name` | Yes | Account name shown in logs. |
| `accounts[].token` | Yes | Claude Code OAuth token used for wake-up requests. |
| `accounts[].session_key` | No | claude.ai `sessionKey` cookie used for reset-time lookup. |
| `wake_hours` | Yes | Comma-separated hours from `0` to `23`. Runs at minute `05`. |
| `wake_prompt` | No | Prompt sent by the wake-up request. Uses the built-in default when omitted. |
| `wake_max_budget_usd` | No | Maximum budget for one wake request. Defaults to `0.02`. |
| `wake_model` | No | Claude Code CLI model alias or full model name. |

## Wake Hour Examples

```yaml
# Morning, noon, evening
wake_hours: "7,12,17"

# Before work, after lunch, evening
wake_hours: "9,14,19"

# Once in the morning
wake_hours: "8"
```

The actual cron run happens at minute 05 of each configured hour. For example, `7,12,17` means `7:05`, `12:05`, and `17:05`.

## Weekdays Only

`setup.sh` creates a daily crontab entry. To run only on weekdays, edit it manually:

```bash
crontab -e
```

Change the Claude Waker schedule to:

```cron
5 7,12,17 * * 1-5 cd /path/to/claude-waker && PATH=.venv/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin ./.venv/bin/python3 ./waker.py >> ./waker.cron.log 2>&1
```

`1-5` means Monday through Friday.

## Uninstall

Remove the crontab task:

```bash
./uninstall.sh
```

The uninstall script only removes the Claude Waker crontab block. It does not delete project files, `.venv`, or `config.yaml`.

## Development

Run tests after installing dependencies:

```bash
./.venv/bin/python3 -m pytest
```

Main files:

- `waker.py`: Main scheduling flow, config loading, wake decision, and summary.
- `wake_worker.py`: Isolated Claude CLI / SDK worker.
- `reset_time_fetcher.py`: claude.ai reset-time lookup helper.
- `setup.sh`: Dependency installation and crontab management.
- `uninstall.sh`: Crontab removal.

## Security Notes

- `config.yaml` contains OAuth tokens and session keys. Do not commit it to a public repository.
- If a token may have leaked, sign in again or regenerate it.
- Browser `sessionKey` cookies can expire. Refresh them when reset-time lookup starts failing.
- This tool sends real Claude requests. Make sure the usage fits your account terms and workflow.

## License

See the original project license and this fork's repository settings.
