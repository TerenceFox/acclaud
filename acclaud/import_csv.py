"""CSV import and Claude-powered transaction categorization."""
import fnmatch
import glob
import os
import re
import subprocess
import sys
from datetime import date

from acclaud import config
from acclaud.config import load_config


def resolve_account(filename, cfg):
    """Match a CSV filename to an hledger account via config patterns."""
    basename = os.path.basename(filename)
    basename = os.path.splitext(basename)[0].lower()

    for acct in cfg["accounts"]["assets"]:
        for pattern in acct.get("csv_patterns", []):
            if fnmatch.fnmatch(basename, pattern):
                return f"assets:{acct['name']}"

    for acct in cfg["accounts"]["liabilities"]:
        for pattern in acct.get("csv_patterns", []):
            if fnmatch.fnmatch(basename, pattern):
                return f"liabilities:{acct['name']}"

    return None


def account_type(account):
    if account.startswith("liabilities:"):
        return "credit card"
    return "bank/checking"


def build_merchant_map():
    """Extract merchant -> expense account mapping from existing transactions."""
    mapping = {}
    desc = None
    with open(config.TRANSACTIONS, encoding="utf-8") as f:
        for line in f:
            if re.match(r"^\d{4}-", line):
                desc = line[11:].strip()
            elif line.startswith("    expenses:") and desc:
                account = re.sub(r"\s+-?\$.*", "", line.strip())
                mapping[desc] = account
    return mapping


def build_prompt(csv_content, hledger_account, acct_type, cfg, merchant_map):
    symbol = cfg["currency_symbol"]

    expense_accounts = "\n".join(
        f"account expenses:{e['name']}" for e in cfg["accounts"]["expenses"]
    )

    other_accounts = "\n".join(
        [f"account assets:{a['name']}" for a in cfg["accounts"]["assets"]]
        + [f"account liabilities:{a['name']}" for a in cfg["accounts"]["liabilities"]]
        + [f"account income:{n}" for n in cfg["accounts"]["income"]]
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

    cfg = load_config()

    if args:
        files = args
        for f in files:
            if not os.path.isfile(f):
                print(f"Error: file not found: {f}", file=sys.stderr)
                sys.exit(1)
    else:
        files = sorted(
            glob.glob(os.path.join(config.CSV_DIR, "*.csv"))
            + glob.glob(os.path.join(config.CSV_DIR, "*.CSV"))
        )
        if not files:
            print("No CSV files found in csv/")
            return

    merchant_map = build_merchant_map()

    for csvfile in files:
        print(f"Processing: {csvfile}")

        account = resolve_account(csvfile, cfg)
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

        prompt = build_prompt(csv_content, account, acct_type_str, cfg, merchant_map)

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
            with open(config.TRANSACTIONS, "a", encoding="utf-8") as f:
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
