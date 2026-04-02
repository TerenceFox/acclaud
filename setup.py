#!/usr/bin/env python3
"""Interactive onboarding wizard for budget tracking setup.

Walks you through adding accounts and expense categories,
then generates config.json and accounts.journal.

Usage: ./setup.py
"""

import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
ACCOUNTS_PATH = os.path.join(SCRIPT_DIR, "accounts.journal")
BUDGET_PATH = os.path.join(SCRIPT_DIR, "budget.journal")

DEFAULT_EXPENSES = [
    {"name": "housing", "description": "rent, mortgage, utilities, internet, insurance, repairs"},
    {"name": "food", "description": "groceries, restaurants, coffee, delivery"},
    {"name": "transportation", "description": "gas, parking, transit, rideshare, car maintenance"},
    {"name": "shopping", "description": "clothing, electronics, household goods, general retail"},
    {"name": "subscriptions", "description": "streaming, software, memberships, recurring charges"},
    {"name": "travel", "description": "flights, hotels, foreign ATM, travel expenses"},
    {"name": "health", "description": "medical, pharmacy, dental"},
    {"name": "other", "description": "gifts, fees, everything else"},
]


def ask(prompt, default=None):
    """Prompt user for input with an optional default."""
    if default:
        result = input(f"{prompt} [{default}]: ").strip()
        return result if result else default
    return input(f"{prompt}: ").strip()


def yes_no(prompt, default=True):
    """Prompt for yes/no."""
    suffix = "[Y/n]" if default else "[y/N]"
    result = input(f"{prompt} {suffix}: ").strip().lower()
    if not result:
        return default
    return result in ("y", "yes")


def suggest_pattern(name):
    """Suggest a CSV filename pattern from an account name."""
    parts = name.lower().split()
    return "*".join(parts) + "*"


def add_accounts(account_type_label):
    """Interactive loop to add accounts."""
    accounts = []
    print(f"\n--- {account_type_label} ---")

    while True:
        name = ask(f"Account name (e.g. 'ally checking'), or Enter to finish")
        if not name:
            break

        name = name.lower()
        account = {"name": name}

        if account_type_label == "Liabilities":
            kind = ask("Type: (c)redit card or (l)oan?", "c")
            account["type"] = "loan" if kind.lower().startswith("l") else "credit card"

        # CSV pattern
        suggested = suggest_pattern(name)
        pattern = ask(f"CSV filename pattern", suggested)
        # Allow comma-separated multiple patterns
        account["csv_patterns"] = [p.strip() for p in pattern.split(",")]

        accounts.append(account)
        print(f"  Added: {name}")

    return accounts


def setup_expenses():
    """Configure expense categories."""
    print("\n--- Expense Categories ---")
    print("Default categories:")
    for i, exp in enumerate(DEFAULT_EXPENSES, 1):
        print(f"  {i}. {exp['name']} — {exp['description']}")

    if yes_no("\nUse these defaults?"):
        expenses = [e.copy() for e in DEFAULT_EXPENSES]
    else:
        expenses = []
        print("Enter categories one at a time (name, then description).")
        while True:
            name = ask("Category name, or Enter to finish")
            if not name:
                break
            desc = ask("  Description", "")
            expenses.append({"name": name.lower(), "description": desc})

    # Offer to add more
    while yes_no("Add another category?", default=False):
        name = ask("Category name")
        desc = ask("  Description", "")
        expenses.append({"name": name.lower(), "description": desc})

    return expenses


def write_config(config):
    """Write config.json."""
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    print(f"\nWrote {CONFIG_PATH}")


def write_accounts_journal(config):
    """Generate accounts.journal from config."""
    lines = ["; Account declarations", ""]

    # Assets
    lines.append("; Assets")
    for acct in config["accounts"]["assets"]:
        lines.append(f"account assets:{acct['name']}")
    lines.append("account assets:cash")
    lines.append("")

    # Liabilities
    lines.append("; Liabilities")
    for acct in config["accounts"]["liabilities"]:
        lines.append(f"account liabilities:{acct['name']}")
    lines.append("")

    # Income
    lines.append("; Income")
    for name in config["accounts"]["income"]:
        lines.append(f"account income:{name}")
    lines.append("")

    # Expenses
    lines.append("; Expenses")
    max_len = max(len(e["name"]) for e in config["accounts"]["expenses"])
    for exp in config["accounts"]["expenses"]:
        padding = " " * (max_len - len(exp["name"]) + 2)
        desc = exp.get("description", "")
        if desc:
            lines.append(f"account expenses:{exp['name']}{padding}  ; {desc}")
        else:
            lines.append(f"account expenses:{exp['name']}")
    lines.append("")

    with open(ACCOUNTS_PATH, "w") as f:
        f.write("\n".join(lines))
    print(f"Wrote {ACCOUNTS_PATH}")


def write_budget_journal(config):
    """Update budget.journal with the chosen currency."""
    symbol = config["currency_symbol"]
    currency = config["currency"]

    content = f"""; Main hledger journal
; Currency: {currency}

commodity {symbol}1,000.00

include accounts.journal
include transactions.journal
"""
    with open(BUDGET_PATH, "w") as f:
        f.write(content)
    print(f"Wrote {BUDGET_PATH}")


def main():
    print("=" * 50)
    print("  Budget Setup Wizard")
    print("=" * 50)

    if os.path.exists(CONFIG_PATH):
        if not yes_no("\nconfig.json already exists. Reconfigure?", default=False):
            print("Aborted.")
            sys.exit(0)

    # Currency
    print("\n--- Currency ---")
    currency = ask("Currency code", "USD")
    symbol = ask("Currency symbol", "$")

    # Assets
    assets = add_accounts("Assets (bank/checking/savings accounts)")

    # Liabilities
    liabilities = add_accounts("Liabilities (credit cards & loans)")

    # Income
    print("\n--- Income ---")
    income = ["salary", "other"]
    print(f"Default income accounts: {', '.join(income)}")
    while yes_no("Add another income account?", default=False):
        name = ask("Income account name")
        income.append(name.lower())

    # Expenses
    expenses = setup_expenses()

    # Build config
    config = {
        "currency": currency,
        "currency_symbol": symbol,
        "accounts": {
            "assets": assets,
            "liabilities": liabilities,
            "income": income,
            "expenses": expenses,
        },
    }

    # Summary
    print("\n" + "=" * 50)
    print("  Summary")
    print("=" * 50)
    print(f"\nCurrency: {currency} ({symbol})")
    print(f"\nAssets:")
    for a in assets:
        print(f"  - {a['name']} (CSV: {', '.join(a['csv_patterns'])})")
    print(f"\nLiabilities:")
    for a in liabilities:
        print(f"  - {a['name']} [{a.get('type', 'credit card')}] (CSV: {', '.join(a['csv_patterns'])})")
    print(f"\nIncome: {', '.join(income)}")
    print(f"\nExpenses: {', '.join(e['name'] for e in expenses)}")

    if not yes_no("\nLooks good?"):
        print("Aborted. Run again to start over.")
        sys.exit(0)

    # Write files
    write_config(config)
    write_accounts_journal(config)
    write_budget_journal(config)

    print("\n" + "=" * 50)
    print("Setup complete!")
    print("Drop CSVs into csv/ and run: make import")
    print("=" * 50)


if __name__ == "__main__":
    main()
