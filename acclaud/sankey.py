"""Sankey diagram generation with Plotly."""
import sys
import tempfile
import webbrowser

from acclaud.helpers import hledger_json, amount_value

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
        print(f"Error: no expense data found for period '{period}'.", file=sys.stderr)
        print("Try a different period (e.g. 'acclaud sankey 2026-01') or import transactions first.", file=sys.stderr)
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
