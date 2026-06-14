#!/bin/bash

# Claude Waker 安裝腳本
# 支持 Linux 和 macOS

set -e

echo "======================================"
echo "   Claude Waker 安裝腳本"
echo "======================================"
echo ""

# 獲取腳本所在目錄
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 檢查操作系統
OS="$(uname -s)"
case "$OS" in
    Linux*)     OS_TYPE=Linux;;
    Darwin*)    OS_TYPE=Mac;;
    *)          echo -e "${RED}❌ 不支持的操作系統: $OS${NC}"; exit 1;;
esac

echo -e "${GREEN}✓${NC} 檢測到操作系統: $OS_TYPE"

# 檢查 uv 是否安裝
echo ""
echo "檢查 uv 安裝..."
if ! command -v uv &> /dev/null; then
    echo -e "${RED}❌ 未找到 uv 命令${NC}"
    echo ""
    echo "請先安裝 uv:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo ""
    echo "或訪問: https://github.com/astral-sh/uv"
    exit 1
fi
echo -e "${GREEN}✓${NC} uv 已安裝: $(uv --version)"

# 檢查 Python3
echo ""
echo "檢查 Python 安裝..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ 未找到 python3 命令${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Python 已安裝: $(python3 --version)"

# 檢查配置文件
echo ""
echo "檢查配置文件..."
if [ ! -f "config.yaml" ]; then
    echo -e "${YELLOW}⚠️  config.yaml 不存在${NC}"
    if [ -f "config.yaml.example" ]; then
        echo "正在從 config.yaml.example 創建 config.yaml..."
        cp config.yaml.example config.yaml
        echo -e "${GREEN}✓${NC} 已創建 config.yaml"
        echo ""
        echo -e "${YELLOW}請編輯 config.yaml 文件，填入你的 OAuth Token 和喚醒時間${NC}"
        echo "編輯完成後，請重新運行此腳本"
        exit 0
    else
        echo -e "${RED}❌ config.yaml.example 也不存在${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}✓${NC} config.yaml 存在"

# 創建虛擬環境
echo ""
echo "創建虛擬環境..."
if [ -d ".venv" ]; then
    echo -e "${YELLOW}⚠️  虛擬環境已存在，跳過創建${NC}"
else
    uv venv
    echo -e "${GREEN}✓${NC} 虛擬環境創建完成"
fi

# 安裝依賴
echo ""
echo "安裝依賴..."
uv pip install -r requirements.txt
echo -e "${GREEN}✓${NC} 依賴安裝完成"

# 將 Claude CLI 接到專案虛擬環境，讓 cron 的乾淨 PATH 也找得到 claude。
echo ""
echo "檢查 Claude CLI..."
CLAUDE_BIN="$(command -v claude || command -v claude-bun || true)"
if [ -z "$CLAUDE_BIN" ]; then
    echo -e "${RED}❌ 未找到 claude 或 claude-bun 命令${NC}"
    echo ""
    echo "請先安裝並登入 Claude Code CLI，確認以下命令可在終端機執行:"
    echo "  claude --version"
    exit 1
fi

CLAUDE_LINK=".venv/bin/claude"
if [ -e "$CLAUDE_LINK" ] || [ -L "$CLAUDE_LINK" ]; then
    rm -f "$CLAUDE_LINK"
fi
ln -s "$CLAUDE_BIN" "$CLAUDE_LINK"
echo -e "${GREEN}✓${NC} Claude CLI 已連結: $CLAUDE_LINK -> $CLAUDE_BIN"

# 驗證配置
echo ""
echo "驗證配置..."
PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python3"

# 創建臨時驗證腳本
cat > /tmp/validate_config.py << 'EOF'
import sys
import yaml
from pathlib import Path

config_file = Path("config.yaml")
if not config_file.exists():
    print("❌ 配置文件不存在")
    sys.exit(1)

try:
    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # 檢查必需字段
    if not config.get('accounts'):
        print("❌ 配置文件缺少 accounts 字段")
        sys.exit(1)

    if not config.get('wake_hours'):
        print("❌ 配置文件缺少 wake_hours 字段")
        sys.exit(1)

    # 檢查賬號
    valid_accounts = 0
    session_key_accounts = 0
    for account in config['accounts']:
        token = account.get('token', '')
        if token and token not in ['your-oauth-token-here-1', 'your-oauth-token-here-2']:
            valid_accounts += 1
        if account.get('session_key'):
            session_key_accounts += 1

    if valid_accounts == 0:
        print("❌ 沒有配置有效的 OAuth Token")
        print("請在 config.yaml 中填入真實的 token")
        sys.exit(1)

    print(f"✓ 配置驗證通過，找到 {valid_accounts} 個有效賬號")
    if session_key_accounts == 0:
        print("⚠️  未配置 session_key，將無法查詢 five_hour_resets_at，排程會直接執行喚醒")
    else:
        print(f"✓ 找到 {session_key_accounts} 個可查詢 reset time 的 session_key")

    # 解析喚醒時間
    wake_hours = [int(h.strip()) for h in config['wake_hours'].split(',')]
    if not wake_hours:
        print("❌ wake_hours 格式錯誤（至少需要1個小時數）")
        sys.exit(1)

    for hour in wake_hours:
        if hour < 0 or hour > 23:
            print(f"❌ 無效的小時數: {hour}（應為0-23）")
            sys.exit(1)

    print(f"✓ 喚醒時間: {', '.join([f'{h}:05' for h in wake_hours])}")

    # 輸出喚醒時間供 shell 腳本使用
    print(f"WAKE_HOURS={config['wake_hours']}")

except Exception as e:
    print(f"❌ 配置驗證失敗: {e}")
    sys.exit(1)
EOF

# 運行驗證
VALIDATION_OUTPUT=$("$PYTHON_BIN" /tmp/validate_config.py)
VALIDATION_EXIT_CODE=$?
rm /tmp/validate_config.py

echo "$VALIDATION_OUTPUT" | grep -v "^WAKE_HOURS="

if [ $VALIDATION_EXIT_CODE -ne 0 ]; then
    echo ""
    echo -e "${RED}配置驗證失敗，請檢查 config.yaml${NC}"
    exit 1
fi

# 提取喚醒時間
WAKE_HOURS=$(echo "$VALIDATION_OUTPUT" | grep "^WAKE_HOURS=" | cut -d'=' -f2)
echo -e "${GREEN}✓${NC} 配置驗證通過"

# 設置 crontab
echo ""
echo "配置 crontab 任務..."
printf -v CRON_PROJECT_DIR "%q" "$SCRIPT_DIR"
CRON_COMMAND="5 $WAKE_HOURS * * * cd $CRON_PROJECT_DIR && PATH=.venv/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin ./.venv/bin/python3 ./waker.py >> ./waker.cron.log 2>&1"
CRON_COMMENT="# Claude Waker - Auto wake Claude accounts"

# 檢查是否已存在
if crontab -l 2>/dev/null | grep -q -E "Claude Waker|claude-waker.*waker\\.py|\\.venv/bin/python3 ./waker\\.py"; then
    echo -e "${YELLOW}⚠️  檢測到已存在的 Claude Waker 任務${NC}"
    read -p "是否替換現有任務? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # 刪除舊任務
        crontab -l 2>/dev/null \
            | grep -v "Claude Waker" \
            | grep -v -E "claude-waker.*waker\\.py|\\.venv/bin/python3 ./waker\\.py" \
            | crontab -
        echo "已刪除舊任務"
    else
        echo "保留現有任務，跳過"
        exit 0
    fi
fi

# 添加新任務
(crontab -l 2>/dev/null; echo ""; echo "$CRON_COMMENT"; echo "$CRON_COMMAND") | crontab -
echo -e "${GREEN}✓${NC} Crontab 任務已添加"

echo ""
echo "======================================"
echo -e "${GREEN}✓ 安裝完成！${NC}"
echo "======================================"
echo ""
echo "Crontab 任務:"
echo "  $CRON_COMMAND"
echo ""
echo "程式日誌: ./waker.log"
echo "Cron 輸出: ./waker.cron.log"
echo ""
echo "提示:"
echo "  - 查看 crontab: crontab -l"
echo "  - 編輯配置: vim config.yaml"
echo "  - 手動測試: ./.venv/bin/python3 ./waker.py"
echo "  - 卸載任務: ./uninstall.sh"
echo ""
