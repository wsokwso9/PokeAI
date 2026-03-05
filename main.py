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
