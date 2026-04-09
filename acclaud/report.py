"""Monthly Obsidian markdown report generation."""
import os
import sys
from datetime import date, timedelta

from acclaud import config
from acclaud.config import load_config
from acclaud.helpers import hledger, hledger_json, amount_value, format_currency
from acclaud.sankey import parse_expense_rows, build_sankey_figure


def cmd_report(args):
    cfg = load_config()
    symbol = cfg["currency_symbol"]

    if args:
        year_month = args[0]
    else:
        first = date.today().replace(day=1)
        year_month = (first - timedelta(days=1)).strftime("%Y-%m")

    output_dir = os.path.expanduser(args[1] if len(args) > 1 else cfg.get("output_dir", os.path.join(config.PROJECT_DIR, "output")))
    attachments_dir = os.path.expanduser(args[2] if len(args) > 2 else cfg.get("attachments_dir", output_dir))
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
