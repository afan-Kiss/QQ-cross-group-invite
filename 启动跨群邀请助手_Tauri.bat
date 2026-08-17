@echo off
chcp 65001 >nul
cd /d "%~dp0cross_group_tauri"
echo [����ģʽ] ���� QQ ��Ⱥ���빤�� (Tauri)
echo ע��: ��ʽ�û���ʹ�ô����� EXE�����������ű���
npm run tauri dev
