"""Path constants and configuration loading."""
import json
import os
import sys
from pathlib import Path

PROJECT_DIR = None
JOURNAL = None
TRANSACTIONS = None
ACCOUNTS_FILE = None
CONFIG_PATH = None
CSV_DIR = None

_sample_mode = False


def _sample_budget_dir():
    return str(Path(__file__).parent / "sample_budget")


def init_paths():
    global PROJECT_DIR, JOURNAL, TRANSACTIONS, ACCOUNTS_FILE, CONFIG_PATH, CSV_DIR, _sample_mode

    cwd = os.getcwd()
    if os.path.isfile(os.path.join(cwd, "config.json")):
        PROJECT_DIR = cwd
        _sample_mode = False
    else:
        PROJECT_DIR = _sample_budget_dir()
        _sample_mode = True

    JOURNAL = os.path.join(PROJECT_DIR, "budget.journal")
    TRANSACTIONS = os.path.join(PROJECT_DIR, "transactions.journal")
    ACCOUNTS_FILE = os.path.join(PROJECT_DIR, "accounts.journal")
    CONFIG_PATH = os.path.join(PROJECT_DIR, "config.json")
    CSV_DIR = os.path.join(PROJECT_DIR, "csv")


def set_cwd_paths():
    global PROJECT_DIR, JOURNAL, TRANSACTIONS, ACCOUNTS_FILE, CONFIG_PATH, CSV_DIR, _sample_mode
    PROJECT_DIR = os.getcwd()
    JOURNAL = os.path.join(PROJECT_DIR, "budget.journal")
    TRANSACTIONS = os.path.join(PROJECT_DIR, "transactions.journal")
    ACCOUNTS_FILE = os.path.join(PROJECT_DIR, "accounts.journal")
    CONFIG_PATH = os.path.join(PROJECT_DIR, "config.json")
    CSV_DIR = os.path.join(PROJECT_DIR, "csv")
    _sample_mode = False


def using_sample():
    return _sample_mode


def load_config():
    if not os.path.exists(CONFIG_PATH):
        print("No config.json found. Run: acclaud setup", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)
    for key in ("currency", "currency_symbol", "accounts"):
        if key not in config:
            print(f"Error: config.json missing required key '{key}'. Run 'acclaud setup' to reconfigure.", file=sys.stderr)
            sys.exit(1)
    accts = config.get("accounts", {})
    for section in ("assets", "liabilities", "income", "expenses"):
        if section not in accts:
            print(f"Error: config.json missing accounts.{section}. Run 'acclaud setup' to reconfigure.", file=sys.stderr)
            sys.exit(1)
    return config


init_paths()
