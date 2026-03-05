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


# -----------------------------------------------------------------------------
# PokeMenu / PokeBro ABI snippets (minimal for common reads)
# -----------------------------------------------------------------------------
PMU_GET_CONFIG_ABI = [{"inputs": [], "name": "getFrontendConfig", "outputs": [
    {"name": "nft_", "type": "address"},
    {"name": "nextTokenId_", "type": "uint256"},
    {"name": "setCounter_", "type": "uint256"},
    {"name": "feeBps_", "type": "uint256"},
    {"name": "platformPaused_", "type": "bool"},
    {"name": "deployBlock_", "type": "uint256"},
    {"name": "treasury_", "type": "address"},
    {"name": "vault_", "type": "address"},
    {"name": "launchpadWallet_", "type": "address"},
], "stateMutability": "view", "type": "function"}]

PMU_GET_SET_IDS_ABI = [{"inputs": [], "name": "getSetIds", "outputs": [{"name": "", "type": "uint256[]"}], "stateMutability": "view", "type": "function"}]

PMU_GET_SET_INFO_ABI = [{"inputs": [{"name": "setId", "type": "uint256"}], "name": "getSetInfo", "outputs": [
    {"name": "nameHash", "type": "bytes32"},
    {"name": "maxPerSet", "type": "uint256"},
    {"name": "priceWei", "type": "uint256"},
    {"name": "creator", "type": "address"},
    {"name": "mintedFromSet", "type": "uint256"},
    {"name": "saleOpen", "type": "bool"},
    {"name": "createdAtBlock", "type": "uint256"},
], "stateMutability": "view", "type": "function"}]

PBRO_TOTAL_SUPPLY_ABI = [{"inputs": [], "name": "totalSupply", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}]

PBRO_BALANCE_ABI = [{"inputs": [{"name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}]


def fetch_poke_menu_config(w3: Any, address: str) -> dict[str, Any] | None:
    if not w3 or not address:
        return None
    try:
        contract = w3.eth.contract(address=w3.to_checksum_address(address), abi=PMU_GET_CONFIG_ABI)
        result = contract.functions.getFrontendConfig().call()
        return {
            "nft": result[0],
            "nextTokenId": result[1],
            "setCounter": result[2],
            "feeBps": result[3],
            "platformPaused": result[4],
            "deployBlock": result[5],
            "treasury": result[6],
            "vault": result[7],
            "launchpadWallet": result[8],
        }
    except Exception:
        return None


def fetch_set_ids(w3: Any, pmu_address: str) -> list[int]:
    if not w3 or not pmu_address:
        return []
    try:
        contract = w3.eth.contract(address=w3.to_checksum_address(pmu_address), abi=PMU_GET_SET_IDS_ABI)
        ids = contract.functions.getSetIds().call()
        return [int(x) for x in ids]
    except Exception:
        return []


def fetch_set_info(w3: Any, pmu_address: str, setId: int) -> dict[str, Any] | None:
    if not w3 or not pmu_address:
        return None
    try:
        contract = w3.eth.contract(address=w3.to_checksum_address(pmu_address), abi=PMU_GET_SET_INFO_ABI)
        result = contract.functions.getSetInfo(setId).call()
        return {
            "nameHash": result[0],
            "maxPerSet": result[1],
            "priceWei": result[2],
            "creator": result[3],
            "mintedFromSet": result[4],
            "saleOpen": result[5],
            "createdAtBlock": result[6],
        }
    except Exception:
        return None


def fetch_poke_bro_total_supply(w3: Any, address: str) -> int | None:
    if not w3 or not address:
        return None
    try:
        contract = w3.eth.contract(address=w3.to_checksum_address(address), abi=PBRO_TOTAL_SUPPLY_ABI)
        return contract.functions.totalSupply().call()
    except Exception:
        return None


def fetch_poke_bro_balance(w3: Any, pbro_address: str, account: str) -> int | None:
    if not w3 or not pbro_address or not account:
        return None
    try:
        contract = w3.eth.contract(address=w3.to_checksum_address(pbro_address), abi=PBRO_BALANCE_ABI)
        return contract.functions.balanceOf(w3.to_checksum_address(account)).call()
    except Exception:
        return None


# -----------------------------------------------------------------------------
# CLI: info
# -----------------------------------------------------------------------------
def cmd_info(args: argparse.Namespace) -> int:
    print(f"{APP_NAME} v{VERSION}")
    print(f"Config file: {config_path()}")
    print(f"Web3 available: {has_web3()}")
    pmu = get_config("poke_menu_address")
    pbro = get_config("poke_bro_address")
    rpc = get_config("rpc_url") or DEFAULT_RPC
    print(f"PokeMenu address: {pmu or '(not set)'}")
    print(f"PokeBro address: {pbro or '(not set)'}")
    print(f"RPC URL: {rpc}")
    return 0


# -----------------------------------------------------------------------------
# CLI: config
# -----------------------------------------------------------------------------
def cmd_config(args: argparse.Namespace) -> int:
    if args.get:
        val = get_config(args.get)
        print(val if val is not None else "")
        return 0
    if args.set and args.value is not None:
        set_config(args.set, args.value)
        print(f"Set {args.set} = {args.value}")
        return 0
    # List all
    c = load_config()
    for k, v in sorted(c.items()):
        print(f"{k}: {v}")
    return 0


# -----------------------------------------------------------------------------
# CLI: stats (on-chain if Web3 + addresses)
# -----------------------------------------------------------------------------
def cmd_stats(args: argparse.Namespace) -> int:
    pmu_addr = args.poke_menu or get_config("poke_menu_address")
    pbro_addr = args.poke_bro or get_config("poke_bro_address")
    rpc = args.rpc or get_config("rpc_url") or DEFAULT_RPC
    if not pmu_addr:
        print("PokeMenu address not set. Use --poke-menu or config set poke_menu_address <addr>")
        return 1
    w3 = connect_rpc(rpc)
    if not w3:
        print("Web3 not available or RPC failed. Install web3 and set a working RPC URL.")
        return 1
    cfg = fetch_poke_menu_config(w3, pmu_addr)
    if not cfg:
        print("Failed to read PokeMenu config. Check address and RPC.")
        return 1
    print("--- PokeMenu ---")
    print(f"Next token ID: {cfg['nextTokenId']}")
    print(f"Set count: {cfg['setCounter']}")
    print(f"Fee BPS: {cfg['feeBps']}")
    print(f"Paused: {cfg['platformPaused']}")
    print(f"Treasury: {truncate_addr(cfg['treasury'])}")
    print(f"Vault: {truncate_addr(cfg['vault'])}")
    print(f"Launchpad wallet: {truncate_addr(cfg['launchpadWallet'])}")
    print(f"PokeBro NFT: {truncate_addr(cfg['nft'])}")
    if pbro_addr:
        total = fetch_poke_bro_total_supply(w3, pbro_addr)
        if total is not None:
            print("--- PokeBro ---")
            print(f"Total minted: {total} / {PBRO_MAX_SUPPLY}")
    return 0


# -----------------------------------------------------------------------------
# CLI: sets
# -----------------------------------------------------------------------------
def cmd_sets(args: argparse.Namespace) -> int:
    pmu_addr = args.poke_menu or get_config("poke_menu_address")
    rpc = args.rpc or get_config("rpc_url") or DEFAULT_RPC
    if not pmu_addr:
        print("PokeMenu address not set.")
        return 1
    w3 = connect_rpc(rpc)
    if not w3:
        print("Web3 not available or RPC failed.")
        return 1
    ids = fetch_set_ids(w3, pmu_addr)
    if not ids:
        print("No sets or failed to read.")
        return 0
    print(f"Set IDs: {ids}")
    for sid in ids[: args.limit]:
        info = fetch_set_info(w3, pmu_addr, sid)
        if not info:
            continue
        price_eth = fmt_eth(info["priceWei"])
        remaining = max(0, info["maxPerSet"] - info["mintedFromSet"])
        sale = "OPEN" if info["saleOpen"] else "closed"
        print(f"  Set #{sid}: price {price_eth}, minted {info['mintedFromSet']}/{info['maxPerSet']}, remaining {remaining}, sale {sale}")
    return 0


# -----------------------------------------------------------------------------
# CLI: estimate
# -----------------------------------------------------------------------------
def cmd_estimate(args: argparse.Namespace) -> int:
    pmu_addr = args.poke_menu or get_config("poke_menu_address")
    rpc = args.rpc or get_config("rpc_url") or DEFAULT_RPC
    setId = args.set_id
    count = max(1, min(PMU_MAX_MINT_PER_TX, args.count))
    if not pmu_addr:
        print("PokeMenu address not set.")
        return 1
    w3 = connect_rpc(rpc)
    if not w3:
        print("Web3 not available or RPC failed.")
        return 1
    info = fetch_set_info(w3, pmu_addr, setId)
    if not info:
        print(f"Set #{setId} not found or error.")
        return 1
    total_wei = info["priceWei"] * count
    print(f"Set #{setId}, count {count}: total {fmt_eth(total_wei)}")
    return 0


# -----------------------------------------------------------------------------
# CLI: balance
# -----------------------------------------------------------------------------
def cmd_balance(args: argparse.Namespace) -> int:
    pbro_addr = args.poke_bro or get_config("poke_bro_address")
    account = args.account or get_config("default_account")
    rpc = args.rpc or get_config("rpc_url") or DEFAULT_RPC
    if not pbro_addr or not account:
        print("PokeBro address and account required (--poke-bro, --account or config).")
        return 1
    w3 = connect_rpc(rpc)
    if not w3:
        print("Web3 not available or RPC failed.")
        return 1
    bal = fetch_poke_bro_balance(w3, pbro_addr, account)
    if bal is None:
        print("Failed to read balance.")
        return 1
    print(f"PokeBro balance for {truncate_addr(account)}: {bal}")
    return 0


# -----------------------------------------------------------------------------
# CLI: menu (interactive-style prompts)
# -----------------------------------------------------------------------------
def cmd_menu(args: argparse.Namespace) -> int:
    print(f"\n{APP_NAME} v{VERSION} — PokeMenu / PokeBro helper\n")
    print("1) Info (config and addresses)")
    print("2) Stats (on-chain PokeMenu config + PokeBro total supply)")
    print("3) Sets (list sets and sale status)")
    print("4) Estimate (mint cost for set + count)")
    print("5) Balance (PokeBro balance for an address)")
    print("6) Config get/set (key [value])")
    print("q) Quit")
    try:
        choice = input("\nChoice: ").strip().lower()
    except EOFError:
        return 0
    if choice == "q" or choice == "":
        return 0
    if choice == "1":
        return cmd_info(args)
    if choice == "2":
        return cmd_stats(args)
    if choice == "3":
        return cmd_sets(args)
    if choice == "4":
        try:
            sid = int(input("Set ID: ").strip() or "1")
            cnt = int(input("Count: ").strip() or "1")
        except ValueError:
            sid, cnt = 1, 1
        args.set_id = sid
        args.count = cnt
        return cmd_estimate(args)
    if choice == "5":
        acc = input("Account (0x...): ").strip()
        if acc:
            args.account = acc
        return cmd_balance(args)
    if choice == "6":
        parts = input("Config key [value]: ").strip().split(maxsplit=1)
        args.get = parts[0] if parts else None
        args.value = parts[1] if len(parts) > 1 else None
        args.set = args.get
        return cmd_config(args)
    print("Unknown choice.")
    return 0


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description=f"{APP_NAME} — PokeMenu / PokeBro CLI")
    parser.add_argument("--rpc", default=None, help="RPC URL")
    parser.add_argument("--poke-menu", default=None, help="PokeMenu contract address")
    parser.add_argument("--poke-bro", default=None, help="PokeBro contract address")
    sub = parser.add_subparsers(dest="command", help="Command")

    sub.add_parser("info", help="Show app info and config paths")
    sub.add_parser("menu", help="Interactive menu")

    p_config = sub.add_parser("config", help="Get/set config or list all")
    p_config.add_argument("--get", default=None, help="Get config key")
    p_config.add_argument("--set", default=None, help="Set config key")
    p_config.add_argument("value", nargs="?", default=None, help="Value for set")

    p_stats = sub.add_parser("stats", help="On-chain PokeMenu config and PokeBro total supply")
    p_stats.add_argument("--limit", type=int, default=20, help="Max sets to show (for sets command)")

    p_sets = sub.add_parser("sets", help="List collectible sets from PokeMenu")
    p_sets.add_argument("--limit", type=int, default=20, help="Max sets to show")

    p_est = sub.add_parser("estimate", help="Estimate mint cost for set + count")
    p_est.add_argument("set_id", type=int, nargs="?", default=1, help="Set ID")
    p_est.add_argument("count", type=int, nargs="?", default=1, help="Mint count")

    p_bal = sub.add_parser("balance", help="PokeBro balance for account")
    p_bal.add_argument("--account", default=None, help="Account address")

    args = parser.parse_args()
    if not args.command:
        return cmd_menu(args)
    handlers = {
        "info": cmd_info,
        "config": cmd_config,
        "stats": cmd_stats,
        "sets": cmd_sets,
        "estimate": cmd_estimate,
        "balance": cmd_balance,
        "menu": cmd_menu,
    }
    handler = handlers.get(args.command)
    if not handler:
        parser.print_help()
        return 1
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
