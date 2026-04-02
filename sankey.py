#!/usr/bin/env python3
"""Generate a sankey diagram of monthly expenses from hledger data.

Usage: ./sankey.py [period]
  period: e.g. "2026-03", "last month", "this month" (default: "this month")

Opens an interactive HTML sankey diagram in your browser.
"""

import json
import subprocess
import sys
import webbrowser
import tempfile
import os

JOURNAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "budget.journal")


def get_expenses(period):
    """Get expense balances from hledger as JSON."""
    cmd = [
        "hledger", "-f", JOURNAL,
        "bal", "expenses",
        "-O", "json",
        "--flat",
        "--no-total",
    ]
    if period:
        cmd += ["-p", period]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"hledger error: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    return json.loads(result.stdout)


def build_sankey(data, period):
    """Build a plotly sankey diagram from hledger JSON balance output."""
    import plotly.graph_objects as go

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

    # hledger JSON wraps rows in an outer list
    rows = data[0] if data and isinstance(data[0][0], list) else data
    for row in rows:
        # hledger JSON: each row is [fullname, shortname, depth, [amounts]]
        account = row[0]
        amounts = row[3]
        amount = sum(
            abs(float(a["aquantity"]["floatingPoint"]))
            for a in amounts
        )
        if amount == 0:
            continue

        # e.g. "expenses:food" -> "Food"
        category = account.split(":")[-1]
        label = category.title()

        if label not in labels:
            labels.append(label)

        target_idx = labels.index(label)
        sources.append(0)  # from "Income"
        targets.append(target_idx)
        values.append(round(amount, 2))
        colors.append(category_colors.get(category, "#B6E880"))

    if not values:
        print("No expense data found for this period.", file=sys.stderr)
        sys.exit(1)

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

    title = f"Monthly Expenses — {period or 'this month'}"
    fig.update_layout(
        title_text=title,
        font_size=14,
        width=900,
        height=500,
    )

    # Write to temp HTML and open in browser
    with tempfile.NamedTemporaryFile(
        suffix=".html", delete=False, mode="w"
    ) as f:
        fig.write_html(f, auto_open=False)
        tmppath = f.name

    webbrowser.open(f"file://{tmppath}")
    print(f"Sankey diagram opened in browser ({tmppath})")


def main():
    period = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "this month"
    data = get_expenses(period)
    build_sankey(data, period)


if __name__ == "__main__":
    main()
