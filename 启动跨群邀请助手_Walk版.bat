@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo 正在启动后台...
start "cross_group_service" /min python cross_group_service.py
timeout /t 2 /nobreak >nul

echo 正在打开跨群邀请助手...
if not exist "cross_group_gui\cross_group_gui.exe.manifest" (
    copy /Y "cross_group_gui\manifest.xml" "cross_group_gui\cross_group_gui.exe.manifest" >nul
)
if exist "cross_group_gui\cross_group_gui.exe" (
    start "" "cross_group_gui\cross_group_gui.exe"
) else (
    echo 找不到程序，请先双击 cross_group_gui\编译.bat 进行编译。
    pause
)
