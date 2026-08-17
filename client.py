# -*- coding: utf-8 -*-
"""Minimal MyQQ HTTP API client (port/token must match plugin UI)."""
from __future__ import annotations

import sys

from myqq_api import call


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python client.py <Api_Name> [c1] [c2] [c3] ...")
        print("example: python client.py Api_GetOnlineQQlist")
        print("example: python client.py Api_AdminInviteGroup 我的QQ 群号 好友QQ")
        raise SystemExit(1)
    print(call(sys.argv[1], *sys.argv[2:]))
