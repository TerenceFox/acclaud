#!/usr/bin/env bash
# Import CSV bank/credit card statements into hledger journal format.
# Reads CSVs from ./csv/, uses Claude to categorize each transaction,
# and appends the results to transactions.journal.
#
# Usage: ./import.sh [filename.csv]
#   If no filename given, processes all CSVs in ./csv/

set -euo pipefail
cd "$(dirname "$0")"

JOURNAL="transactions.journal"
CSV_DIR="csv"
ACCOUNTS_FILE="accounts.journal"

# Read account definitions so Claude knows the valid categories
ACCOUNTS=$(grep '^account expenses:' "$ACCOUNTS_FILE")

# Map CSV filename to hledger account
# Expected filenames: chase-amazon-visa.csv, apple-card.csv,
#   ally-checking.csv, ally-savings.csv, capital-one-checking.csv
resolve_account() {
    local basename
    basename=$(basename "$1")
    basename="${basename%.[cC][sS][vV]}"
    basename=$(echo "$basename" | tr '[:upper:]' '[:lower:]')

    case "$basename" in
        *chase*amazon*|*amazon*visa*|*chase*visa*)
            echo "liabilities:chase amazon visa" ;;
        *apple*card*)
            echo "liabilities:apple card" ;;
        *ally*check*)
            echo "assets:ally checking" ;;
        *ally*sav*)
            echo "assets:ally savings" ;;
        *capital*one*check*)
            echo "assets:capital one checking" ;;
        *)
            echo ""
            return 1 ;;
    esac
}

account_type() {
    case "$1" in
        liabilities:*) echo "credit card" ;;
        assets:*)      echo "bank/checking" ;;
    esac
}

classify_and_append() {
    local csvfile="$1"
    echo "Processing: $csvfile"

    local hledger_account
    if ! hledger_account=$(resolve_account "$csvfile"); then
        echo "ERROR: Cannot determine account from filename '$(basename "$csvfile")'" >&2
        echo "Expected: chase-amazon-visa.csv, apple-card.csv, ally-checking.csv, ally-savings.csv, capital-one-checking.csv" >&2
        return 1
    fi

    local acct_type
    acct_type=$(account_type "$hledger_account")
    echo "  Account: $hledger_account ($acct_type)"

    local csv_content
    csv_content=$(<"$csvfile")

    # Build merchant → category mapping from existing transactions
    # Extracts "description → expense account" pairs for consistency
    local merchant_map
    merchant_map=$(awk '
        /^[0-9][0-9][0-9][0-9]-/ { desc = substr($0, 12) }
        /^    expenses:/ { line = $0; gsub(/^    /, "", line); gsub(/  +-?\$.*/, "", line); if (desc != "") print desc " -> " line }
    ' "$JOURNAL" | sort -u)

    # Ask Claude to parse the CSV and produce hledger journal entries
    local prompt
    prompt=$(cat <<PROMPT
You are a bookkeeping assistant. Below is a CSV statement from: $hledger_account (a $acct_type account).

EXPENSE ACCOUNTS:
$ACCOUNTS

OTHER ACCOUNTS (use only if a transaction is a transfer between accounts):
account assets:ally checking
account assets:ally savings
account assets:capital one checking
account liabilities:chase amazon visa
account liabilities:apple card
account income:salary
account income:other

PREVIOUS MERCHANT CATEGORIZATIONS (use these to stay consistent — always categorize a merchant the same way):
$merchant_map

CSV CONTENT:
$csv_content

INSTRUCTIONS:
- If a merchant matches or closely matches one from the PREVIOUS MERCHANT CATEGORIZATIONS list, use the same expense account.
- Parse every transaction row from the CSV.
- For each transaction, produce a valid hledger journal entry.
- Use your best judgment to assign each transaction to the single most appropriate expense account based on the merchant/description.
- For income/deposits, use the appropriate income account.
- For transfers between accounts (e.g. payment to credit card, transfer between checking/savings), use the appropriate other account — NOT an expense account.
- The balancing account for all non-transfer transactions is: $hledger_account
- Use USD with \$ symbol, e.g. \$50.00
- Format dates as YYYY-MM-DD (infer the year from context if not present).
- Use the merchant/description as the transaction description (clean it up to be human-readable).
- Output ONLY valid hledger journal entries, one blank line between each. No commentary, no explanations, no markdown.
- Do NOT wrap output in code fences (no \`\`\` or \`\`\`hledger or \`\`\`journal). Output raw hledger text only.
- If the CSV is empty or has no transactions, output nothing at all.

SIGN CONVENTIONS (important for hledger):
- This is a $acct_type account ($hledger_account).
- For BANK accounts: expenses are POSITIVE, the bank account posting is NEGATIVE (money leaving). Income is the reverse.
- For CREDIT CARD accounts: expenses are POSITIVE, the liability posting is NEGATIVE. Payments to the card are POSITIVE on the liability (reducing it).
- Each transaction's amounts must sum to zero.

Example output for a bank account:
2026-03-15 Whole Foods
    expenses:food              \$85.32
    assets:ally checking      -\$85.32

Example output for a credit card:
2026-03-16 Netflix
    expenses:subscriptions     \$15.99
    liabilities:chase amazon visa  -\$15.99
PROMPT
    )

    local result
    result=$(echo "$prompt" | claude --print 2>/dev/null)

    # Strip markdown code fences and any non-journal prose
    result=$(echo "$result" | sed '/^```/d')
    # Remove lines that don't look like journal entries (dates, postings, comments, or blank lines)
    result=$(echo "$result" | grep -E '^(;|[0-9]{4}-|    [a-z]|$)' || true)

    if [[ -z "$result" ]]; then
        echo "SKIP: No transactions found in $csvfile"
        return 0
    fi

    # Append to journal with a header comment
    {
        echo ""
        echo "; Imported from $(basename "$csvfile") on $(date +%Y-%m-%d)"
        echo "$result"
    } >> "$JOURNAL"

    echo "Done: $(echo "$result" | grep -c '^[0-9]') transactions imported from $(basename "$csvfile")"
}

# Process specified file or all CSVs
if [[ $# -ge 1 ]]; then
    classify_and_append "$1"
else
    shopt -s nullglob
    csvfiles=("$CSV_DIR"/*.csv "$CSV_DIR"/*.CSV)
    if [[ ${#csvfiles[@]} -eq 0 ]]; then
        echo "No CSV files found in $CSV_DIR/"
        exit 0
    fi
    for f in "${csvfiles[@]}"; do
        classify_and_append "$f"
    done
fi
