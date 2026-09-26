@echo off
rem =============================================
rem  ClearC 一键启动脚本（双击运行）
rem  注意：本文件为 GBK 编码 + CRLF 换行，请勿用 UTF-8 覆盖保存。
rem  1) 自动申请管理员权限（回收站清理 / 跨盘扫描需要）
rem  2) 优先启动已打包的 dist\ClearC.exe
rem  3) 找不到 exe 时退回源码运行（需安装 Python）
rem =============================================
title ClearC 启动器
setlocal
cd /d "%~dp0"

rem ---- 1. 非管理员则自动提权重跑本脚本 ----
net session >nul 2>&1
if errorlevel 1 (
    echo [ClearC] 正在申请管理员权限，请在弹出的窗口中点击“是”...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b 0
)

rem ---- 2. 优先启动打包好的 exe ----
set "EXE=%CD%\dist\ClearC.exe"
if exist "%EXE%" (
    start "" "%EXE%"
    exit /b 0
)

rem ---- 3. 退回源码运行（保留控制台便于查看错误） ----
if not exist "main.py" (
    echo [ClearC] 未找到 dist\ClearC.exe，也未找到 main.py。
    echo [ClearC] 请先运行打包命令生成 exe。
    pause
    exit /b 1
)

where python >nul 2>&1
if not errorlevel 1 (
    echo [ClearC] 未找到 exe，以源码方式启动...
    python main.py
    if errorlevel 1 pause
    exit /b 0
)

where py >nul 2>&1
if not errorlevel 1 (
    echo [ClearC] 未找到 exe，以源码方式启动（py 启动器）...
    py main.py
    if errorlevel 1 pause
    exit /b 0
)

echo [ClearC] 未找到 Python 解释器，请先安装 Python 3.12+。
pause
exit /b 1
