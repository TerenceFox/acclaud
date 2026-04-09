"""Path constants and configuration loading."""
import json
import os
import sys

PROJECT_DIR = os.getcwd()
JOURNAL = os.path.join(PROJECT_DIR, "budget.journal")
TRANSACTIONS = os.path.join(PROJECT_DIR, "transactions.journal")
ACCOUNTS_FILE = os.path.join(PROJECT_DIR, "accounts.journal")
CONFIG_PATH = os.path.join(PROJECT_DIR, "config.json")
CSV_DIR = os.path.join(PROJECT_DIR, "csv")


def load_config():
    if not os.path.exists(CONFIG_PATH):
        print("No config.json found. Run: acclaud setup", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)
    for key in ("currency", "currency_symbol", "accounts"):
        if key not in config:
            print(f"Error: config.json missing required key '{key}'", file=sys.stderr)
            sys.exit(1)
    accts = config.get("accounts", {})
    for section in ("assets", "liabilities", "income", "expenses"):
        if section not in accts:
            print(f"Error: config.json missing accounts.{section}", file=sys.stderr)
            sys.exit(1)
    return config
