#!/usr/bin/env python3
"""Generate a monthly budget report as Obsidian-flavored markdown.

Usage: ./monthly-report.py [YYYY-MM] [output-dir]
  YYYY-MM:    month to report on (default: last month)
  output-dir: where to write the report (default: current directory)

Produces:
  - YYYY-MM Budget Report.md  (the report)
  - YYYY-MM Sankey.html        (interactive sankey diagram, embedded in report)
"""

import json
import os
import subprocess
import sys
from datetime import date, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JOURNAL = os.path.join(SCRIPT_DIR, "budget.journal")


def hledger(*args):
    """Run an hledger command and return stdout."""
    cmd = ["hledger", "-f", JOURNAL] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"hledger error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def hledger_json(*args):
    """Run an hledger command with JSON output and parse it."""
    return json.loads(hledger(*args, "-O", "json"))


def amount_value(amount_obj):
    """Extract float value from an hledger amount object."""
    return float(amount_obj["aquantity"]["floatingPoint"])


def format_usd(value):
    """Format a float as USD string."""
    if value < 0:
        return f"-${abs(value):,.2f}"
    return f"${value:,.2f}"


def get_month_period(year_month):
    """Return the hledger period string for a given YYYY-MM."""
    return year_month


def get_balances(period):
    """Get all account balances as a list of (account, amount) tuples."""
    data = hledger_json("bal", "--no-total", "--flat", "-p", period)
    results = []
    rows = data[0] if data and isinstance(data[0][0], list) else data
    for row in rows:
        account = row[0]
        amounts = row[3]
        value = sum(amount_value(a) for a in amounts)
        results.append((account, value))
    return results


def get_income_statement(period):
    """Get income statement as plain text."""
    return hledger("is", "-p", period)


def get_cashflow(period):
    """Get cash flow statement as plain text."""
    return hledger("cf", "-p", period)


def get_expense_categories(period):
    """Get expense category totals sorted by amount."""
    data = hledger_json("bal", "expenses", "--no-total", "--flat", "-p", period)
    results = []
    rows = data[0] if data and isinstance(data[0][0], list) else data
    for row in rows:
        account = row[0]
        amounts = row[3]
        value = sum(amount_value(a) for a in amounts)
        if value != 0:
            results.append((account, value))
    results.sort(key=lambda x: x[1], reverse=True)
    return results


def get_transactions_for_category(category, period):
    """Get individual transactions for an expense category."""
    data = hledger_json("reg", category, "-p", period)
    transactions = []
    for row in data:
        tx_date = row[0]
        description = row[2]
        posting = row[3]
        amount = sum(amount_value(a) for a in posting["pamount"])
        transactions.append((tx_date, description, amount))
    # Sort by amount descending (largest first)
    transactions.sort(key=lambda x: abs(x[2]), reverse=True)
    return transactions


def generate_sankey(period, output_path):
    """Generate sankey diagram as PNG image."""
    import plotly.graph_objects as go

    data = hledger_json("bal", "expenses", "--no-total", "--flat", "-p", period)
    rows = data[0] if data and isinstance(data[0][0], list) else data

    labels = ["Income"]
    sources = []
    targets = []
    values = []
    colors = []

    category_colors = {
        "housing": "#636EFA",
        "food": "#EF553B",
        "transportation": "#00CC96",
        "shopping": "#AB63FA",
        "subscriptions": "#FFA15A",
        "travel": "#19D3F3",
        "health": "#FF6692",
        "other": "#B6E880",
    }

    for row in rows:
        account = row[0]
        amounts = row[3]
        amount = sum(abs(amount_value(a)) for a in amounts)
        if amount == 0:
            continue

        category = account.split(":")[-1]
        label = category.title()

        if label not in labels:
            labels.append(label)

        target_idx = labels.index(label)
        sources.append(0)
        targets.append(target_idx)
        values.append(round(amount, 2))
        colors.append(category_colors.get(category, "#B6E880"))

    if not values:
        return False

    total = sum(values)
    labels[0] = f"Total Spent (${total:,.2f})"

    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=20,
            thickness=30,
            line=dict(color="black", width=0.5),
            label=labels,
            color=["#888"] + colors,
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            color=[
                f"rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.4)"
                for c in colors
            ],
        ),
    )])

    fig.update_layout(
        title_text=f"Expense Breakdown — {period}",
        font_size=14,
        width=900,
        height=500,
    )

    fig.write_image(output_path, scale=2)
    return True


def build_report(year_month, output_dir, attachments_dir=None):
    """Build the full monthly report."""
    if attachments_dir is None:
        attachments_dir = output_dir
    os.makedirs(attachments_dir, exist_ok=True)

    period = get_month_period(year_month)

    # Gather data
    balances = get_balances(period)
    income_stmt = get_income_statement(period)
    cashflow = get_cashflow(period)
    expense_categories = get_expense_categories(period)

    # Generate sankey
    sankey_filename = f"{year_month} Sankey.png"
    sankey_path = os.path.join(attachments_dir, sankey_filename)
    has_sankey = generate_sankey(period, sankey_path)

    # Build markdown
    lines = []

    # Frontmatter
    lines.append("---")
    lines.append(f"date: {year_month}-01")
    lines.append("type: budget-report")
    lines.append(f"period: {year_month}")
    total_expenses = sum(v for _, v in expense_categories)
    total_income = sum(abs(v) for acct, v in balances if acct.startswith("income:"))
    lines.append(f"total-expenses: {total_expenses:.2f}")
    lines.append(f"total-income: {total_income:.2f}")
    lines.append("---")
    lines.append("")

    # Title
    lines.append(f"# {year_month} Budget Report")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| | Amount |")
    lines.append(f"|---|---:|")
    lines.append(f"| **Total Income** | {format_usd(total_income)} |")
    lines.append(f"| **Total Expenses** | {format_usd(total_expenses)} |")
    net = total_income - total_expenses
    lines.append(f"| **Net** | {format_usd(net)} |")
    lines.append("")

    # Balances (assets, liabilities only — expenses are shown below)
    lines.append("## Account Balances")
    lines.append("")
    lines.append("| Account | Balance |")
    lines.append("|---|---:|")
    for account, value in balances:
        if account.startswith("assets:") or account.startswith("liabilities:"):
            lines.append(f"| {account} | {format_usd(value)} |")
    lines.append("")

    # Income Statement
    lines.append("## Income Statement")
    lines.append("")
    lines.append("```")
    lines.append(income_stmt.strip())
    lines.append("```")
    lines.append("")

    # Cash Flow
    lines.append("## Cash Flow")
    lines.append("")
    lines.append("```")
    lines.append(cashflow.strip())
    lines.append("```")
    lines.append("")

    # Sankey
    if has_sankey:
        lines.append("## Expense Breakdown")
        lines.append("")
        lines.append(f"![[{sankey_filename}]]")
        lines.append("")

    # Expense category tables
    lines.append("## Expenses by Category")
    lines.append("")

    for category, total in expense_categories:
        cat_name = category.split(":")[-1].title()
        lines.append(f"### {cat_name} — {format_usd(total)}")
        lines.append("")
        lines.append("| Date | Description | Amount |")
        lines.append("|---|---|---:|")

        transactions = get_transactions_for_category(category, period)
        for tx_date, desc, amount in transactions:
            lines.append(f"| {tx_date} | {desc} | {format_usd(amount)} |")

        lines.append("")

    # Write report
    report_filename = f"{year_month} Budget Report.md"
    report_path = os.path.join(output_dir, report_filename)
    with open(report_path, "w") as f:
        f.write("\n".join(lines))

    print(f"Report: {report_path}")
    if has_sankey:
        print(f"Sankey: {sankey_path}")


def main():
    # Default to last month
    if len(sys.argv) > 1:
        year_month = sys.argv[1]
    else:
        today = date.today()
        first_of_month = today.replace(day=1)
        last_month = first_of_month - timedelta(days=1)
        year_month = last_month.strftime("%Y-%m")

    output_dir = sys.argv[2] if len(sys.argv) > 2 else "."
    attachments_dir = sys.argv[3] if len(sys.argv) > 3 else None
    os.makedirs(output_dir, exist_ok=True)

    build_report(year_month, output_dir, attachments_dir)


if __name__ == "__main__":
    main()
