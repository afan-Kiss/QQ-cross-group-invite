# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from pathlib import Path


def test_cleanup_old_logs_by_day(tmp_path: Path):
    from service_logger import cleanup_old_logs

    now = time.time()
    old = tmp_path / "service.log.1"
    mid = tmp_path / "service.log.2"
    fresh = tmp_path / "service.log"
    other = tmp_path / "notes.txt"
    app_old = tmp_path / "app.log.3"
    for p, age_days in ((old, 10), (mid, 3), (fresh, 0), (other, 20), (app_old, 10)):
        p.write_text("x", encoding="utf-8")
        ts = now - age_days * 86400
        import os

        os.utime(p, (ts, ts))

    deleted = cleanup_old_logs(tmp_path, retention_days=7, auto_clean=True, now=now)
    assert "service.log.1" in deleted
    assert "app.log.3" in deleted
    assert mid.exists()
    assert fresh.exists()
    assert other.exists()  # never delete non-log files
    assert not old.exists()
    assert not app_old.exists()


def test_auto_clean_false_keeps_all(tmp_path: Path):
    from service_logger import cleanup_old_logs
    import os

    now = time.time()
    old = tmp_path / "service.log.1"
    old.write_text("x", encoding="utf-8")
    os.utime(old, (now - 20 * 86400, now - 20 * 86400))
    deleted = cleanup_old_logs(tmp_path, retention_days=7, auto_clean=False, now=now)
    assert deleted == []
    assert old.exists()
