#!/usr/bin/env sh
cd "$(dirname "$0")" || exit 1
# 依赖(pypdfium2/Pillow)装在 Python 3.11; 缺包的解释器会让每个任务 0 秒失败, 故优先验证后使用
if command -v py >/dev/null 2>&1 && py -3.11 -c "import pypdfium2, PIL" >/dev/null 2>&1; then
    exec py -3.11 webapp.py
fi
exec python3 webapp.py
