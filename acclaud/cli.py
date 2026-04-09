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

import os
import shutil
import sys

from acclaud.config import CONFIG_PATH
from acclaud.setup import cmd_setup
from acclaud.import_csv import cmd_import
from acclaud.reports import cmd_hledger_report
from acclaud.sankey import cmd_sankey
from acclaud.report import cmd_report

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
