@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ����������Ⱥ�������֣���ҳ�棩...
start "cross_group_service" python cross_group_service.py
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:17888/"
