#!/usr/bin/env python3
"""
PokeAI — CLI and helper for PokeMenu launchpad and PokeBro NFT.
Config-driven; optional RPC for on-chain reads. Single-file app.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
APP_NAME = "PokeAI"
VERSION = "1.0.0"
CONFIG_FILENAME = "poke_ai_config.json"
DEFAULT_RPC = "https://eth.llamarpc.com"
PMU_MAX_SETS = 64
PMU_POKEBRO_CAP = 100_000
PMU_MAX_MINT_PER_TX = 24
PBRO_MAX_SUPPLY = 100_000

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
def config_path() -> Path:
    base = os.environ.get("POKEAI_CONFIG_DIR") or os.path.expanduser("~")
    return Path(base) / CONFIG_FILENAME


def load_config() -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(data: dict[str, Any]) -> bool:
    path = config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except OSError:
        return False


def get_config(key: str, default: Any = None) -> Any:
    return load_config().get(key, default)


def set_config(key: str, value: Any) -> None:
    c = load_config()
    c[key] = value
    save_config(c)


# -----------------------------------------------------------------------------
# Formatting
# -----------------------------------------------------------------------------
def fmt_eth(wei: int | str) -> str:
    try:
        w = int(wei)
        return f"{w / 1e18:.6f} ETH"
    except (ValueError, TypeError):
        return str(wei)


def truncate_addr(addr: str, head: int = 6, tail: int = 4) -> str:
    if not addr or len(addr) < head + tail + 2:
        return addr or ""
    if addr.startswith("0x"):
        return f"{addr[: head + 2]}…{addr[-tail:]}"
    return f"{addr[:head]}…{addr[-tail:]}"


# -----------------------------------------------------------------------------
# Optional Web3 (no hard dependency)
# -----------------------------------------------------------------------------
def _try_import_web3() -> Any:
    try:
        from web3 import Web3
        return Web3
    except ImportError:
        return None


def has_web3() -> bool:
    return _try_import_web3() is not None


def connect_rpc(url: str | None = None) -> Any | None:
    url = url or get_config("rpc_url") or DEFAULT_RPC
    w3 = _try_import_web3()
    if w3 is None:
        return None
    try:
        provider = w3.HTTPProvider(url)
        conn = w3(provider)
        if conn.is_connected():
            return conn
    except Exception:
        pass
    return None


