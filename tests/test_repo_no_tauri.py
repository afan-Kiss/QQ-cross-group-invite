# -*- coding: utf-8 -*-
"""Guard against Tauri / Rust release chain resurrection."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAURI_BAT = "\u542f\u52a8\u8de8\u7fa4\u9080\u8bf7\u52a9\u624b_Tauri.bat"


def test_cross_group_tauri_absent():
    assert not (ROOT / "cross_group_tauri").exists()
    assert not (ROOT / TAURI_BAT).exists()


def test_root_build_release_is_wails_wrapper():
    text = (ROOT / "build_release.ps1").read_text(encoding="utf-8", errors="replace").lower()
    assert "cross_group_wails" in text
    for banned in ("src-tauri", "cargo", "rustc", "npm run tauri"):
        assert banned not in text, banned


def test_root_build_sidecar_no_rust():
    text = (ROOT / "build_sidecar.ps1").read_text(encoding="utf-8", errors="replace").lower()
    for banned in ("src-tauri", "cargo", "rustc", "targettriple", "tauri"):
        assert banned not in text, banned


def test_gitignore_no_tauri_entries():
    gi = ROOT / ".gitignore"
    if not gi.exists():
        return
    text = gi.read_text(encoding="utf-8", errors="replace")
    assert "cross_group_tauri" not in text


def test_wails_release_smoke_uses_temp_port():
    text = (ROOT / "cross_group_wails" / "build_release.ps1").read_text(
        encoding="utf-8", errors="replace"
    )
    assert "TcpListener" in text
    assert "--port" in text
    assert "taskkill /IM" not in text.lower()
    assert "taskkill.exe /IM" not in text.lower()
    assert 'Invoke-RestMethod -Uri "http://127.0.0.1:17888/health"' not in text
    assert 'Uri "http://127.0.0.1:17888/shutdown"' not in text
    assert "smoke-test" not in text
    assert "taskkill.exe /PID" in text or "taskkill /PID" in text.lower()
    assert "VERSION file missing" in text
