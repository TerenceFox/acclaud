#!/usr/bin/env bash
# Convenience wrapper for common hledger reports.
#
# Usage: ./report.sh <command> [period]
#
# Commands:
#   balance    - Current account balances
#   expenses   - Expense breakdown
#   income     - Income statement (income & expenses)
#   monthly    - Monthly expense totals
#   cashflow   - Cash flow statement
#
# Period examples: "this month", "last month", "2026Q1", "2026"

set -euo pipefail
cd "$(dirname "$0")"

JOURNAL="budget.journal"
CMD="${1:-balance}"
PERIOD="${2:-}"

period_args=()
if [[ -n "$PERIOD" ]]; then
    period_args=(-p "$PERIOD")
fi

case "$CMD" in
    balance|bal)
        hledger -f "$JOURNAL" bal "${period_args[@]}" --tree
        ;;
    expenses|exp)
        hledger -f "$JOURNAL" bal expenses "${period_args[@]}" --tree --sort
        ;;
    income|is)
        hledger -f "$JOURNAL" is "${period_args[@]}"
        ;;
    monthly|mon)
        hledger -f "$JOURNAL" bal expenses "${period_args[@]}" --monthly --tree
        ;;
    cashflow|cf)
        hledger -f "$JOURNAL" cf "${period_args[@]}"
        ;;
    *)
        echo "Unknown command: $CMD"
        echo "Available: balance, expenses, income, monthly, cashflow"
        exit 1
        ;;
esac
