# Claude Waker

自動安排低成本 Claude Code 喚醒請求，協助把 Claude Pro/Max 的 5 小時用量窗口對齊到你想要的工作節奏。

> 本專案 fork 自 [weidwonder/claude-waker](https://github.com/weidwonder/claude-waker)。目前版本已加入 reset time 查詢、條件式喚醒、隔離 worker、預算限制、模型選擇與更安全的 cron 管理。
>
> [English](README.md) | 繁體中文 | [简体中文](README.zh-CN.md)

## 專案用途

Claude Pro/Max 的用量窗口通常會從該窗口第一次使用時開始計算。如果第一次使用發生在不理想的時間，下一次重置可能就會卡在工作流程中間。

Claude Waker 會依照你設定的時間由 cron 自動執行。每次執行時，它會：

1. 讀取 `config.yaml` 中的每個帳號。
2. 若有設定 `session_key`，先查詢 claude.ai 的 `five_hour_resets_at`。
3. 如果目前 5 小時窗口尚未重置，就略過該帳號。
4. 如果窗口已重置，或 reset time 查詢失敗，就送出低成本 Claude Code 喚醒請求。

這讓排程可以維持固定，同時避免在目前用量窗口仍有效時重複喚醒。

## 主要功能

- 支援多個 Claude 帳號依序處理。
- 使用 claude.ai `sessionKey` 查詢 5 小時與 7 天 reset time。
- 只有在 5 小時窗口已重置時才喚醒；查詢失敗時會保守地直接喚醒。
- 透過 `wake_worker.py` 隔離執行 Claude 請求，OAuth token 不會出現在命令列參數。
- 支援自訂喚醒時間、prompt、模型與單次請求預算。
- 安裝腳本會建立 `.venv`、安裝依賴、連結 Claude CLI，並管理 crontab 區塊。
- 支援 macOS 與 Linux。

## 建議部署環境

建議部署在會長時間開機的機器，例如：

- 家用 NAS
- VPS 或雲端主機
- 長時間開機的 Mac 或 Linux 電腦
- Raspberry Pi 或其他小型伺服器

Claude Waker 依賴 cron。若機器關機或休眠，排程就不會執行。

## 前置需求

1. Python 3.8+
2. [uv](https://github.com/astral-sh/uv)

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. Claude Code CLI

   ```bash
   npm install -g @anthropic-ai/claude-code
   ```

   確認可以執行：

   ```bash
   claude --version
   ```

## 安裝

### 1. 取得 Claude Code OAuth token

每個帳號都需要一組 Claude Code OAuth token：

```bash
claude setup-token
```

完成瀏覽器登入後，終端機會顯示類似下面的 token：

```text
Your OAuth token: sk-ant-oat03-...
```

請將 token 複製到 `config.yaml` 的 `token` 欄位。

若有多個 Claude 帳號，請在瀏覽器切換或登出帳號後，再次執行 `claude setup-token`。

### 2. 取得 claude.ai sessionKey

`session_key` 用於查詢目前 reset time。若沒有設定，Claude Waker 仍可運作，但每次排程都會直接嘗試喚醒。

取得方式：

1. 登入 [claude.ai](https://claude.ai)。
2. 開啟瀏覽器開發者工具。
3. 找到 claude.ai 的 `sessionKey` cookie。
4. 將值複製到 `config.yaml` 的 `session_key` 欄位。

`session_key` 可能會過期；過期時工具會記錄警告並改為直接喚醒。

### 3. 建立 config.yaml

第一次執行安裝腳本會從範例建立 `config.yaml`：

```bash
./setup.sh
```

接著編輯 `config.yaml`：

```yaml
accounts:
  - name: "主帳號"
    token: "sk-ant-oat03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    session_key: "sk-ant-sid01-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  - name: "備用帳號"
    token: "sk-ant-oat03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    session_key: "sk-ant-sid01-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# 排程小時；cron 固定在每個指定小時的 05 分執行
wake_hours: "7,12,17"

# 低成本喚醒請求使用的 prompt
wake_prompt: "In one short sentence, confirm this scheduled Claude Code session is active and ready for use."

# 單次喚醒請求的最高預算
wake_max_budget_usd: 0.03

# Claude Code CLI 支援的模型 alias 或完整模型名稱；留空則使用 CLI 預設模型
wake_model: "haiku"
```

### 4. 完成安裝並設定 cron

再次執行：

```bash
./setup.sh
```

安裝腳本會：

- 建立 `.venv`
- 安裝 `requirements.txt`
- 將可用的 `claude` 或 `claude-bun` 連結到 `.venv/bin/claude`
- 驗證 `config.yaml`
- 建立或替換受管理的 `Claude Waker` crontab 區塊

## 使用方式

### 手動執行一次

```bash
./.venv/bin/python3 ./waker.py
```

### 查詢 reset time

查詢所有設定了 `session_key` 的帳號：

```bash
./.venv/bin/python3 ./reset_time_fetcher.py
```

查詢指定帳號：

```bash
./.venv/bin/python3 ./reset_time_fetcher.py --account "主帳號"
```

也可以直接提供 sessionKey：

```bash
CLAUDE_SESSION_KEY="sk-ant-sid01-..." ./.venv/bin/python3 ./reset_time_fetcher.py
```

### 查看日誌

應用程式日誌：

```bash
tail -f waker.log
```

cron stdout/stderr：

```bash
tail -f waker.cron.log
```

### 查看 crontab 區塊

```bash
crontab -l | grep -A 2 -B 1 "Claude Waker"
```

### 修改喚醒時間

1. 編輯 `config.yaml` 的 `wake_hours`。
2. 重新執行 `./setup.sh`。
3. 依提示替換既有 Claude Waker cron 任務。

## 設定說明

| 欄位 | 必填 | 說明 |
| --- | --- | --- |
| `accounts` | 是 | Claude 帳號清單。每個帳號至少需要 `name` 與 `token`。 |
| `accounts[].name` | 是 | 日誌中顯示的帳號名稱。 |
| `accounts[].token` | 是 | Claude Code OAuth token，用於送出喚醒請求。 |
| `accounts[].session_key` | 否 | claude.ai 的 `sessionKey` cookie，用於查詢 reset time。 |
| `wake_hours` | 是 | 逗號分隔的小時數，範圍 `0-23`。實際執行分鐘固定為 `05`。 |
| `wake_prompt` | 否 | 喚醒請求送出的 prompt。未設定時使用內建預設值。 |
| `wake_max_budget_usd` | 否 | 單次喚醒請求最高預算，預設 `0.03`。 |
| `wake_model` | 否 | Claude Code CLI 模型 alias 或完整模型名稱。 |

## 喚醒時間範例

```yaml
# 早上、中午、傍晚
wake_hours: "7,12,17"

# 上班前、午休後、晚間
wake_hours: "9,14,19"

# 只在早上排程一次
wake_hours: "8"
```

實際 cron 會在每個指定小時的第 5 分鐘執行。例如 `7,12,17` 代表 `7:05`、`12:05`、`17:05`。

## 僅限工作日

`setup.sh` 會建立每日執行的 crontab。若只想在工作日執行，請手動編輯：

```bash
crontab -e
```

將 Claude Waker 排程改成：

```cron
5 7,12,17 * * 1-5 cd /path/to/claude-waker && PATH=.venv/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin ./.venv/bin/python3 ./waker.py >> ./waker.cron.log 2>&1
```

`1-5` 代表週一到週五。

## 卸載

移除 crontab 任務：

```bash
./uninstall.sh
```

卸載腳本只會刪除 Claude Waker 的 crontab 區塊，不會刪除專案檔案、`.venv` 或 `config.yaml`。

## 開發

安裝依賴後執行測試：

```bash
./.venv/bin/python3 -m pytest
```

主要檔案：

- `waker.py`：主排程流程、設定載入、喚醒判斷與統計。
- `wake_worker.py`：隔離執行 Claude CLI / SDK 的 worker。
- `reset_time_fetcher.py`：claude.ai reset time 查詢工具。
- `setup.sh`：依賴安裝與 crontab 管理。
- `uninstall.sh`：移除 crontab。

## 安全提醒

- `config.yaml` 會包含 OAuth token 與 sessionKey，請勿提交到公開 repository。
- 若懷疑 token 外洩，請重新登入或重新產生 token。
- 瀏覽器 `sessionKey` cookie 可能會過期；reset-time 查詢失敗時請更新。
- 本工具會送出真實 Claude 請求，請自行確認符合你的帳號條款與使用情境。

## 授權

請參考原始專案授權與本 fork 的 repository 設定。
