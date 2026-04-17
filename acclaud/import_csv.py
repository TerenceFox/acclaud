"""CSV import and Claude-powered transaction categorization."""
import fnmatch
import glob
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from acclaud import config, simplefin
from acclaud.config import load_config
from acclaud.simplefin import Transaction


@dataclass
class CsvBundle:
    account: str           # hledger account, e.g. "assets:ally checking"
    acct_type: str         # "bank/checking" or "credit card"
    raw_csv: str
    filename: str


@dataclass
class ImportOpts:
    dry_run: bool = False
    date_from: date = None
    date_to: date = None


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


_SIMPLEFIN_ID_RE = re.compile(r";\s*simplefin-id:\s*(\S+)")


def existing_simplefin_ids(journal_path):
    """Return every simplefin-id tag found in journal comments."""
    ids = set()
    if not os.path.isfile(journal_path):
        return ids
    with open(journal_path, encoding="utf-8") as f:
        for line in f:
            m = _SIMPLEFIN_ID_RE.search(line)
            if m:
                ids.add(m.group(1))
    return ids


def _parse_date_arg(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        print(f"Error: invalid date '{s}'. Expected format: YYYY-MM-DD.", file=sys.stderr)
        sys.exit(2)


def parse_import_args(args):
    """Parse --dry-run, --from YYYY-MM-DD, --to YYYY-MM-DD; return (opts, positional)."""
    opts = ImportOpts()
    positional = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--dry-run":
            opts.dry_run = True
        elif a == "--from":
            if i + 1 >= len(args):
                print("Error: --from requires a date argument (YYYY-MM-DD).", file=sys.stderr)
                sys.exit(2)
            opts.date_from = _parse_date_arg(args[i + 1])
            i += 1
        elif a.startswith("--from="):
            opts.date_from = _parse_date_arg(a.split("=", 1)[1])
        elif a == "--to":
            if i + 1 >= len(args):
                print("Error: --to requires a date argument (YYYY-MM-DD).", file=sys.stderr)
                sys.exit(2)
            opts.date_to = _parse_date_arg(args[i + 1])
            i += 1
        elif a.startswith("--to="):
            opts.date_to = _parse_date_arg(a.split("=", 1)[1])
        elif a.startswith("--"):
            print(f"Error: unknown flag '{a}'. Valid flags: --dry-run, --from, --to.", file=sys.stderr)
            sys.exit(2)
        else:
            positional.append(a)
        i += 1
    return opts, positional


def resolve_date_range(opts):
    """Return (date_from, date_to), defaulting to 1st-of-month .. today."""
    today = date.today()
    d_from = opts.date_from or today.replace(day=1)
    d_to = opts.date_to or today
    if d_from > d_to:
        print(f"Error: --from ({d_from}) is after --to ({d_to}). Swap the dates.", file=sys.stderr)
        sys.exit(2)
    return d_from, d_to


def _format_transactions_table(transactions, symbol):
    lines = ["date | amount | description | source_account | id"]
    for t in transactions:
        amount_str = f"{t.amount:.2f}"
        # Pipe-delimited; descriptions are cleaned of pipes defensively.
        desc = (t.description or "").replace("|", "/")
        lines.append(
            f"{t.date.isoformat()} | {amount_str} | {desc} | {t.account} | {t.transaction_id or ''}"
        )
    return "\n".join(lines)


def build_prompt(transactions, csv_bundles, cfg, merchant_map, date_from=None, date_to=None):
    """Build the Claude prompt.

    transactions: normalized, already sign-adjusted per hledger convention
                  (for liabilities, SimpleFIN sign has been flipped upstream).
    csv_bundles:  raw CSV files — Claude parses each per today's flow.
    At most one side is usually populated.
    """
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

    parts = [
        "You are a bookkeeping assistant. Produce valid hledger journal entries for the transactions below.",
        "",
        f"CURRENCY SYMBOL: {symbol}",
        "",
        "EXPENSE ACCOUNTS:",
        expense_accounts,
        "",
        ("THE USER'S OTHER ACCOUNTS (list these to recognize transfers, but do NOT use them as balancing postings — transfers balance to equity:in-transit):"
         if cfg.get("use_in_transit") else
         "OTHER ACCOUNTS (use only if a transaction is a transfer between accounts):"),
        other_accounts,
        "",
        "PREVIOUS MERCHANT CATEGORIZATIONS (use these to stay consistent — always categorize a merchant the same way):",
        merchant_lines,
    ]

    if transactions:
        parts += [
            "",
            "NORMALIZED TRANSACTIONS:",
            "Each row is already sign-adjusted for the source_account's hledger posting.",
            "For each row: source_account posting = amount; the balancing posting (expense/income/transfer) = -amount.",
            "",
            _format_transactions_table(transactions, symbol),
        ]

    if csv_bundles:
        parts += [
            "",
            "RAW CSV FILES (parse each into transactions — infer date/amount/description from the CSV columns):",
        ]
        for b in csv_bundles:
            parts += [
                "",
                f"--- FILE: {b.filename} (source_account={b.account}, type={b.acct_type}) ---",
                b.raw_csv.strip(),
                "--- END FILE ---",
            ]

    if (date_from or date_to) and csv_bundles:
        parts += [
            "",
            f"DATE HINT (CSV only): only emit transactions between {date_from} and {date_to}. "
            "Skip any CSV row outside that range.",
        ]

    use_in_transit = cfg.get("use_in_transit", False)

    transfer_instructions = []
    if use_in_transit:
        transfer_instructions = [
            "- For TRANSFERS between the user's OWN accounts (e.g. credit card payment, checking↔savings, cash advance), the balancing posting MUST be `equity:in-transit` — NOT the counterparty asset or liability account. The counterparty will have its own entry from its own CSV/SimpleFIN source; equity:in-transit cancels across both sides.",
            "  - How to recognize: the description names one of the user's other configured accounts (the OTHER ACCOUNTS list above), e.g. 'Chase Credit Card Autopay' when 'chase' is a configured liability, or 'Transfer to Savings' when 'savings' is a configured asset.",
            "  - Payments from a bank account to a credit card are transfers. Credit card purchases at merchants are NOT transfers (they are expenses).",
            "  - External transfers (Zelle/Venmo/Paypal to someone else) are NOT transfers — they are expenses.",
        ]
    else:
        transfer_instructions = [
            "- For transfers between accounts (e.g. credit card payment, checking↔savings), use the appropriate OTHER account — NOT an expense account.",
        ]

    transfer_examples = []
    if use_in_transit:
        transfer_examples = [
            "",
            f"2026-03-20 Chase Credit Card Autopay",
            f"    equity:in-transit          {symbol}250.00",
            f"    assets:ally checking      -{symbol}250.00",
            "",
            f"2026-03-20 Payment Received — Thank You",
            f"    liabilities:chase visa     {symbol}250.00",
            f"    equity:in-transit         -{symbol}250.00",
        ]

    cc_sign = (
        f"- credit card accounts: expense postings POSITIVE, liability posting NEGATIVE. Payments to the card are POSITIVE on the liability (reducing debt) and balance to equity:in-transit NEGATIVE."
        if use_in_transit else
        f"- credit card accounts: expense postings POSITIVE, liability posting NEGATIVE. Payments to the card are POSITIVE on the liability (reducing debt) and NEGATIVE on the paying bank account."
    )

    parts += [
        "",
        "INSTRUCTIONS:",
        "- If a merchant matches or closely matches one from PREVIOUS MERCHANT CATEGORIZATIONS, reuse its expense account.",
        "- Use your best judgment to assign each transaction to the most appropriate expense account based on the merchant/description.",
        "- For income/deposits, use the appropriate income account.",
        *transfer_instructions,
        "- Clean up descriptions to be human-readable.",
        "- Format dates as YYYY-MM-DD.",
        f"- Use the {symbol} symbol on amounts, e.g. {symbol}50.00.",
        "- Each entry's postings must sum to zero.",
        "- If a NORMALIZED TRANSACTION row has a non-empty id, append a trailing line `    ; simplefin-id:<id>` as the final line of that entry.",
        "- Output ONLY valid hledger text — no code fences, no commentary, no markdown. Blank line between entries.",
        "",
        "SIGN CONVENTIONS for raw CSV rows (they are NOT pre-normalized):",
        "- bank/checking accounts: expense postings POSITIVE, bank-account posting NEGATIVE. Income is the reverse.",
        cc_sign,
        "- For NORMALIZED TRANSACTIONS: simply use amount as the source_account posting and -amount as the balancing posting (signs already baked in).",
        "",
        "Examples:",
        f"2026-03-15 Whole Foods",
        f"    expenses:food              {symbol}85.32",
        f"    assets:ally checking      -{symbol}85.32",
        f"    ; simplefin-id:txn_abc",
        *transfer_examples,
    ]

    return "\n".join(parts)


def clean_result(text):
    """Strip markdown fences and non-journal lines from Claude output."""
    lines = []
    for line in text.splitlines():
        if line.startswith("```"):
            continue
        if re.match(r"^(;|[0-9]{4}-|    [a-z;]|$)", line):
            lines.append(line)
    return "\n".join(lines).strip()


def _update_merchant_map_from_output(cleaned, merchant_map):
    desc = None
    for line in cleaned.splitlines():
        if re.match(r"^\d{4}-", line):
            desc = line[11:].strip()
        elif line.startswith("    expenses:") and desc:
            acct = re.sub(r"\s+-?\$.*", "", line.strip())
            merchant_map[desc] = acct


def _run_claude(prompt):
    result = subprocess.run(
        ["claude", "--print"],
        input=prompt,
        capture_output=True,
        text=True,
    )
    return clean_result(result.stdout)


def _account_is_simplefin_managed(account_str, cfg):
    """True if account_str (e.g. 'assets:ally checking') has simplefin_name set in cfg."""
    if ":" not in account_str:
        return False
    section, name = account_str.split(":", 1)
    for acct in cfg.get("accounts", {}).get(section, []):
        if acct.get("name") == name:
            return bool(acct.get("simplefin_name"))
    return False


def _collect_csv_bundles(cfg, *, skip_simplefin_managed):
    """Scan csv/ and build bundles, optionally skipping files mapped to SimpleFIN accounts."""
    files = sorted(
        glob.glob(os.path.join(config.CSV_DIR, "*.csv"))
        + glob.glob(os.path.join(config.CSV_DIR, "*.CSV"))
    )
    bundles = []
    for csvfile in files:
        account = resolve_account(csvfile, cfg)
        if not account:
            print(
                f"  Warning: skipping {os.path.basename(csvfile)} — filename doesn't match any account's csv_patterns in config.json.",
                file=sys.stderr,
            )
            continue
        if skip_simplefin_managed and _account_is_simplefin_managed(account, cfg):
            print(
                f"  Warning: skipping {os.path.basename(csvfile)} — account {account} is SimpleFIN-managed. "
                f"Move the CSV out of csv/ or remove simplefin_name from config.json to process it.",
                file=sys.stderr,
            )
            continue
        with open(csvfile, encoding="utf-8") as f:
            raw = f.read()
        if not raw.strip():
            print(f"  Warning: skipping {os.path.basename(csvfile)} — empty file.", file=sys.stderr)
            continue
        bundles.append(CsvBundle(
            account=account,
            acct_type=account_type(account),
            raw_csv=raw,
            filename=os.path.basename(csvfile),
        ))
    return bundles


def _import_simplefin_and_csv(opts, cfg, merchant_map):
    """Combined SimpleFIN + csv/ import in one consolidated Claude call."""
    d_from, d_to = resolve_date_range(opts)
    access_url = simplefin.get_access_url()
    print(f"Fetching transactions from SimpleFIN ({d_from} → {d_to})...")
    try:
        payload = simplefin.fetch_transactions(access_url, d_from, d_to)
    except simplefin.SimpleFINError as e:
        print(f"Error: SimpleFIN fetch failed. {e}", file=sys.stderr)
        sys.exit(1)

    transactions = simplefin.normalize(payload, cfg)
    known_ids = existing_simplefin_ids(config.TRANSACTIONS)
    already = sum(1 for t in transactions if t.transaction_id in known_ids)
    transactions = [t for t in transactions if t.transaction_id not in known_ids]

    bundles = _collect_csv_bundles(cfg, skip_simplefin_managed=True)

    if not transactions and not bundles:
        if already:
            print(f"No new transactions ({already} already imported).")
        else:
            print(f"No transactions found between {d_from} and {d_to}.")
        return

    print(
        f"  {len(transactions)} SimpleFIN transaction(s)"
        + (f" ({already} already imported)" if already else "")
        + (f", {len(bundles)} CSV file(s)" if bundles else "")
    )

    prompt = build_prompt(transactions, bundles, cfg, merchant_map, d_from, d_to)
    cleaned = _run_claude(prompt)
    if not cleaned:
        print("  SKIP: Claude returned no entries.")
        return

    tx_count = sum(1 for line in cleaned.splitlines() if re.match(r"^\d{4}-", line))
    src_parts = []
    if transactions:
        src_parts.append(f"SimpleFIN {d_from}→{d_to}")
    if bundles:
        src_parts.append("CSV: " + ", ".join(b.filename for b in bundles))
    header = f"\n; Imported on {date.today()} ({'; '.join(src_parts)})"

    if opts.dry_run:
        print(header)
        print(cleaned)
        print(f"\n  (dry run: {tx_count} transactions not written)")
    else:
        with open(config.TRANSACTIONS, "a", encoding="utf-8") as f:
            f.write(header + "\n")
            f.write(cleaned + "\n")
        print(f"  Done: {tx_count} transactions imported")


def cmd_import(args):
    opts, positional = parse_import_args(args)
    cfg = load_config()
    merchant_map = build_merchant_map()

    if positional:
        files = positional
        for f in files:
            if not os.path.isfile(f):
                print(f"Error: file not found: {f}. Check the path and try again.", file=sys.stderr)
                sys.exit(1)
    elif simplefin.is_configured():
        _import_simplefin_and_csv(opts, cfg, merchant_map)
        return
    else:
        files = sorted(
            glob.glob(os.path.join(config.CSV_DIR, "*.csv"))
            + glob.glob(os.path.join(config.CSV_DIR, "*.CSV"))
        )
        if not files:
            print(
                "Error: no transaction source found.\n"
                "  - Configure SimpleFIN: run 'acclaud setup' and enable SimpleFIN, or\n"
                "  - Drop a CSV into csv/, or\n"
                "  - Specify a file: acclaud import path/to/file.csv",
                file=sys.stderr,
            )
            sys.exit(1)

    for csvfile in files:
        print(f"Processing: {csvfile}")

        account = resolve_account(csvfile, cfg)
        if not account:
            print(
                f"  Error: filename '{os.path.basename(csvfile)}' doesn't match any account's csv_patterns in config.json.",
                file=sys.stderr,
            )
            continue

        acct_type_str = account_type(account)
        print(f"  Account: {account} ({acct_type_str})")

        with open(csvfile, encoding="utf-8") as f:
            csv_content = f.read()

        if not csv_content.strip():
            print("  Warning: skipping — empty file.", file=sys.stderr)
            continue

        bundle = CsvBundle(
            account=account,
            acct_type=acct_type_str,
            raw_csv=csv_content,
            filename=os.path.basename(csvfile),
        )

        prompt = build_prompt([], [bundle], cfg, merchant_map)
        cleaned = _run_claude(prompt)

        if not cleaned:
            print("  SKIP: No transactions found")
            continue

        tx_count = sum(1 for line in cleaned.splitlines() if re.match(r"^\d{4}-", line))

        if opts.dry_run:
            print(f"\n; Imported from {os.path.basename(csvfile)} on {date.today()}")
            print(cleaned)
            print(f"\n  (dry run: {tx_count} transactions not written)")
        else:
            with open(config.TRANSACTIONS, "a", encoding="utf-8") as f:
                f.write(f"\n; Imported from {os.path.basename(csvfile)} on {date.today()}\n")
                f.write(cleaned + "\n")
            print(f"  Done: {tx_count} transactions imported")

        _update_merchant_map_from_output(cleaned, merchant_map)
