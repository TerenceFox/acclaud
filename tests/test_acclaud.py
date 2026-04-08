"""Tests for acclaud pure functions."""
import pytest
import acclaud


class TestCleanResult:
    def test_strips_markdown_fences(self):
        text = "```hledger\n2026-03-15 Groceries\n    expenses:food  $50.00\n    assets:checking  -$50.00\n```"
        result = acclaud.clean_result(text)
        assert "```" not in result
        assert "2026-03-15 Groceries" in result

    def test_keeps_valid_journal_lines(self):
        text = "2026-03-15 Groceries\n    expenses:food  $50.00\n    assets:checking  -$50.00"
        result = acclaud.clean_result(text)
        assert result == text

    def test_strips_commentary(self):
        text = "Here are the transactions:\n2026-03-15 Groceries\n    expenses:food  $50.00\n    assets:checking  -$50.00\nDone!"
        result = acclaud.clean_result(text)
        assert "Here are" not in result
        assert "Done!" not in result
        assert "2026-03-15 Groceries" in result

    def test_empty_input(self):
        assert acclaud.clean_result("") == ""

    def test_preserves_comments(self):
        text = "; imported\n2026-03-15 Groceries\n    expenses:food  $50.00"
        result = acclaud.clean_result(text)
        assert "; imported" in result

    def test_preserves_blank_lines_between_entries(self):
        text = "2026-03-15 Groceries\n    expenses:food  $50.00\n\n2026-03-16 Gas\n    expenses:transportation  $30.00"
        result = acclaud.clean_result(text)
        assert "Groceries" in result
        assert "Gas" in result


class TestResolveAccount:
    @pytest.fixture()
    def config(self):
        return {
            "accounts": {
                "assets": [
                    {"name": "ally checking", "csv_patterns": ["ally*check*"]},
                ],
                "liabilities": [
                    {"name": "chase visa", "csv_patterns": ["chase*", "*chase*visa*"]},
                ],
            }
        }

    def test_matches_asset(self, config):
        assert acclaud.resolve_account("ally-checking-2026.csv", config) == "assets:ally checking"

    def test_matches_liability(self, config):
        assert acclaud.resolve_account("chase-march.csv", config) == "liabilities:chase visa"

    def test_no_match(self, config):
        assert acclaud.resolve_account("unknown-bank.csv", config) is None

    def test_case_insensitive(self, config):
        # resolve_account lowercases the basename before matching
        assert acclaud.resolve_account("Ally-Checking.CSV", config) == "assets:ally checking"

    def test_path_stripped(self, config):
        assert acclaud.resolve_account("/tmp/csv/ally-checking.csv", config) == "assets:ally checking"


class TestBuildMerchantMap:
    def test_parses_journal(self, tmp_path):
        journal = tmp_path / "transactions.journal"
        journal.write_text(
            "2026-03-15 Whole Foods\n"
            "    expenses:food              $85.32\n"
            "    assets:checking           -$85.32\n"
            "\n"
            "2026-03-16 Netflix\n"
            "    expenses:subscriptions     $15.99\n"
            "    liabilities:chase         -$15.99\n"
        )
        original = acclaud.TRANSACTIONS
        acclaud.TRANSACTIONS = str(journal)
        try:
            mapping = acclaud.build_merchant_map()
            assert mapping["Whole Foods"] == "expenses:food"
            assert mapping["Netflix"] == "expenses:subscriptions"
        finally:
            acclaud.TRANSACTIONS = original

    def test_empty_journal(self, tmp_path):
        journal = tmp_path / "transactions.journal"
        journal.write_text("")
        original = acclaud.TRANSACTIONS
        acclaud.TRANSACTIONS = str(journal)
        try:
            assert acclaud.build_merchant_map() == {}
        finally:
            acclaud.TRANSACTIONS = original

    def test_last_categorization_wins(self, tmp_path):
        journal = tmp_path / "transactions.journal"
        journal.write_text(
            "2026-03-01 Starbucks\n"
            "    expenses:food              $5.00\n"
            "    assets:checking           -$5.00\n"
            "\n"
            "2026-03-15 Starbucks\n"
            "    expenses:subscriptions     $5.00\n"
            "    assets:checking           -$5.00\n"
        )
        original = acclaud.TRANSACTIONS
        acclaud.TRANSACTIONS = str(journal)
        try:
            mapping = acclaud.build_merchant_map()
            assert mapping["Starbucks"] == "expenses:subscriptions"
        finally:
            acclaud.TRANSACTIONS = original


class TestFormatCurrency:
    def test_positive(self):
        assert acclaud.format_currency(1234.56) == "$1,234.56"

    def test_negative(self):
        assert acclaud.format_currency(-50.00) == "-$50.00"

    def test_zero(self):
        assert acclaud.format_currency(0) == "$0.00"

    def test_custom_symbol(self):
        assert acclaud.format_currency(100, "EUR ") == "EUR 100.00"

    def test_large_number(self):
        assert acclaud.format_currency(1234567.89) == "$1,234,567.89"
