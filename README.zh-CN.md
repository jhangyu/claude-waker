# Claude Waker

自动安排低成本 Claude Code 唤醒请求，帮助把 Claude Pro/Max 的 5 小时用量窗口对齐到你的工作节奏。

> 本项目 fork 自 [weidwonder/claude-waker](https://github.com/weidwonder/claude-waker)。当前版本已加入 reset time 查询、条件式唤醒、隔离 worker、预算限制、模型选择和更安全的 cron 管理。
>
> [English](README.md) | [繁體中文](README.zh-TW.md) | 简体中文

## 项目用途

Claude Pro/Max 的用量窗口通常会从该窗口第一次使用时开始计算。如果第一次使用发生在不理想的时间，下一次重置可能会卡在工作流程中间。

Claude Waker 会按照你设置的时间由 cron 自动执行。每次执行时，它会：

1. 读取 `config.yaml` 中的每个账号。
2. 如果设置了 `session_key`，先查询 claude.ai 的 `five_hour_resets_at`。
3. 如果当前 5 小时窗口尚未重置，就跳过该账号。
4. 如果窗口已重置，或 reset time 查询失败，就发送低成本 Claude Code 唤醒请求。

这样可以保持固定排程，同时避免在当前用量窗口仍有效时重复唤醒。

## 主要功能

- 支持多个 Claude 账号依次处理。
- 使用 claude.ai `sessionKey` 查询 5 小时和 7 天 reset time。
- 只有在 5 小时窗口已重置时才唤醒；查询失败时会保守地直接唤醒。
- 通过 `wake_worker.py` 隔离执行 Claude 请求，OAuth token 不会出现在命令行参数中。
- 支持自定义唤醒时间、prompt、模型和单次请求预算。
- 安装脚本会创建 `.venv`、安装依赖、链接 Claude CLI，并管理 crontab 区块。
- 支持 macOS 和 Linux。

## 推荐部署环境

建议部署在会长期开机的机器，例如：

- 家用 NAS
- VPS 或云服务器
- 长期开机的 Mac 或 Linux 电脑
- Raspberry Pi 或其他小型服务器

Claude Waker 依赖 cron。如果机器关机或休眠，排程就不会执行。

## 前置要求

1. Python 3.8+
2. [uv](https://github.com/astral-sh/uv)

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. Claude Code CLI

   ```bash
   npm install -g @anthropic-ai/claude-code
   ```

   确认可以执行：

   ```bash
   claude --version
   ```

## 安装

### 1. 获取 Claude Code OAuth token

每个账号都需要一组 Claude Code OAuth token：

```bash
claude setup-token
```

完成浏览器登录后，终端会显示类似下面的 token：

```text
Your OAuth token: sk-ant-oat03-...
```

请将 token 复制到 `config.yaml` 的 `token` 字段。

如果有多个 Claude 账号，请在浏览器切换或退出账号后，再次执行 `claude setup-token`。

### 2. 获取 claude.ai sessionKey

`session_key` 用于查询当前 reset time。如果没有设置，Claude Waker 仍可运行，但每次排程都会直接尝试唤醒。

获取方式：

1. 登录 [claude.ai](https://claude.ai)。
2. 打开浏览器开发者工具。
3. 找到 claude.ai 的 `sessionKey` cookie。
4. 将值复制到 `config.yaml` 的 `session_key` 字段。

`session_key` 可能会过期；过期时工具会记录警告并改为直接唤醒。

### 3. 创建 config.yaml

第一次执行安装脚本会从示例创建 `config.yaml`：

```bash
./setup.sh
```

然后编辑 `config.yaml`：

```yaml
accounts:
  - name: "主账号"
    token: "sk-ant-oat03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    session_key: "sk-ant-sid01-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  - name: "备用账号"
    token: "sk-ant-oat03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    session_key: "sk-ant-sid01-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# 排程小时；cron 固定在每个指定小时的 05 分执行
wake_hours: "7,12,17"

# 低成本唤醒请求使用的 prompt
wake_prompt: "In one short sentence, confirm this scheduled Claude Code session is active and ready for use."

# 单次唤醒请求的最高预算
wake_max_budget_usd: 0.03

# Claude Code CLI 支持的模型 alias 或完整模型名称；留空则使用 CLI 默认模型
wake_model: "haiku"
```

### 4. 完成安装并设置 cron

再次执行：

```bash
./setup.sh
```

安装脚本会：

- 创建 `.venv`
- 安装 `requirements.txt`
- 将可用的 `claude` 或 `claude-bun` 链接到 `.venv/bin/claude`
- 验证 `config.yaml`
- 创建或替换受管理的 `Claude Waker` crontab 区块

## 使用方式

### 手动执行一次

```bash
./.venv/bin/python3 ./waker.py
```

### 查询 reset time

查询所有设置了 `session_key` 的账号：

```bash
./.venv/bin/python3 ./reset_time_fetcher.py
```

查询指定账号：

```bash
./.venv/bin/python3 ./reset_time_fetcher.py --account "主账号"
```

也可以直接提供 sessionKey：

```bash
CLAUDE_SESSION_KEY="sk-ant-sid01-..." ./.venv/bin/python3 ./reset_time_fetcher.py
```

### 查看日志

应用日志：

```bash
tail -f waker.log
```

cron stdout/stderr：

```bash
tail -f waker.cron.log
```

### 查看 crontab 区块

```bash
crontab -l | grep -A 2 -B 1 "Claude Waker"
```

### 修改唤醒时间

1. 编辑 `config.yaml` 的 `wake_hours`。
2. 重新执行 `./setup.sh`。
3. 按提示替换现有 Claude Waker cron 任务。

## 配置说明

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `accounts` | 是 | Claude 账号列表。每个账号至少需要 `name` 和 `token`。 |
| `accounts[].name` | 是 | 日志中显示的账号名称。 |
| `accounts[].token` | 是 | Claude Code OAuth token，用于发送唤醒请求。 |
| `accounts[].session_key` | 否 | claude.ai 的 `sessionKey` cookie，用于查询 reset time。 |
| `wake_hours` | 是 | 逗号分隔的小时数，范围 `0-23`。实际执行分钟固定为 `05`。 |
| `wake_prompt` | 否 | 唤醒请求发送的 prompt。未设置时使用内置默认值。 |
| `wake_max_budget_usd` | 否 | 单次唤醒请求最高预算，默认 `0.03`。 |
| `wake_model` | 否 | Claude Code CLI 模型 alias 或完整模型名称。 |

## 唤醒时间示例

```yaml
# 早上、中午、傍晚
wake_hours: "7,12,17"

# 上班前、午休后、晚间
wake_hours: "9,14,19"

# 只在早上排程一次
wake_hours: "8"
```

实际 cron 会在每个指定小时的第 5 分钟执行。例如 `7,12,17` 代表 `7:05`、`12:05`、`17:05`。

## 仅限工作日

`setup.sh` 会创建每日执行的 crontab。如果只想在工作日执行，请手动编辑：

```bash
crontab -e
```

将 Claude Waker 排程改成：

```cron
5 7,12,17 * * 1-5 cd /path/to/claude-waker && PATH=.venv/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin ./.venv/bin/python3 ./waker.py >> ./waker.cron.log 2>&1
```

`1-5` 代表周一到周五。

## 卸载

移除 crontab 任务：

```bash
./uninstall.sh
```

卸载脚本只会删除 Claude Waker 的 crontab 区块，不会删除项目文件、`.venv` 或 `config.yaml`。

## 开发

安装依赖后执行测试：

```bash
./.venv/bin/python3 -m pytest
```

主要文件：

- `waker.py`：主排程流程、配置加载、唤醒判断和统计。
- `wake_worker.py`：隔离执行 Claude CLI / SDK 的 worker。
- `reset_time_fetcher.py`：claude.ai reset time 查询工具。
- `setup.sh`：依赖安装和 crontab 管理。
- `uninstall.sh`：移除 crontab。

## 安全提醒

- `config.yaml` 会包含 OAuth token 和 sessionKey，请勿提交到公开 repository。
- 如果怀疑 token 泄露，请重新登录或重新生成 token。
- 浏览器 `sessionKey` cookie 可能会过期；reset-time 查询失败时请更新。
- 本工具会发送真实 Claude 请求，请自行确认符合你的账号条款和使用场景。

## 授权

请参考原始项目授权和本 fork 的 repository 设置。
