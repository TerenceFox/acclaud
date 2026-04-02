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
./acclaud report "2026-03"                 # full monthly Obsidian report
```

All commands default to the previous month when no period is given.

### Environment variables

| Variable | Description | Default |
|---|---|---|
| `ACCLAUD_VAULT` | Output directory for monthly reports | `.` (current directory) |
| `ACCLAUD_ATTACHMENTS` | Output directory for report images | same as vault |

Configure in `.env` (created on first run, excluded from git):

```sh
ACCLAUD_VAULT=~/notes/02 Areas/Budget
ACCLAUD_ATTACHMENTS=~/notes/attachments
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

## Installation

Acclaud requires Python 3, hledger, Claude Code, and a couple of Python packages.

### Arch Linux

```sh
sudo pacman -S hledger python python-plotly
pip install kaleido python-dotenv
```

### Debian / Ubuntu / WSL

```sh
sudo apt update && sudo apt install hledger python3 python3-pip
pip install plotly kaleido python-dotenv
```

### macOS

```sh
brew install hledger python
pip3 install plotly kaleido python-dotenv
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
