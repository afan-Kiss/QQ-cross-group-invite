# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from tests.fixture_sanitizer import (
    PLACEHOLDER_SOURCE_GROUP,
    PLACEHOLDER_TARGET_GROUP,
    redact_u_tokens,
    synthetic_cursor_placeholder,
)

ROOT = Path(__file__).resolve().parent
PROVENANCE = ROOT / "fixtures" / "picker_live_builders.PROVENANCE.md"
FIXTURE = ROOT / "fixtures" / "picker_live_builders.json"


def test_provenance_file_marks_synthetic_not_verified():
    text = PROVENANCE.read_text(encoding="utf-8")
    assert "REAL CAPTURE FIXTURE PROVENANCE NOT VERIFIED" in text
    assert "SYNTHETIC GOLDEN" in text
    assert "seq: unknown" in text
    assert FIXTURE.exists()


def test_sanitizer_redacts_u_tokens_without_changing_length():
    raw = b"pre u_LIVESECRETTOKENAAAAAAA post"
    out = redact_u_tokens(raw)
    assert len(out) == len(raw)
    assert b"u_LIVESECRETTOKENAAAAAAA" not in out
    assert b"u_REDACT" in out


def test_fixture_uses_placeholder_groups_and_synthetic_cursor():
    import json

    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert fx["placeholder_target_group"] == PLACEHOLDER_TARGET_GROUP
    assert fx["placeholder_source_group"] == PLACEHOLDER_SOURCE_GROUP
    assert bytes.fromhex(fx["fe7_page_cursor_hex"]) == synthetic_cursor_placeholder()
    blob = bytes.fromhex(fx["88d_111_pb_hex"] + fx["11ec_pb_hex"] + fx["fe7_first_page_pb_hex"])
    assert b"u_" not in blob
