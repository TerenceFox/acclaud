# Acclaud

AI-powered personal finance tracking with [hledger](https://hledger.org/) and [Claude](https://claude.ai/claude-code).

## Getting started

```sh
./acclaud setup
```

The setup wizard walks you through adding your bank accounts, credit cards, loans, and expense categories.

## Usage

```sh
./acclaud import                           # import all CSVs in csv/
./acclaud import csv/ally-checking.csv     # import one file
./acclaud balance "2026-03"                # account balances
./acclaud expenses "this month"            # expense breakdown
./acclaud income "2026-03"                 # income statement
./acclaud monthly "2026-03"                # monthly expense totals
./acclaud cashflow "2026-03"               # cash flow statement
./acclaud sankey "2026-03"                 # sankey diagram (opens in browser)
./acclaud report "2026-03" ./out ./att     # full monthly Obsidian report
```

### Importing

1. Export a CSV from your bank or credit card
2. Drop it into `csv/` with a filename matching your account (configured during setup)
3. Run `./acclaud import`

Claude categorizes each transaction into the appropriate expense account. Existing transactions are used to build a merchant-to-category mapping, ensuring consistent categorization across imports.

### Monthly report

`./acclaud report` generates an Obsidian-flavored markdown report with:

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

## Installation

Acclaud requires Python 3, hledger, Claude Code, and a couple of Python packages.

### Arch Linux

```sh
sudo pacman -S hledger python python-plotly
pip install kaleido
```

### Debian / Ubuntu / WSL

```sh
sudo apt update && sudo apt install hledger python3 python3-pip
pip install plotly kaleido
```

### macOS

```sh
brew install hledger python
pip3 install plotly kaleido
```

### Claude Code

Install [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (required for transaction categorization):

```sh
npm install -g @anthropic-ai/claude-code
```

### Clone and run

```sh
git clone https://github.com/youruser/acclaud.git
cd acclaud
./acclaud setup
```
