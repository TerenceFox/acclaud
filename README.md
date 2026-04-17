# Acclaud

[![PyPI](https://img.shields.io/pypi/v/acclaud)](https://pypi.org/project/acclaud/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

AI-powered personal finance tracking with [hledger](https://hledger.org/) and [Claude](https://docs.anthropic.com/en/docs/claude-code).

![Demo](assets/demo.gif)

## How it works

1. Export CSVs from your bank or credit card
2. `acclaud import` sends them to Claude, which categorizes each transaction into your expense accounts
3. Transactions are stored in plain-text hledger journals
4. `acclaud report` generates a monthly markdown report with balances, statements, and a Sankey diagram

Merchant categorizations are learned from your history, so imports stay consistent over time.

## Installation

> **System dependencies:** Acclaud requires [hledger](https://hledger.org/install.html) and [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed and available on your PATH.

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
pip install acclaud
```

Or install from source:

```sh
pip install git+https://github.com/TerenceFox/acclaud
```

Python dependencies (plotly, kaleido, requests) are installed automatically.

### Upgrading

```sh
pip install --upgrade git+https://github.com/TerenceFox/acclaud
```

This pulls the latest from GitHub and re-syncs dependencies from `pyproject.toml`.

## Quick start

Acclaud ships with a sample budget so you can see it in action immediately:

```sh
pip install git+https://github.com/TerenceFox/acclaud
acclaud report
```

No setup required — the sample budget contains ~100 fictional transactions across three months, enough to produce a full report with balances, income statements, and a Sankey diagram.

### Setting up your own budget

When you're ready to use real data:

```sh
mkdir my-budget && cd my-budget
acclaud setup
```

The setup wizard walks you through adding your bank accounts, credit cards, loans, expense categories, opening balances, and output directories. It creates all the files needed to get started (`config.json`, journal files, and a `csv/` directory). Everything lives in your project folder, so each directory is a self-contained budget — you can run multiple budgets on the same machine.

## Usage

```sh
acclaud import                           # fetch from SimpleFIN (if configured) or import CSVs in csv/
acclaud import csv/ally-checking.csv     # import one file (overrides SimpleFIN)
acclaud import --from 2026-03-01 --to 2026-03-31
acclaud import --dry-run                 # preview without writing
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

Two supported sources — same command either way:

**From CSV** (default):

1. Export a CSV from your bank or credit card
2. Drop it into `csv/` with a filename matching your account (configured during setup)
3. Run `acclaud import`

**From SimpleFIN** (automated, optional):

[SimpleFIN](https://beta-bridge.simplefin.org) ($15/yr) gives acclaud read-only API access to your bank and credit card transactions. When configured, `acclaud import` fetches transactions directly — no CSV export step.

1. Sign up at https://beta-bridge.simplefin.org and connect your accounts
2. Copy the setup token from your SimpleFIN dashboard
3. Run `acclaud setup` and answer yes at the SimpleFIN prompt (or re-run setup, decline full reconfigure, and accept "Update SimpleFIN only")
4. For each of your acclaud asset/liability accounts, enter its SimpleFIN display name when prompted
5. Run `acclaud import`

The access URL is stored at `~/.config/acclaud/credentials` (mode 0600). Alternatively, set `SIMPLEFIN_ACCESS_URL` in the environment — env var takes precedence over the file.

**Date ranges**: by default, imports cover the 1st of the current month to today. Override with `--from YYYY-MM-DD --to YYYY-MM-DD`. Repeated imports are deduplicated via SimpleFIN transaction IDs recorded in `transactions.journal` as `; simplefin-id:…` comments.

**Mixed sources in one run**: if SimpleFIN is configured AND you also have CSVs in `csv/`, `acclaud import` processes both in a single pass. CSV files that resolve to a SimpleFIN-managed account (one with `simplefin_name` set) are skipped with a warning to prevent duplicates. This makes transitioning one account at a time easy: once you set `simplefin_name` on an account, its CSVs are auto-ignored.

**Explicit file arg wins**: if you run `acclaud import some-file.csv`, it takes the CSV path regardless of SimpleFIN configuration (no SimpleFIN fetch, no mixing).

Claude categorizes each transaction into the appropriate expense account. Existing transactions are used to build a merchant-to-category mapping, ensuring consistent categorization across imports.

### Monthly report

`acclaud report` generates an Obsidian-flavored markdown report with:

- Summary table (income, expenses, net)
- Account balances
- Income statement and cash flow
- Sankey diagram of expenses (PNG)
- Per-category transaction tables, sorted largest to smallest

### Opening balances

During setup (or by editing `opening.journal` directly), you can set starting balances for your accounts. Without these, balance reports only reflect transaction flows and asset totals will appear incorrect. Enter positive amounts for assets and negative amounts for liabilities (e.g. credit card debt).

### Configuration

Output directories can be configured during `acclaud setup` or by editing `config.json` directly:

```json
{
  "output_dir": "~/notes/02 Areas/Budget",
  "attachments_dir": "~/notes/attachments"
}
```

| Key | Description | Default |
|---|---|---|
| `output_dir` | Output directory for reports | `output/` |
| `attachments_dir` | Optional separate directory for images | same as `output_dir` |

## Built with

- [hledger](https://hledger.org/) -- plain-text accounting
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) -- AI-powered CSV categorization
- [Plotly](https://plotly.com/python/) -- Sankey diagrams

Built with [Claude Code](https://claude.ai/claude-code).
