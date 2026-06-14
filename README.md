# Claude Waker ⏰

自动唤醒 Claude 账号，优化 5 小时限额使用窗口 | Claude Scheduler | Claude Wakeup Tool | Claude Auto Timer

> **Automatic Claude account scheduler for optimizing 5-hour usage quota windows**
>
> [English Documentation](README.en.md) | 中文文档

**关键词**: Claude定时唤醒 | Claude调度器 | Claude自动化 | Claude Pro优化 | Claude Max工具 | claude scheduler | claude wakeup | claude timer | claude automation | claude quota optimizer

## 📖 项目背景

### 问题

Claude Pro/Max 账号有每 5 小时的使用限额，但这个限额**不是固定时间重置**，而是从**第一次使用开始计时**。

这可能导致无法最大化利用额度。例如：

- 工作时间：9:30-12:00, 13:30-18:30
- 如果 10:00 第一次使用，很快耗尽额度
- 下午 3:00 之前都无法继续使用（浪费了下午的工作时间）

### 解决方案

通过在**固定时间点**自动发送消息来"唤醒" Claude，主动触发计时窗口，从而优化使用时间：

- 早上 7:05 自动唤醒 → 12:00 重置
- 中午 12:05 自动唤醒 → 17:00 重置
- 下午 17:05 自动唤醒 → 22:00 重置

**为什么是 05 分？** Claude 的 5 小时限额是按**整点计时**的（如 7:00-12:00），在 7:05 发送消息不会影响这 5 分钟，因为计时已经从 7:00 开始了。使用 05 分可以确保 cron 任务稳定触发。

这样就能在工作时间内最大化利用额度！

## ✨ 特性

**🎯 核心优势**：
- 🚀 **同时管理多个 Claude 账号** - 网上大多数工具只支持单账号，本工具可以一次性唤醒所有账号
- ⚡ **极致轻量** - 单个 Python 文件 + 最小依赖，无复杂配置，资源占用极低
- 🎨 **简单易用** - 一键安装，自动配置，无需编程知识

**完整功能**：
- ✅ 支持多个 Claude 账号同时唤醒
- ✅ 自定义唤醒时间（可配置多个时间点）
- ✅ 自动配置 crontab 定时任务（claude scheduler）
- ✅ 最小化 API 请求（短 prompt + 快速超时）
- ✅ 详细日志记录
- ✅ 错误处理（单个账号失败不影响其他账号）
- ✅ 支持 Linux 和 macOS

## 🚀 快速开始

### 部署建议

**推荐部署环境**：
- 🖥️ **常开机器**：家用 NAS、云服务器、个人电脑等 24 小时运行的设备
- 💻 **操作系统**：macOS 或 Linux（推荐 Ubuntu/Debian）
- ⚠️ **注意**：如果部署在个人电脑上，需要保持电脑开机以确保定时任务正常运行

**为什么需要常开机器？**
因为程序通过 crontab 定时任务运行，机器关机时任务无法执行。建议部署在服务器、NAS 或树莓派等常开设备上。

### 前置要求

1. **Python 3.8+**
2. **uv** (快速的 Python 包管理器)
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
3. **Claude CLI** (用于获取 OAuth Token)
   ```bash
   npm install -g @anthropic-ai/claude-code
   ```

### 安装步骤

#### 1. 获取 OAuth Token

为每个 Claude 账号获取 OAuth Token：

```bash
# 获取第一个账号的 token
claude setup-token
```

这会打开浏览器进行认证，完成后会在终端输出 token，类似：

```
Your OAuth token: sk-ant-oat03-...（很长的字符串）
```

**复制并保存这个 token**。

如果有多个账号，退出当前账号后重复此步骤：
```bash
# 在浏览器中登出 Claude
# 再次运行获取另一个账号的 token
claude setup-token
```

#### 2. 克隆并配置项目

```bash
# 克隆或下载项目
cd claude_waker

# 运行安装脚本
./setup.sh
```

首次运行 `setup.sh` 会自动创建 `config.yaml`，提示你编辑配置。

#### 3. 编辑配置文件

编辑 `config.yaml`：

```yaml
# Claude 账号列表
accounts:
  - name: "主账号"
    token: "sk-ant-oat03-...（第一个账号的token）"
    session_key: "sk-ant-sid01-...（claude.ai 的 sessionKey cookie）"
  - name: "备用账号"
    token: "sk-ant-oat03-...（第二个账号的token）"
    session_key: "sk-ant-sid01-...（claude.ai 的 sessionKey cookie）"

# 唤醒时间（小时，0-23）
# 实际触发时间为每小时的 05 分
wake_hours: "7,12,17"  # 在 7:05, 12:05, 17:05 唤醒

# 喚醒訊息
# 程式會另外使用 /usage 查詢用量；這裡保留一個低成本的真實模型請求來喚醒
wake_prompt: "In one short sentence, confirm this scheduled Claude Code session is active and ready for use."

# 單次喚醒請求的最高預算
wake_max_budget_usd: 0.02

# 喚醒請求使用的模型
# 可填 Claude Code 支援的模型 alias 或完整模型名稱，例如 "haiku"
wake_model: "haiku"
```

#### 4. 完成安装

编辑完配置后，再次运行安装脚本：

```bash
./setup.sh
```

安装脚本会：
- ✓ 创建虚拟环境（使用 uv）
- ✓ 安装依赖
- ✓ 将 Claude CLI 链接到 `.venv/bin/claude`，让 cron 能在干净环境中找到它
- ✓ 验证配置和 token
- ✓ 自动配置 crontab 定时任务

## 📝 使用说明

### 自动运行

安装完成后，程序会自动在指定时间运行，无需手动操作。

### 手动测试

测试程序是否正常工作：

```bash
./.venv/bin/python3 ./waker.py
```

### 查看日志

```bash
tail -f waker.log
```

日志示例：
```
[2025-12-03 07:05:01] ============================================================
[2025-12-03 07:05:01] Claude Waker 开始运行
[2025-12-03 07:05:01] ✓ 检测到操作系统: Mac
[2025-12-03 07:05:01] 开始唤醒任务，共 2 个账号
[2025-12-03 07:05:01] 正在唤醒账号: 主账号
[2025-12-03 07:05:03] ✅ 主账号 - 唤醒成功
[2025-12-03 07:05:05] 正在唤醒账号: 备用账号
[2025-12-03 07:05:07] ✅ 备用账号 - 唤醒成功
[2025-12-03 07:05:07] ------------------------------------------------------------
[2025-12-03 07:05:07] 唤醒任务完成: 成功 2 个，失败 0 个
[2025-12-03 07:05:07] ============================================================
```

### 查看 Crontab 任务

```bash
crontab -l | grep "Claude Waker"
```

### 修改唤醒时间

1. 编辑 `config.yaml` 中的 `wake_hours`
2. 重新运行 `./setup.sh` 更新 crontab

### 卸载

运行卸载脚本：

```bash
./uninstall.sh
```

## ⚙️ 配置说明

### config.yaml

| 字段 | 说明 | 格式 |
|------|------|------|
| `accounts` | Claude 账号列表 | 数组，每个账号包含 `name`、`token`，建议同时配置 `session_key` |
| `wake_hours` | 唤醒时间 | 字符串，逗号分隔的小时数（0-23） |
| `wake_prompt` | 唤醒時發送的訊息 | 字符串 |
| `wake_max_budget_usd` | 單次喚醒請求的最高預算 | 數字，預設 `0.02` |
| `wake_model` | 喚醒請求使用的模型 | 字符串，例如 `haiku`；留空則使用 Claude Code 預設模型 |

### 唤醒时间示例

```yaml
# 早中晚各一次
wake_hours: "7,12,17"

# 上班前、午休后、下班前
wake_hours: "9,14,18"

# 仅工作日早晨（需要手动修改 crontab 添加星期限制）
wake_hours: "9"
```

**注意**: 实际触发时间为每小时的 **05 分**（如 7:05, 12:05）。这不会浪费 5 分钟配额，因为 Claude 从整点开始计时。

## 🔧 高级用法

### 限制工作日运行

手动编辑 crontab，添加工作日限制：

```bash
crontab -e
```

修改 Claude Waker 任务为：

```cron
# Claude Waker - Auto wake Claude accounts (仅工作日)
5 7,12,17 * * 1-5 cd /path/to/claude_waker && PATH=.venv/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin ./.venv/bin/python3 ./waker.py >> ./waker.cron.log 2>&1
```

`1-5` 表示周一到周五。

### 自定义日志位置

修改 `waker.py` 中的 `LOG_FILE` 变量：

```python
LOG_FILE = Path("/your/custom/path/waker.log")
```

### 调整超时时间

修改 `waker.py` 中的超时设置：

```python
async with asyncio.timeout(60):  # 修改为你想要的秒数
```

## ❓ 常见问题

### Q: 如何确认 token 是否有效？

运行 `./setup.sh`，脚本会自动验证 token。

或手动测试：
```bash
./.venv/bin/python3 ./waker.py
```

### Q: 程序没有按时运行？

1. 检查 crontab 是否正确：`crontab -l | grep "Claude Waker"`
2. 确认系统时间正确：`date`
3. 检查日志文件：`tail -f waker.log`
4. 确认 cron 服务运行正常（macOS 需要授权终端访问）

### Q: Token 过期了怎么办？

重新获取 token 并更新 `config.yaml`：

```bash
claude setup-token
# 复制新 token 到 config.yaml
```

如果 `session_key` 过期，也请重新从浏览器的 claude.ai cookie 取得并更新 `config.yaml`。`session_key` 只用于查询 `five_hour_resets_at`，失效时程序会直接执行喚醒。

### Q: 如何添加更多账号？

在 `config.yaml` 中添加新账号：

```yaml
accounts:
  - name: "账号1"
    token: "token1"
    session_key: "sessionKey1"
  - name: "账号2"
    token: "token2"
    session_key: "sessionKey2"
  - name: "账号3"  # 新增
    token: "token3"
    session_key: "sessionKey3"
```

无需重新运行 `setup.sh`。

### Q: 可以配置很多个唤醒时间吗？

可以。修改 `wake_hours` 即可，如：

```yaml
wake_hours: "6,9,12,15,18,21"  # 6 个时间点
```

### Q: 日志文件太大怎么办？

使用 logrotate 或手动清理：

```bash
# 手动清空日志
> waker.log

# 或保留最后 100 行
tail -100 waker.log > waker.log.tmp && mv waker.log.tmp waker.log
```

### Q: macOS 上 cron 没有权限运行？

macOS 需要授权终端访问：

1. 系统偏好设置 → 安全性与隐私 → 隐私 → 完全磁盘访问权限
2. 添加 `/usr/sbin/cron` 或你使用的终端应用

## 📄 项目结构

```
claude_waker/
├── waker.py              # 主程序
├── setup.sh              # 安装脚本
├── config.yaml           # 配置文件（需手动创建）
├── config.yaml.example   # 配置示例
├── requirements.txt      # Python 依赖
├── .gitignore
├── .venv/               # 虚拟环境（setup.sh 自动创建）
├── waker.log            # 日志文件（自动生成）
└── README.md            # 本文件
```

## 🔗 相关链接

- [Claude Code 文档](https://docs.claude.com/en/docs/claude-code)
- [Claude Agent SDK](https://docs.claude.com/en/api/agent-sdk/overview)
- [uv - Python 包管理器](https://github.com/astral-sh/uv)
- [参考项目 - claude-oauth-demo](https://github.com/anthropics/claude-agent-sdk-python)

## 📜 许可证

MIT

## 🙏 致谢

本项目参考了 [claude-oauth-demo](../claude-oauth-demo) 的 OAuth 认证实现。

---

**祝你使用愉快！充分利用 Claude Pro/Max 的每一分钟额度！** 🚀
