"""Simple hledger report passthrough commands."""
from acclaud.helpers import hledger


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
