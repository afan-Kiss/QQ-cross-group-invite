# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest


def test_start_batch_rejects_invalid_batch_size():
    import cross_group_batch as batch

    with pytest.raises(ValueError, match="1-1000"):
        batch.start_batch(
            target_group_id=1, source_group_id=2, count=1, interval_ms=200, batch_size=0
        )
    with pytest.raises(ValueError, match="1-1000"):
        batch.start_batch(
            target_group_id=1, source_group_id=2, count=1, interval_ms=200, batch_size=1001
        )
    with pytest.raises(ValueError):
        batch.start_batch(
            target_group_id=1, source_group_id=2, count=1, interval_ms=50, batch_size=1
        )
