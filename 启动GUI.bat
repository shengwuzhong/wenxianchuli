@echo off
cd /d %~dp0
rem 桌面工作台用 Python 3.11(pypdfium2/Pillow 装在那里); PATH 里没有 pythonw, 直接用 pyw 启动器
start "" pyw -3.11 gui.py
