# -*- coding: utf-8 -*-
"""Sanitize historical picker packets into non-secret fixtures.

Does not invent provenance. If no real capture is supplied, callers must label
the output as synthetic golden rather than verified live evidence.
"""
from __future__ import annotations

import re

PLACEHOLDER_TARGET_GROUP = 1111111111
PLACEHOLDER_SOURCE_GROUP = 2222222222
SYNTHETIC_CURSOR = bytes(range(36))
U_TOKEN_RE = re.compile(rb"u_[A-Za-z0-9_-]{16,}")
REDACTED_TOKEN_PREFIX = b"u_REDACT"


def redact_u_tokens(data: bytes) -> bytes:
    """Replace live u_ tokens with a same-length redacted placeholder."""
    out = data
    for match in reversed(list(U_TOKEN_RE.finditer(data))):
        raw = match.group()
        redacted = (REDACTED_TOKEN_PREFIX + b"A" * max(0, len(raw) - len(REDACTED_TOKEN_PREFIX)))[
            : len(raw)
        ]
        out = out[: match.start()] + redacted + out[match.end() :]
    return out


def replace_varint_group_ids(hex_data: str, *, source: int, target: int) -> str:
    """Best-effort decimal string rewrite is unsafe; keep hex and document IDs.

    Fixture generation should rebuild packets with capture_utils builders using
    PLACEHOLDER_* group ids, then copy only static blobs (flags/xml/style).
    """
    del hex_data, source, target
    raise NotImplementedError(
        "Do not byte-patch group ids in place. Rebuild with builders and "
        "placeholder group ids so SEND/RECV length and field layout stay honest."
    )


def synthetic_cursor_placeholder() -> bytes:
    return SYNTHETIC_CURSOR
