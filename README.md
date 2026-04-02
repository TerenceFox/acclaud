# Claudit

AI-powered personal finance tracking with [hledger](https://hledger.org/) and [Claude](https://claude.ai/claude-code).

## Getting started

```sh
./claudit setup
```

The setup wizard walks you through adding your bank accounts, credit cards, loans, and expense categories.

## Usage

```sh
./claudit import                           # import all CSVs in csv/
./claudit import csv/ally-checking.csv     # import one file
./claudit balance "2026-03"                # account balances
./claudit expenses "this month"            # expense breakdown
./claudit income "2026-03"                 # income statement
./claudit monthly "2026-03"                # monthly expense totals
./claudit cashflow "2026-03"               # cash flow statement
./claudit sankey "2026-03"                 # sankey diagram (opens in browser)
./claudit report "2026-03" ./out ./att     # full monthly Obsidian report
```

### Importing

1. Export a CSV from your bank or credit card
2. Drop it into `csv/` with a filename matching your account (configured during setup)
3. Run `./claudit import`

Claude categorizes each transaction into the appropriate expense account. Existing transactions are used to build a merchant-to-category mapping, ensuring consistent categorization across imports.

### Monthly report

`./claudit report` generates an Obsidian-flavored markdown report with:

- Summary table (income, expenses, net)
- Account balances
- Income statement and cash flow
- Sankey diagram of expenses (PNG)
- Per-category transaction tables, sorted largest to smallest

## Makefile

Wraps all commands, defaulting to the previous month:

```sh
make setup           # run onboarding wizard
make import          # import all CSVs
make balance         # last month's balances
make expenses        # last month's expense breakdown
make sankey          # sankey diagram in browser
make report          # full monthly report to Obsidian vault
make clean-csv       # clear csv/ after importing
make MONTH=2026-03 report  # override month
```

## Dependencies

- [hledger](https://hledger.org/) — `sudo pacman -S hledger`
- [Claude Code](https://claude.ai/claude-code) — used for transaction categorization
- [plotly](https://plotly.com/python/) — `sudo pacman -S python-plotly` — sankey diagrams
- [kaleido](https://github.com/nicmcd/kaleido) — `pip install kaleido` — PNG export
