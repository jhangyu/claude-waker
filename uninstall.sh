#!/bin/bash

# Claude Waker 卸載腳本
# 支持 Linux 和 macOS

set -e

echo "======================================"
echo "   Claude Waker 卸載腳本"
echo "======================================"
echo ""

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 檢查是否存在 Claude Waker 任務
echo "檢查 crontab 任務..."
CLAUDE_WAKER_PATTERN="Claude Waker|claude-waker.*waker\\.py|\\.venv/bin/python3 ./waker\\.py"

if ! crontab -l 2>/dev/null | grep -q -E "$CLAUDE_WAKER_PATTERN"; then
    echo -e "${YELLOW}⚠️  未找到 Claude Waker 的 crontab 任務${NC}"
    echo "可能已經卸載或從未安裝"
    exit 0
fi

# 顯示當前任務
echo ""
echo "找到以下 Claude Waker 任務:"
echo "----------------------------------------"
crontab -l 2>/dev/null | grep -E -B 1 -A 1 "$CLAUDE_WAKER_PATTERN" || true
echo "----------------------------------------"
echo ""

# 確認卸載
read -p "確認刪除這些任務嗎? (y/n) " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "已取消卸載"
    exit 0
fi

# 刪除任務
echo ""
echo "正在刪除 crontab 任務..."

TEMP_CRON=$(mktemp)
crontab -l 2>/dev/null | python3 -c '
import re
import sys

pattern = re.compile(r"Claude Waker|claude-waker.*waker\.py|\.venv/bin/python3 ./waker\.py")
lines = sys.stdin.read().splitlines()
filtered = []
skip_next = False

for line in lines:
    if skip_next:
        skip_next = False
        if pattern.search(line):
            continue
    if "Claude Waker" in line:
        skip_next = True
        continue
    if pattern.search(line):
        continue
    filtered.append(line)

if filtered:
    sys.stdout.write("\n".join(filtered).rstrip() + "\n")
' > "$TEMP_CRON"

crontab "$TEMP_CRON"

rm -f "$TEMP_CRON"

# 驗證刪除
if crontab -l 2>/dev/null | grep -q -E "$CLAUDE_WAKER_PATTERN"; then
    echo -e "${RED}❌ 刪除失敗，請手動檢查 crontab${NC}"
    echo "執行: crontab -e"
    exit 1
else
    echo -e "${GREEN}✓${NC} Crontab 任務已刪除"
fi

echo ""
echo "======================================"
echo -e "${GREEN}✓ 卸載完成！${NC}"
echo "======================================"
echo ""
echo "提示:"
echo "  - 專案文件和配置仍然保留"
echo "  - 如需完全刪除，請手動刪除專案目錄"
echo "  - 如需重新安裝，請執行: ./setup.sh"
echo ""
