# Acclaud

AI-powered personal finance tracking with [hledger](https://hledger.org/) and [Claude](https://claude.ai/claude-code).

## Installation

Requires Python 3.9+, hledger, and Claude Code.

### 1. Install hledger

- **Arch**: `sudo pacman -S hledger`
- **Debian/Ubuntu/WSL**: `sudo apt install hledger`
- **macOS**: `brew install hledger`

### 2. Install Claude Code

```sh
npm install -g @anthropic-ai/claude-code
```

### 3. Install Acclaud

```sh
pip install git+https://github.com/youruser/acclaud.git
```

Python dependencies (plotly, kaleido, python-dotenv) are installed automatically.

## Getting started

```sh
mkdir my-budget && cd my-budget
acclaud setup
```

The setup wizard walks you through adding your bank accounts, credit cards, loans, and expense categories. All other commands require setup to be run first.

## Usage

```sh
acclaud import                           # import all CSVs in csv/
acclaud import csv/ally-checking.csv     # import one file
acclaud balance "2026-03"                # account balances
acclaud expenses "this month"            # expense breakdown
acclaud income "2026-03"                 # income statement
acclaud monthly "2026-03"                # monthly expense totals
acclaud cashflow "2026-03"               # cash flow statement
acclaud sankey "2026-03"                 # sankey diagram (opens in browser)
acclaud report "2026-03"                 # full monthly report
```

All commands default to the previous month when no period is given.

### Importing

1. Export a CSV from your bank or credit card
2. Drop it into `csv/` with a filename matching your account (configured during setup)
3. Run `acclaud import`

Claude categorizes each transaction into the appropriate expense account. Existing transactions are used to build a merchant-to-category mapping, ensuring consistent categorization across imports.

### Monthly report

`acclaud report` generates an Obsidian-flavored markdown report with:

- Summary table (income, expenses, net)
- Account balances
- Income statement and cash flow
- Sankey diagram of expenses (PNG)
- Per-category transaction tables, sorted largest to smallest

### Configuration

Set output directories in a `.env` file in your project folder:

```sh
ACCLAUD_OUTPUT=~/notes/02 Areas/Budget
ACCLAUD_ATTACHMENTS=~/notes/attachments
```

| Variable | Description | Default |
|---|---|---|
| `ACCLAUD_OUTPUT` | Output directory for reports and images | `output/` |
| `ACCLAUD_ATTACHMENTS` | Optional separate directory for images | same as `ACCLAUD_OUTPUT` |
