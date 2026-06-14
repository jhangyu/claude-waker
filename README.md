# Claude Waker

自動安排 Claude Code 喚醒請求，協助把 Claude Pro/Max 的 5 小時用量窗口對齊到你想要的工作節奏。

> 本專案 fork 自 [weidwonder/claude-waker](https://github.com/weidwonder/claude-waker)，目前版本已加入 reset time 查詢、條件式喚醒、隔離 worker、預算限制與更完整的 cron 管理。
>
> 繁體中文文件 | [English Documentation](README.en.md)

## 專案用途

Claude Pro/Max 的 5 小時用量窗口通常會從第一次使用開始計算。如果你在不理想的時間第一次使用 Claude，可能會讓重置時間卡在工作流程中間。

Claude Waker 會在你設定的時間點由 cron 自動執行。每次執行時，它會：

1. 依序檢查 `config.yaml` 中的每個帳號。
2. 若有設定 `session_key`，先查詢 claude.ai 的 `five_hour_resets_at`。
3. 如果目前窗口尚未到期，就略過該帳號，避免不必要的喚醒請求。
4. 如果窗口已到期，或 reset time 查詢失敗，就透過 Claude Code CLI 送出低成本喚醒請求。

這讓排程可以維持在固定時間執行，同時盡量避免在用量窗口尚未結束時重複觸發。

## 主要功能

- 支援多個 Claude 帳號依序處理。
- 支援 `session_key` 查詢 5 小時與 7 天 reset time。
- 只有在 5 小時窗口已到期時才喚醒；查詢失敗時會保守地直接喚醒。
- 使用獨立 `wake_worker.py` 執行 Claude 請求，OAuth token 不會出現在命令列參數。
- 支援自訂喚醒時間、喚醒 prompt、模型與單次請求預算。
- 安裝腳本會建立 `.venv`、安裝依賴、連結 Claude CLI，並管理 crontab 區塊。
- 支援 macOS 與 Linux。

## 適合部署在哪裡

建議部署在會長時間開機的機器，例如：

- 家用 NAS
- VPS 或雲端主機
- 長時間開機的 Mac、Linux 電腦
- Raspberry Pi 或其他小型伺服器

這個工具依賴 crontab 排程；如果機器關機或休眠，排程就不會執行。

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

   安裝後請確認可以執行：

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

請把 token 複製下來，稍後填入 `config.yaml` 的 `token` 欄位。

如果你有多個 Claude 帳號，請在瀏覽器切換或登出帳號後，重複執行 `claude setup-token`。

### 2. 取得 claude.ai sessionKey

`session_key` 用於查詢目前帳號的 reset time。若沒有設定，Claude Waker 仍可運作，但每次排程都會直接嘗試喚醒。

取得方式：

1. 在瀏覽器登入 [claude.ai](https://claude.ai)。
2. 開啟瀏覽器開發者工具。
3. 找到 claude.ai 網站 cookie 中的 `sessionKey`。
4. 將值填入 `config.yaml` 的 `session_key` 欄位。

`session_key` 可能會過期；過期時工具會記錄警告，並改為直接喚醒。

### 3. 建立設定檔

第一次執行安裝腳本會從範例檔建立 `config.yaml`：

```bash
./setup.sh
```

看到提示後，編輯 `config.yaml`。

```yaml
accounts:
  - name: "主帳號"
    token: "sk-ant-oat03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    session_key: "sk-ant-sid01-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  - name: "備用帳號"
    token: "sk-ant-oat03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    session_key: "sk-ant-sid01-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# 排程小時，實際 cron 觸發時間固定為每小時的 05 分
wake_hours: "7,12,17"

# 低成本喚醒請求使用的 prompt
wake_prompt: "In one short sentence, confirm this scheduled Claude Code session is active and ready for use."

# 單次喚醒請求的最高預算
wake_max_budget_usd: 0.02

# Claude Code CLI 支援的模型 alias 或完整模型名稱；留空則使用 CLI 預設模型
wake_model: "haiku"
```

### 4. 完成安裝並設定 cron

填好設定後再次執行：

```bash
./setup.sh
```

安裝腳本會：

- 建立 `.venv`
- 安裝 `requirements.txt`
- 將目前可用的 `claude` 或 `claude-bun` 連結到 `.venv/bin/claude`
- 驗證 `config.yaml`
- 在 crontab 中建立 `Claude Waker` 區塊

## 使用方式

### 手動執行一次

```bash
./.venv/bin/python3 ./waker.py
```

### 查詢 reset time

從 `config.yaml` 中所有有 `session_key` 的帳號查詢：

```bash
./.venv/bin/python3 ./reset_time_fetcher.py
```

只查詢指定帳號：

```bash
./.venv/bin/python3 ./reset_time_fetcher.py --account "主帳號"
```

也可以直接用環境變數或參數提供 sessionKey：

```bash
CLAUDE_SESSION_KEY="sk-ant-sid01-..." ./.venv/bin/python3 ./reset_time_fetcher.py
```

### 查看日誌

程式日誌：

```bash
tail -f waker.log
```

cron stdout/stderr：

```bash
tail -f waker.cron.log
```

### 查看目前 crontab

```bash
crontab -l | grep -A 2 -B 1 "Claude Waker"
```

### 修改喚醒時間

1. 編輯 `config.yaml` 的 `wake_hours`。
2. 重新執行 `./setup.sh`。
3. 若腳本偵測到既有 Claude Waker 任務，選擇替換。

## 設定說明

| 欄位 | 必填 | 說明 |
| --- | --- | --- |
| `accounts` | 是 | Claude 帳號清單。每個帳號至少需要 `name` 與 `token`。 |
| `accounts[].name` | 是 | 日誌中顯示的帳號名稱。 |
| `accounts[].token` | 是 | Claude Code OAuth token，用於送出喚醒請求。 |
| `accounts[].session_key` | 否 | claude.ai 的 `sessionKey` cookie，用於查詢 reset time。 |
| `wake_hours` | 是 | 逗號分隔的小時數，範圍 `0-23`。實際觸發分鐘固定為 `05`。 |
| `wake_prompt` | 否 | 喚醒請求送出的 prompt。未設定時使用內建預設值。 |
| `wake_max_budget_usd` | 否 | 單次喚醒請求最高預算，預設 `0.02`。 |
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

實際 cron 會在每個指定小時的第 5 分鐘執行，例如 `7,12,17` 代表 `7:05`、`12:05`、`17:05`。

## 工作日限定

`setup.sh` 目前會建立每日執行的 crontab。若只想在工作日執行，可以手動編輯：

```bash
crontab -e
```

將 Claude Waker 區塊中的排程改成：

```cron
5 7,12,17 * * 1-5 cd /path/to/claude-waker && PATH=.venv/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin ./.venv/bin/python3 ./waker.py >> ./waker.cron.log 2>&1
```

其中 `1-5` 代表週一到週五。

## 卸載

移除 crontab 任務：

```bash
./uninstall.sh
```

卸載腳本只會刪除 Claude Waker 的 crontab 區塊，不會刪除專案檔案、`.venv` 或 `config.yaml`。

## 開發與測試

安裝依賴後可以執行測試：

```bash
./.venv/bin/python3 -m pytest
```

目前主要檔案：

- `waker.py`：主排程流程，負責讀取設定、判斷是否需要喚醒、統計結果。
- `wake_worker.py`：隔離執行 Claude CLI / SDK 的 worker。
- `reset_time_fetcher.py`：查詢 claude.ai reset time。
- `setup.sh`：安裝依賴並管理 crontab。
- `uninstall.sh`：移除 crontab 任務。

## 安全提醒

- `config.yaml` 會包含 OAuth token 與 sessionKey，請不要提交到公開 repository。
- 若懷疑 token 外洩，請重新登入或重新產生 token。
- `session_key` 來自瀏覽器 cookie，可能會過期；過期時重新取得即可。
- 本工具會對 Claude 送出真實請求，請自行確認符合你的帳號使用條款與使用情境。

## 授權

請參考原始專案授權與本 fork 的 repository 設定。
