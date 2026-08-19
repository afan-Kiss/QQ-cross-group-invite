# picker_live_builders.json provenance

Status: SYNTHETIC GOLDEN

REAL CAPTURE FIXTURE PROVENANCE NOT VERIFIED

This file documents tests/fixtures/picker_live_builders.json.
The current golden hex was generated from in-repo live builders
(capture_utils.build_88d_111, build_11ec_1, build_fe7_group_list)
using placeholder group ids. Matching builder output to this JSON is
a round-trip of the builder, not independent proof that a real NapCat
SEND/RECV window contained these bytes.

No original success capture filename, seq, or SEND/RECV pair is checked
into this repository for these fixtures. Do not treat the JSON as a
sanitized extract of a verified live packet.

## Shared placeholders

- placeholder_target_group: 1111111111
- placeholder_source_group: 2222222222
- sanitizer: tests/fixture_sanitizer.py
  - live u_ tokens would be replaced with same-length u_REDACT...
  - group ids must be rebuilt via builders, not in-place varint patches
  - cursor placeholder is sequential 00..23 (36 bytes), not a live field15

## Fixtures

### 88d_111_pb_hex

- capture file: NOT PRESENT (synthetic)
- seq: unknown
- cmd: OidbSvcTrpcTcp.0x88d_111
- SEND/RECV: synthetic SEND
- original length: unknown; golden send_len = 48
- dynamic fields replaced with placeholders:
  - nested target group -> 1111111111
  - outer body type 537099973 kept as builder constant
- bytes kept as builder constants:
  - top field1=0x88d, field2=111, field12=0
  - nested flags blob 88d_111_flags_hex

### 11ec_pb_hex

- capture file: NOT PRESENT (synthetic)
- seq: unknown
- cmd: OidbSvcTrpcTcp.0x11ec_1
- SEND/RECV: synthetic SEND
- original length: unknown; golden send_len = 266
- dynamic fields:
  - inner group id -> 1111111111
- static blobs copied from builder constants:
  - XML msg template (11ec_msg_template_hex)
  - style blob (11ec_style_blob_hex)
- no live u_ token is present

### fe7_first_page_pb_hex

- capture file: NOT PRESENT (synthetic)
- seq: unknown
- cmd: OidbSvcTrpcTcp.0xfe7_4
- SEND/RECV: synthetic SEND (first page, no field15)
- original length: unknown; golden send_len = 96
- dynamic fields:
  - source group -> 2222222222
- static:
  - member field mask blob
  - body field2=5, field3=2

### fe7_next_page_pb_hex / fe7_page_cursor_hex / fe7_recv_with_cursor_hex

- capture file: NOT PRESENT (synthetic)
- seq: unknown
- cmd: OidbSvcTrpcTcp.0xfe7_4
- SEND/RECV: NOT a verified live SEND/RECV pair
- cursor bytes: sequential 0x00..0x23 constructed for tests
- original length: unknown; next-page send_len = 134
- these fixtures prove builder field15 encoding/decoding, not a real
  picker pagination window

Field15 live cursor rule in runtime code remains: only the previous
page's live RECV body.field15. This JSON cursor is not that evidence.

## How to promote a fixture from a real capture

1. Keep the original capture file offline / uncommitted if it has tokens.
2. Record: filename, seq, cmd, direction SEND or RECV, original length.
3. Rebuild the packet with placeholder group ids via the builders.
4. Run redact_u_tokens on any remaining u_ blobs.
5. Fill this provenance with the real seq/cmd/direction/length.
6. Only then remove the SYNTHETIC GOLDEN / NOT VERIFIED labels.

Until that happens, tests against this JSON are synthetic golden tests.
