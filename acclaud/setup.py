"""Interactive setup wizard."""
import json
import os
import sys
from datetime import date

from acclaud import config, simplefin
from acclaud.helpers import ask, yes_no, format_currency

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


def suggest_pattern(name):
    return "*".join(name.lower().split()) + "*"


def add_accounts(label):
    accounts = []
    print(f"\n--- {label} ---")
    while True:
        name = ask("Account name (e.g. 'ally checking'), or Enter to finish")
        if not name:
            break
        name = name.lower()
        account = {"name": name}
        if "Liabilities" in label:
            kind = ask("Type: (c)redit card or (l)oan?", "c")
            account["type"] = "loan" if kind.lower().startswith("l") else "credit card"
        suggested = suggest_pattern(name)
        pattern = ask("CSV filename pattern", suggested)
        account["csv_patterns"] = [p.strip() for p in pattern.split(",")]
        accounts.append(account)
        print(f"  Added: {name}")
    return accounts


def setup_expenses():
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

    while yes_no("Add another category?", default=False):
        name = ask("Category name")
        desc = ask("  Description", "")
        expenses.append({"name": name.lower(), "description": desc})

    return expenses


def write_accounts_journal(cfg):
    lines = ["; Account declarations", ""]

    lines.append("; Assets")
    for acct in cfg["accounts"]["assets"]:
        lines.append(f"account assets:{acct['name']}")
    lines.append("account assets:cash")
    lines.append("")

    lines.append("; Liabilities")
    for acct in cfg["accounts"]["liabilities"]:
        lines.append(f"account liabilities:{acct['name']}")
    lines.append("")

    lines.append("; Income")
    for name in cfg["accounts"]["income"]:
        lines.append(f"account income:{name}")
    lines.append("")

    lines.append("; Equity")
    lines.append("account equity:opening balances")
    if cfg.get("use_in_transit"):
        lines.append("account equity:in-transit  ; holds the other side of transfers between your accounts; should net to zero")
    lines.append("")

    lines.append("; Expenses")
    max_len = max(len(e["name"]) for e in cfg["accounts"]["expenses"])
    for exp in cfg["accounts"]["expenses"]:
        padding = " " * (max_len - len(exp["name"]) + 2)
        desc = exp.get("description", "")
        if desc:
            lines.append(f"account expenses:{exp['name']}{padding}  ; {desc}")
        else:
            lines.append(f"account expenses:{exp['name']}")
    lines.append("")

    with open(config.ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {config.ACCOUNTS_FILE}")


def write_budget_journal(cfg):
    symbol = cfg["currency_symbol"]
    currency = cfg["currency"]
    content = f"""; Main hledger journal
; Currency: {currency}

commodity {symbol}1,000.00

include accounts.journal
include opening.journal
include transactions.journal
"""
    with open(config.JOURNAL, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Wrote {config.JOURNAL}")


def setup_opening_balances(cfg):
    """Optionally set opening balances for asset and liability accounts."""
    symbol = cfg["currency_symbol"]
    all_accounts = (
        [(f"assets:{a['name']}", a['name']) for a in cfg["accounts"]["assets"]]
        + [(f"liabilities:{a['name']}", a['name']) for a in cfg["accounts"]["liabilities"]]
    )

    if not all_accounts:
        return

    print("\n--- Opening Balances (optional) ---")
    print("Set starting balances so reports show correct totals.")
    print("For liabilities (credit cards), enter the amount owed as a negative number.")
    print("You can skip this and add them later.")

    if not yes_no("\nSet opening balances?", default=False):
        print("Skipped.")
        return

    bal_date = ask("Balance date (YYYY-MM-DD)", date.today().strftime("%Y-%m-%d"))

    entries = []
    for full_name, display_name in all_accounts:
        amount_str = ask(f"  {full_name}", "0")
        try:
            cleaned = amount_str.replace(",", "").replace(symbol, "").strip()
            amount = float(cleaned)
        except ValueError:
            amount = 0
        if amount != 0:
            entries.append((full_name, amount))

    if not entries:
        print("No balances entered.")
        return

    opening_file = os.path.join(config.PROJECT_DIR, "opening.journal")
    lines = [f"; Opening balances as of {bal_date}", ""]
    for full_name, amount in entries:
        lines.append(f"{bal_date} Opening balance")
        lines.append(f"    {full_name:<40s}  {format_currency(amount, symbol)}")
        lines.append(f"    equity:opening balances")
        lines.append("")

    with open(opening_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {opening_file}")


def _prompt_simplefin_names(cfg):
    """For each asset/liability, ask for its SimpleFIN display name.

    If an access URL is configured, queries the API to show the live list of
    account names so the user can pick by number instead of typing.
    """
    all_accts = cfg["accounts"]["assets"] + cfg["accounts"]["liabilities"]
    if not all_accts:
        return

    detected = []
    access_url = simplefin.get_access_url()
    if access_url:
        print("\nFetching account list from SimpleFIN...")
        try:
            detected = simplefin.list_accounts(access_url)
        except simplefin.SimpleFINError as e:
            print(f"  (Couldn't fetch account list: {e}. Falling back to manual entry.)")

    if detected:
        print("\nSimpleFIN reports these accounts:")
        for i, a in enumerate(detected, 1):
            label = a["name"] or "(unnamed)"
            if a["org"]:
                label = f"{label} — {a['org']}"
            print(f"  {i}. {label}")
        print("\nFor each acclaud account, enter the matching SimpleFIN name OR its number above.")
    else:
        print("\nFor each account, enter its name as shown in SimpleFIN.")
    print("(Press Enter to skip — unmapped accounts are ignored on import.)")

    for acct in all_accts:
        current = acct.get("simplefin_name", "")
        val = ask(f"  {acct['name']}", current)
        if not val:
            continue
        if val.isdigit() and detected:
            idx = int(val) - 1
            if 0 <= idx < len(detected):
                val = detected[idx]["name"]
            else:
                print(f"    (Number out of range — storing '{val}' as-is.)")
        acct["simplefin_name"] = val


def setup_simplefin(cfg):
    """Optional SimpleFIN setup. Safe to re-run."""
    print("\n--- SimpleFIN (optional) ---")
    print("SimpleFIN ($15/yr) lets acclaud fetch transactions directly from your banks.")
    print("  Sign up: https://beta-bridge.simplefin.org")
    already = simplefin.is_configured()
    if already:
        print(f"  Credentials already present at {simplefin.CREDENTIALS_PATH}.")
        if yes_no("Replace existing credentials?", default=False):
            _run_token_exchange()
        _prompt_simplefin_names(cfg)
        return

    if not yes_no("Configure SimpleFIN now?", default=False):
        return

    if _run_token_exchange():
        _prompt_simplefin_names(cfg)


def _run_token_exchange():
    """Prompt for setup token, exchange, and write credentials. Return True on success."""
    token = ask("Paste your SimpleFIN setup token")
    if not token:
        print("  Skipped SimpleFIN setup.")
        return False
    try:
        access_url = simplefin.exchange_setup_token(token.strip())
    except simplefin.SimpleFINError as e:
        print(f"  Token exchange failed: {e}")
        return False
    simplefin.write_credentials(access_url)
    print(f"  Wrote {simplefin.CREDENTIALS_PATH} (0600).")
    return True


def setup_output_dirs(cfg):
    """Optionally configure output directories in config.json."""
    print("\n--- Output Directories (optional) ---")
    print("Configure where monthly reports and images are saved.")
    current_output = cfg.get("output_dir", "output/")
    current_attachments = cfg.get("attachments_dir", "same as output")
    print(f"  output_dir      — report markdown (current: {current_output})")
    print(f"  attachments_dir — report images   (current: {current_attachments})")

    if not yes_no("\nConfigure output directories?", default=False):
        print("Skipped.")
        return

    output = ask("Report output directory", cfg.get("output_dir", ""))
    attachments = ask("Attachments directory (Enter to use same as output)", cfg.get("attachments_dir", ""))

    if output:
        cfg["output_dir"] = output
    if attachments:
        cfg["attachments_dir"] = attachments


def cmd_setup(_args):
    config.set_cwd_paths()
    print("=" * 50)
    print("  Acclaud Setup Wizard")
    print("=" * 50)

    if os.path.exists(config.CONFIG_PATH):
        if not yes_no("\nconfig.json already exists. Reconfigure?", default=False):
            if yes_no("Update SimpleFIN credentials / account mappings only?", default=False):
                with open(config.CONFIG_PATH, encoding="utf-8") as f:
                    cfg = json.load(f)
                setup_simplefin(cfg)
                with open(config.CONFIG_PATH, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2)
                print(f"\nUpdated {config.CONFIG_PATH}")
                return
            print("Aborted.")
            return

    print("\n--- Currency ---")
    currency = ask("Currency code", "USD")
    symbol = ask("Currency symbol", "$")

    assets = add_accounts("Assets (bank/checking/savings accounts)")
    liabilities = add_accounts("Liabilities (credit cards & loans)")

    print("\n--- Income ---")
    income = ["salary", "other"]
    print(f"Default income accounts: {', '.join(income)}")
    while yes_no("Add another income account?", default=False):
        name = ask("Income account name")
        income.append(name.lower())

    expenses = setup_expenses()

    use_in_transit = False
    if len(assets) + len(liabilities) > 1:
        print("\n--- Transfer Tracking ---")
        if liabilities:
            print("You have credit cards — payments from a bank account to a card")
            print("will appear in both accounts' statements.")
        else:
            print("You have multiple bank accounts — transfers between them")
            print("will appear in both accounts' statements.")
        print("An equity:in-transit account prevents double-counting by letting")
        print("each side record independently.")
        use_in_transit = yes_no("Add equity:in-transit?")

    cfg = {
        "currency": currency,
        "currency_symbol": symbol,
        "use_in_transit": use_in_transit,
        "accounts": {
            "assets": assets,
            "liabilities": liabilities,
            "income": income,
            "expenses": expenses,
        },
    }

    print("\n" + "=" * 50)
    print("  Summary")
    print("=" * 50)
    print(f"\nCurrency: {currency} ({symbol})")
    print("\nAssets:")
    for a in assets:
        print(f"  - {a['name']} (CSV: {', '.join(a['csv_patterns'])})")
    print("\nLiabilities:")
    for a in liabilities:
        print(f"  - {a['name']} [{a.get('type', 'credit card')}] (CSV: {', '.join(a['csv_patterns'])})")
    print(f"\nIncome: {', '.join(income)}")
    print(f"\nExpenses: {', '.join(e['name'] for e in expenses)}")

    if not yes_no("\nLooks good?"):
        print("Aborted. Run again to start over.")
        return

    # Output directories (optional, before writing config)
    setup_output_dirs(cfg)

    # SimpleFIN (optional) — may add simplefin_name fields to asset/liability accounts
    setup_simplefin(cfg)

    with open(config.CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    print(f"\nWrote {config.CONFIG_PATH}")

    write_accounts_journal(cfg)
    write_budget_journal(cfg)

    os.makedirs(os.path.join(config.PROJECT_DIR, "csv"), exist_ok=True)

    # Create empty placeholder journals if they don't exist (so hledger includes don't fail)
    for name, comment in [
        ("opening.journal", "; Opening balances (use acclaud setup to populate)"),
        ("transactions.journal", "; Imported transactions (use acclaud import to populate)"),
    ]:
        path = os.path.join(config.PROJECT_DIR, name)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(comment + "\n")

    # Opening balances (optional)
    setup_opening_balances(cfg)

    print("\n" + "=" * 50)
    print("Setup complete!")
    print("Drop CSVs into csv/ and run: acclaud import")
    print("=" * 50)
