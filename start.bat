@echo off
cd /d %~dp0
rem 依赖(pypdfium2/Pillow)装在 Python 3.11; PATH 里的 python 可能是 Microsoft Store 空壳(退出码 9009)
rem 或另一版本解释器(缺包 -> 每个任务 0 秒失败), 故优先用 py 启动器定位 3.11
py -3.11 -c "import pypdfium2, PIL" >nul 2>&1
if not errorlevel 1 (
    py -3.11 webapp.py
) else (
    echo [warn] py -3.11 不可用或缺少依赖, 回退到 PATH 中的 python
    python webapp.py
)
if errorlevel 1 pause
