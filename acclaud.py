#!/usr/bin/env python3
"""Acclaud — AI-powered personal finance tracking with hledger.

Usage:
    acclaud setup                              Configure accounts interactively
    acclaud import [file.csv]                  Import CSV transactions
    acclaud balance [period]                   Account balances
    acclaud expenses [period]                  Expense breakdown
    acclaud income [period]                    Income statement
    acclaud monthly [period]                   Monthly expense totals
    acclaud cashflow [period]                  Cash flow statement
    acclaud sankey [period]                    Sankey diagram (opens in browser)
    acclaud report [YYYY-MM]                   Full monthly Obsidian report

Config keys (in config.json):
    output_dir            Output directory for monthly reports
    attachments_dir       Output directory for report images
"""

import fnmatch
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import webbrowser
from datetime import date, timedelta
PROJECT_DIR = os.getcwd()
JOURNAL = os.path.join(PROJECT_DIR, "budget.journal")
TRANSACTIONS = os.path.join(PROJECT_DIR, "transactions.journal")
ACCOUNTS_FILE = os.path.join(PROJECT_DIR, "accounts.journal")
CONFIG_PATH = os.path.join(PROJECT_DIR, "config.json")
CSV_DIR = os.path.join(PROJECT_DIR, "csv")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def hledger(*args):
    cmd = ["hledger", "-f", JOURNAL] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"hledger error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def hledger_json(*args):
    return json.loads(hledger(*args, "-O", "json"))


def amount_value(amount_obj):
    return float(amount_obj["aquantity"]["floatingPoint"])


def format_currency(value, symbol="$"):
    if value < 0:
        return f"-{symbol}{abs(value):,.2f}"
    return f"{symbol}{value:,.2f}"


def ask(prompt, default=None):
    if default is not None:
        result = input(f"{prompt} [{default}]: ").strip()
        return result if result else default
    return input(f"{prompt}: ").strip()


def yes_no(prompt, default=True):
    suffix = "[Y/n]" if default else "[y/N]"
    result = input(f"{prompt} {suffix}: ").strip().lower()
    if not result:
        return default
    return result in ("y", "yes")


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def resolve_account(filename, config):
    """Match a CSV filename to an hledger account via config patterns."""
    basename = os.path.basename(filename)
    basename = os.path.splitext(basename)[0].lower()

    for acct in config["accounts"]["assets"]:
        for pattern in acct.get("csv_patterns", []):
            if fnmatch.fnmatch(basename, pattern):
                return f"assets:{acct['name']}"

    for acct in config["accounts"]["liabilities"]:
        for pattern in acct.get("csv_patterns", []):
            if fnmatch.fnmatch(basename, pattern):
                return f"liabilities:{acct['name']}"

    return None


def account_type(account):
    if account.startswith("liabilities:"):
        return "credit card"
    return "bank/checking"


def build_merchant_map():
    """Extract merchant → expense account mapping from existing transactions."""
    mapping = {}
    desc = None
    with open(TRANSACTIONS, encoding="utf-8") as f:
        for line in f:
            if re.match(r"^\d{4}-", line):
                desc = line[11:].strip()
            elif line.startswith("    expenses:") and desc:
                account = re.sub(r"\s+-?\$.*", "", line.strip())
                mapping[desc] = account
    return mapping


def build_prompt(csv_content, hledger_account, acct_type, config, merchant_map):
    symbol = config["currency_symbol"]

    expense_accounts = "\n".join(
        f"account expenses:{e['name']}" for e in config["accounts"]["expenses"]
    )

    other_accounts = "\n".join(
        [f"account assets:{a['name']}" for a in config["accounts"]["assets"]]
        + [f"account liabilities:{a['name']}" for a in config["accounts"]["liabilities"]]
        + [f"account income:{n}" for n in config["accounts"]["income"]]
    )

    merchant_lines = "\n".join(
        f"{desc} -> {acct}" for desc, acct in sorted(merchant_map.items())
    )

    return f"""You are a bookkeeping assistant. Below is a CSV statement from: {hledger_account} (a {acct_type} account).

EXPENSE ACCOUNTS:
{expense_accounts}

OTHER ACCOUNTS (use only if a transaction is a transfer between accounts):
{other_accounts}

PREVIOUS MERCHANT CATEGORIZATIONS (use these to stay consistent — always categorize a merchant the same way):
{merchant_lines}

CSV CONTENT:
{csv_content}

INSTRUCTIONS:
- If a merchant matches or closely matches one from the PREVIOUS MERCHANT CATEGORIZATIONS list, use the same expense account.
- Parse every transaction row from the CSV.
- For each transaction, produce a valid hledger journal entry.
- Use your best judgment to assign each transaction to the single most appropriate expense account based on the merchant/description.
- For income/deposits, use the appropriate income account.
- For transfers between accounts (e.g. payment to credit card, transfer between checking/savings), use the appropriate other account — NOT an expense account.
- The balancing account for all non-transfer transactions is: {hledger_account}
- Use the {symbol} symbol for amounts, e.g. {symbol}50.00
- Format dates as YYYY-MM-DD (infer the year from context if not present).
- Use the merchant/description as the transaction description (clean it up to be human-readable).
- Output ONLY valid hledger journal entries, one blank line between each. No commentary, no explanations, no markdown.
- Do NOT wrap output in code fences (no ``` or ```hledger or ```journal). Output raw hledger text only.
- If the CSV is empty or has no transactions, output nothing at all.

SIGN CONVENTIONS (important for hledger):
- This is a {acct_type} account ({hledger_account}).
- For BANK accounts: expenses are POSITIVE, the bank account posting is NEGATIVE (money leaving). Income is the reverse.
- For CREDIT CARD accounts: expenses are POSITIVE, the liability posting is NEGATIVE. Payments to the card are POSITIVE on the liability (reducing it).
- Each transaction's amounts must sum to zero.

Example output for a bank account:
2026-03-15 Whole Foods
    expenses:food              {symbol}85.32
    assets:ally checking      -{symbol}85.32

Example output for a credit card:
2026-03-16 Netflix
    expenses:subscriptions     {symbol}15.99
    liabilities:chase amazon visa  -{symbol}15.99"""


def clean_result(text):
    """Strip markdown fences and non-journal lines from Claude output."""
    lines = []
    for line in text.splitlines():
        if line.startswith("```"):
            continue
        if re.match(r"^(;|[0-9]{4}-|    [a-z]|$)", line):
            lines.append(line)
    return "\n".join(lines).strip()


def cmd_import(args):
    dry_run = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]

    config = load_config()

    if args:
        files = args
        for f in files:
            if not os.path.isfile(f):
                print(f"Error: file not found: {f}", file=sys.stderr)
                sys.exit(1)
    else:
        files = sorted(
            glob.glob(os.path.join(CSV_DIR, "*.csv"))
            + glob.glob(os.path.join(CSV_DIR, "*.CSV"))
        )
        if not files:
            print("No CSV files found in csv/")
            return

    merchant_map = build_merchant_map()

    for csvfile in files:
        print(f"Processing: {csvfile}")

        account = resolve_account(csvfile, config)
        if not account:
            print(f"  ERROR: Cannot determine account from filename '{os.path.basename(csvfile)}'", file=sys.stderr)
            continue

        acct_type_str = account_type(account)
        print(f"  Account: {account} ({acct_type_str})")

        with open(csvfile, encoding="utf-8") as f:
            csv_content = f.read()

        if not csv_content.strip():
            print("  SKIP: Empty file")
            continue

        prompt = build_prompt(csv_content, account, acct_type_str, config, merchant_map)

        result = subprocess.run(
            ["claude", "--print"],
            input=prompt,
            capture_output=True,
            text=True,
        )

        cleaned = clean_result(result.stdout)
        if not cleaned:
            print("  SKIP: No transactions found")
            continue

        tx_count = sum(1 for line in cleaned.splitlines() if re.match(r"^\d{4}-", line))

        if dry_run:
            print(f"\n; Imported from {os.path.basename(csvfile)} on {date.today()}")
            print(cleaned)
            print(f"\n  (dry run: {tx_count} transactions not written)")
        else:
            with open(TRANSACTIONS, "a", encoding="utf-8") as f:
                f.write(f"\n; Imported from {os.path.basename(csvfile)} on {date.today()}\n")
                f.write(cleaned + "\n")
            print(f"  Done: {tx_count} transactions imported")

        # Update merchant map for next file in this run
        desc = None
        for line in cleaned.splitlines():
            if re.match(r"^\d{4}-", line):
                desc = line[11:].strip()
            elif line.startswith("    expenses:") and desc:
                acct = re.sub(r"\s+-?\$.*", "", line.strip())
                merchant_map[desc] = acct


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def cmd_hledger_report(report_type, args):
    period_args = ["-p", args[0]] if args else []

    commands = {
        "balance":  ["bal", "--tree"] + period_args,
        "expenses": ["bal", "expenses", "--tree", "--sort"] + period_args,
        "income":   ["is"] + period_args,
        "monthly":  ["bal", "expenses", "--monthly", "--tree"] + period_args,
        "cashflow": ["cf"] + period_args,
    }

    print(hledger(*commands[report_type]), end="")


# ---------------------------------------------------------------------------
# Sankey
# ---------------------------------------------------------------------------

CATEGORY_COLORS = {
    "housing": "#636EFA",
    "food": "#EF553B",
    "transportation": "#00CC96",
    "shopping": "#AB63FA",
    "subscriptions": "#FFA15A",
    "travel": "#19D3F3",
    "health": "#FF6692",
    "other": "#B6E880",
}


def parse_expense_rows(period=None):
    """Get expense balances from hledger JSON."""
    args = ["bal", "expenses", "--no-total", "--flat"]
    if period:
        args += ["-p", period]
    data = hledger_json(*args)
    rows = data[0] if data and isinstance(data[0][0], list) else data
    results = []
    for row in rows:
        account = row[0]
        amounts = row[3]
        value = sum(abs(amount_value(a)) for a in amounts)
        if value != 0:
            results.append((account, value))
    return results


def build_sankey_figure(rows, title, symbol="$"):
    import plotly.graph_objects as go

    labels = ["Income"]
    sources, targets, values, colors = [], [], [], []

    for account, amount in rows:
        category = account.split(":")[-1]
        label = category.title()
        if label not in labels:
            labels.append(label)
        targets.append(labels.index(label))
        sources.append(0)
        values.append(round(amount, 2))
        colors.append(CATEGORY_COLORS.get(category, "#B6E880"))

    if not values:
        return None

    total = sum(values)
    labels[0] = f"Total Spent ({symbol}{total:,.2f})"

    return go.Figure(data=[go.Sankey(
        node=dict(
            pad=20, thickness=30,
            line=dict(color="black", width=0.5),
            label=labels,
            color=["#888"] + colors,
        ),
        link=dict(
            source=sources, target=targets, value=values,
            color=[
                f"rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.4)"
                for c in colors
            ],
        ),
    )])


def cmd_sankey(args):
    period = args[0] if args else "this month"
    rows = parse_expense_rows(period)

    fig = build_sankey_figure(rows, period)
    if not fig:
        print("No expense data found for this period.", file=sys.stderr)
        sys.exit(1)

    fig.update_layout(
        title_text=f"Monthly Expenses — {period}",
        font_size=14, width=900, height=500,
    )

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
        fig.write_html(f, auto_open=False)
        tmppath = f.name

    webbrowser.open(f"file://{tmppath}")
    print(f"Sankey diagram opened in browser ({tmppath})")


# ---------------------------------------------------------------------------
# Monthly Report
# ---------------------------------------------------------------------------

def cmd_report(args):
    config = load_config()
    symbol = config["currency_symbol"]

    if args:
        year_month = args[0]
    else:
        first = date.today().replace(day=1)
        year_month = (first - timedelta(days=1)).strftime("%Y-%m")

    output_dir = os.path.expanduser(args[1] if len(args) > 1 else config.get("output_dir", os.path.join(PROJECT_DIR, "output")))
    attachments_dir = os.path.expanduser(args[2] if len(args) > 2 else config.get("attachments_dir", output_dir))
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(attachments_dir, exist_ok=True)

    period = year_month

    # Gather data
    bal_data = hledger_json("bal", "--no-total", "--flat", "-p", period)
    bal_rows = bal_data[0] if bal_data and isinstance(bal_data[0][0], list) else bal_data
    balances = [(r[0], sum(amount_value(a) for a in r[3])) for r in bal_rows]

    income_stmt = hledger("is", "-p", period)
    cashflow = hledger("cf", "-p", period)

    expense_categories = parse_expense_rows(period)
    expense_categories.sort(key=lambda x: x[1], reverse=True)

    # Sankey PNG
    sankey_filename = f"{year_month} Sankey.png"
    sankey_path = os.path.join(attachments_dir, sankey_filename)
    fig = build_sankey_figure(expense_categories, period, symbol)
    has_sankey = False
    if fig:
        fig.update_layout(
            title_text=f"Expense Breakdown — {period}",
            font_size=14, width=900, height=500,
        )
        fig.write_image(sankey_path, scale=2)
        has_sankey = True

    # Build markdown
    total_expenses = sum(v for _, v in expense_categories)
    total_income = sum(abs(v) for a, v in balances if a.startswith("income:"))
    net = total_income - total_expenses
    def fc(v): return format_currency(v, symbol)

    lines = [
        "---",
        f"date: {year_month}-01",
        "type: budget-report",
        f"period: {year_month}",
        f"total-expenses: {total_expenses:.2f}",
        f"total-income: {total_income:.2f}",
        "---",
        "",
        f"# {year_month} Budget Report",
        "",
        "## Summary",
        "",
        "| | Amount |",
        "|---|---:|",
        f"| **Total Income** | {fc(total_income)} |",
        f"| **Total Expenses** | {fc(total_expenses)} |",
        f"| **Net** | {fc(net)} |",
        "",
        "## Account Balances",
        "",
        "| Account | Balance |",
        "|---|---:|",
    ]

    for account, value in balances:
        if account.startswith("assets:") or account.startswith("liabilities:"):
            lines.append(f"| {account} | {fc(value)} |")
    lines.append("")

    lines += [
        "## Income Statement", "",
        "```", income_stmt.strip(), "```", "",
        "## Cash Flow", "",
        "```", cashflow.strip(), "```", "",
    ]

    if has_sankey:
        lines += ["## Expense Breakdown", "", f"![[{sankey_filename}]]", ""]

    lines += ["## Expenses by Category", ""]

    for category, total in expense_categories:
        cat_name = category.split(":")[-1].title()
        lines += [
            f"### {cat_name} — {fc(total)}", "",
            "| Date | Description | Amount |",
            "|---|---|---:|",
        ]

        reg_data = hledger_json("reg", category, "-p", period)
        transactions = []
        for row in reg_data:
            tx_date, desc = row[0], row[2]
            amount = sum(amount_value(a) for a in row[3]["pamount"])
            transactions.append((tx_date, desc, amount))
        transactions.sort(key=lambda x: abs(x[2]), reverse=True)

        for tx_date, desc, amount in transactions:
            lines.append(f"| {tx_date} | {desc} | {fc(amount)} |")
        lines.append("")

    report_filename = f"{year_month} Budget Report.md"
    report_path = os.path.join(output_dir, report_filename)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Report: {report_path}")
    if has_sankey:
        print(f"Sankey: {sankey_path}")


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

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


def write_accounts_journal(config):
    lines = ["; Account declarations", ""]

    lines.append("; Assets")
    for acct in config["accounts"]["assets"]:
        lines.append(f"account assets:{acct['name']}")
    lines.append("account assets:cash")
    lines.append("")

    lines.append("; Liabilities")
    for acct in config["accounts"]["liabilities"]:
        lines.append(f"account liabilities:{acct['name']}")
    lines.append("")

    lines.append("; Income")
    for name in config["accounts"]["income"]:
        lines.append(f"account income:{name}")
    lines.append("")

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

    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {ACCOUNTS_FILE}")


def write_budget_journal(config):
    symbol = config["currency_symbol"]
    currency = config["currency"]
    content = f"""; Main hledger journal
; Currency: {currency}

commodity {symbol}1,000.00

include accounts.journal
include transactions.journal
"""
    with open(JOURNAL, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Wrote {JOURNAL}")


def setup_output_dirs(config):
    """Optionally configure output directories in config.json."""
    print("\n--- Output Directories (optional) ---")
    print("Configure where monthly reports and images are saved.")
    current_output = config.get("output_dir", "output/")
    current_attachments = config.get("attachments_dir", "same as output")
    print(f"  output_dir      — report markdown (current: {current_output})")
    print(f"  attachments_dir — report images   (current: {current_attachments})")

    if not yes_no("\nConfigure output directories?", default=False):
        print("Skipped.")
        return

    output = ask("Report output directory", config.get("output_dir", ""))
    attachments = ask("Attachments directory (Enter to use same as output)", config.get("attachments_dir", ""))

    if output:
        config["output_dir"] = output
    if attachments:
        config["attachments_dir"] = attachments


def cmd_setup(_args):
    print("=" * 50)
    print("  Acclaud Setup Wizard")
    print("=" * 50)

    if os.path.exists(CONFIG_PATH):
        if not yes_no("\nconfig.json already exists. Reconfigure?", default=False):
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
    setup_output_dirs(config)

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print(f"\nWrote {CONFIG_PATH}")

    write_accounts_journal(config)
    write_budget_journal(config)

    print("\n" + "=" * 50)
    print("Setup complete!")
    print("Drop CSVs into csv/ and run: acclaud import")
    print("=" * 50)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

COMMANDS = {
    "setup":    cmd_setup,
    "import":   cmd_import,
    "balance":  lambda a: cmd_hledger_report("balance", a),
    "bal":      lambda a: cmd_hledger_report("balance", a),
    "expenses": lambda a: cmd_hledger_report("expenses", a),
    "exp":      lambda a: cmd_hledger_report("expenses", a),
    "income":   lambda a: cmd_hledger_report("income", a),
    "is":       lambda a: cmd_hledger_report("income", a),
    "monthly":  lambda a: cmd_hledger_report("monthly", a),
    "mon":      lambda a: cmd_hledger_report("monthly", a),
    "cashflow": lambda a: cmd_hledger_report("cashflow", a),
    "cf":       lambda a: cmd_hledger_report("cashflow", a),
    "sankey":   cmd_sankey,
    "report":   cmd_report,
}

COMMAND_HELP = {
    "setup":    "Configure accounts, categories, and currency interactively.",
    "import":   "Import CSV bank/credit card statements.\n\n  Usage: acclaud import [--dry-run] [file.csv ...]\n\n  Reads all CSVs in csv/ by default, or specific files if given.\n  --dry-run  Preview imported transactions without writing to journal.",
    "balance":  "Show account balances for a period. Alias: bal",
    "expenses": "Show expense breakdown for a period. Alias: exp",
    "income":   "Show income statement for a period. Alias: is",
    "monthly":  "Show monthly expense totals. Alias: mon",
    "cashflow": "Show cash flow statement. Alias: cf",
    "sankey":   "Generate Sankey expense diagram in browser.\n\n  Usage: acclaud sankey [period]",
    "report":   "Generate full monthly Obsidian markdown report.\n\n  Usage: acclaud report [YYYY-MM]",
}


def check_dependency(name, install_hint):
    if not shutil.which(name):
        print(f"Error: {name} not found on PATH.", file=sys.stderr)
        print(f"Install: {install_hint}", file=sys.stderr)
        sys.exit(1)


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        if len(sys.argv) > 2 and sys.argv[2] in COMMAND_HELP:
            print(f"acclaud {sys.argv[2]}: {COMMAND_HELP[sys.argv[2]]}")
            sys.exit(0)
        print(__doc__.strip())
        sys.exit(0)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if args and args[0] in ("-h", "--help"):
        if cmd in COMMAND_HELP:
            print(f"acclaud {cmd}: {COMMAND_HELP[cmd]}")
            sys.exit(0)

    if cmd not in COMMANDS:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(f"Available: {', '.join(dict.fromkeys(COMMANDS))}")
        sys.exit(1)

    if cmd != "setup" and not os.path.isfile(CONFIG_PATH):
        print("No config.json found. Run 'acclaud setup' first.")
        sys.exit(1)

    if cmd not in ("setup", "help"):
        check_dependency("hledger", "https://hledger.org/install.html")
    if cmd == "import":
        check_dependency("claude", "npm install -g @anthropic-ai/claude-code")

    COMMANDS[cmd](args)


if __name__ == "__main__":
    main()
