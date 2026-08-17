@echo off
chcp 65001 >nul
cd /d "%~dp0"
python pull_cross_group.py
if errorlevel 1 pause
