# Claudit

Personal finance tracking with [hledger](https://hledger.org/) and AI-powered transaction categorization.

## Getting started

Run the setup wizard to configure your accounts:

```sh
make setup
```

This walks you through adding your bank accounts, credit cards, loans, and expense categories. It generates `config.json` and `accounts.journal`.

## Importing transactions

1. Export a CSV from your bank or credit card
2. Drop it into `csv/` with a filename matching your account (configured during setup)
3. Run the import:

```sh
./import.sh                        # process all CSVs in csv/
./import.sh csv/ally-checking.csv  # process one file
```

The script sends each CSV to Claude, which categorizes every transaction into the appropriate expense account and outputs valid hledger entries. Results are appended to `transactions.journal`.

The importer also reads existing transactions to build a merchant-to-category mapping, ensuring merchants are always categorized consistently across imports.

## Reports

```sh
./report.sh balance                  # all account balances
./report.sh expenses                 # expense breakdown
./report.sh expenses "this month"    # expense breakdown for current month
./report.sh income                   # income statement
./report.sh monthly                  # monthly expense totals
./report.sh cashflow                 # cash flow statement
./report.sh sankey "2026-03"         # sankey diagram (opens in browser)
./report.sh report "2026-03"         # full monthly report (Obsidian markdown)
./report.sh report "2026-03" ~/vault/budget  # output to a specific directory
```

All commands accept an optional period argument: `"last month"`, `"2026Q1"`, `"2026"`, etc.

### Monthly report

`./monthly-report.py YYYY-MM [output-dir] [attachments-dir]` generates a full Obsidian-flavored markdown report containing:

- Summary table (income, expenses, net)
- Account balances
- Income statement and cash flow
- Sankey diagram of expenses (PNG image)
- Per-category transaction tables, sorted largest to smallest

## Makefile

A Makefile wraps all commands, defaulting to the previous month:

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
- [jq](https://jqlang.github.io/jq/) — `sudo pacman -S jq` — used by `import.sh` to read config
- [Claude Code](https://claude.ai/claude-code) — used by `import.sh` for transaction categorization
- [plotly](https://plotly.com/python/) — `sudo pacman -S python-plotly` — used by `sankey.py` for visualizations
- [kaleido](https://github.com/nicmcd/kaleido) — `pip install kaleido` — used for sankey PNG export
