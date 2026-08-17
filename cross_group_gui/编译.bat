@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo 正在编译跨群邀请助手...
set GOPROXY=https://goproxy.cn,direct
python _gen_main.py
go build -mod=mod -ldflags="-H windowsgui" -o cross_group_gui.exe .
if errorlevel 1 (
    echo 编译失败。
    pause
    exit /b 1
)
copy /Y manifest.xml cross_group_gui.exe.manifest >nul
echo 编译成功。
pause
