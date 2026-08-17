# -*- coding: utf-8 -*-
from __future__ import annotations

import cross_group_batch as cgb
from cross_group_batch import RATE_BUCKET_SEC, RateBucket


def test_record_rate_buckets_same_window(monkeypatch):
    monkeypatch.setattr(cgb, "_now", lambda: 1000.0)
    cgb._record_rate("success")
    cgb._record_rate("success")
    cgb._record_rate("failed")
    cgb._record_rate("rate_limited")

    series = cgb._state.rate_series
    assert len(series) == 1
    bucket = series[0]
    expected_ts = int(1000.0 // RATE_BUCKET_SEC) * RATE_BUCKET_SEC
    assert bucket.timestamp == expected_ts
    assert bucket.success == 2
    assert bucket.failed == 1
    assert bucket.rate_limited == 1
    assert bucket.total == 4
    d = bucket.to_dict()
    assert d["total"] == 4
    assert d["timestamp"] == expected_ts


def test_record_rate_new_bucket_on_boundary(monkeypatch):
    t = {"v": 1000.0}
    monkeypatch.setattr(cgb, "_now", lambda: t["v"])

    cgb._record_rate("success")
    t["v"] = 1000.0 + RATE_BUCKET_SEC
    cgb._record_rate("failed")

    series = cgb._state.rate_series
    assert len(series) == 2
    assert series[0].success == 1
    assert series[1].failed == 1
    assert series[1].timestamp == series[0].timestamp + RATE_BUCKET_SEC


def test_record_rate_retention_prunes_old(monkeypatch):
    monkeypatch.setattr(cgb, "_now", lambda: 10_000.0)
    old_ts = int((10_000.0 - cgb.RATE_RETENTION_SEC - 10) // RATE_BUCKET_SEC) * RATE_BUCKET_SEC
    cgb._state.rate_series = [RateBucket(timestamp=old_ts, success=9)]
    cgb._record_rate("success")
    assert all(b.timestamp >= 10_000.0 - cgb.RATE_RETENTION_SEC for b in cgb._state.rate_series)
    assert cgb._state.rate_series[-1].success == 1
