# Budget

Personal finance tracking with [hledger](https://hledger.org/) and AI-powered transaction categorization.

## Journal structure

- `budget.journal` — entry point; sets USD commodity and includes the other files
- `accounts.journal` — account and expense category declarations
- `transactions.journal` — all transaction entries

## Accounts

**Assets (bank accounts):**
- `assets:ally checking`
- `assets:ally savings`
- `assets:capital one checking`
- `assets:cash`

**Liabilities (credit cards):**
- `liabilities:chase amazon visa`
- `liabilities:apple card`

**Income:**
- `income:salary`
- `income:other`

**Expenses (6 broad categories):**
- `expenses:housing` — rent, mortgage, utilities, internet, insurance, repairs
- `expenses:food` — groceries, restaurants, coffee, delivery
- `expenses:transportation` — gas, parking, transit, rideshare, car maintenance
- `expenses:shopping` — clothing, electronics, household goods, retail
- `expenses:subscriptions` — streaming, software, memberships, recurring
- `expenses:other` — healthcare, travel, gifts, fees, catch-all

## Importing transactions

1. Export a CSV from your bank or credit card
2. Drop it into `csv/` with a recognizable filename:
   - `ally-checking.csv`
   - `ally-savings.csv`
   - `capital-one-checking.csv`
   - `chase-amazon-visa.csv`
   - `apple-card.csv`
3. Run the import:

```sh
./import.sh                        # process all CSVs in csv/
./import.sh csv/ally-checking.csv  # process one file
```

The script sends each CSV to Claude, which categorizes every transaction into the appropriate expense account and outputs valid hledger entries. Results are appended to `transactions.journal`.

## Reports

```sh
./report.sh balance                  # all account balances
./report.sh expenses                 # expense breakdown
./report.sh expenses "this month"    # expense breakdown for current month
./report.sh income                   # income statement
./report.sh monthly                  # monthly expense totals
./report.sh cashflow                 # cash flow statement
```

All commands accept an optional period argument: `"last month"`, `"2026Q1"`, `"2026"`, etc.

## Dependencies

- [hledger](https://hledger.org/) — `sudo pacman -S hledger`
- [Claude Code](https://claude.ai/claude-code) — used by `import.sh` for transaction categorization
