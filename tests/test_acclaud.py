"""Tests for acclaud pure functions."""
from datetime import date
from decimal import Decimal

import pytest
from acclaud import config, simplefin
from acclaud.import_csv import (
    clean_result,
    resolve_account,
    build_merchant_map,
    existing_simplefin_ids,
    parse_import_args,
    resolve_date_range,
    ImportOpts,
    _account_is_simplefin_managed,
)
from acclaud.helpers import format_currency


class TestCleanResult:
    def test_strips_markdown_fences(self):
        text = "```hledger\n2026-03-15 Groceries\n    expenses:food  $50.00\n    assets:checking  -$50.00\n```"
        result = clean_result(text)
        assert "```" not in result
        assert "2026-03-15 Groceries" in result

    def test_keeps_valid_journal_lines(self):
        text = "2026-03-15 Groceries\n    expenses:food  $50.00\n    assets:checking  -$50.00"
        result = clean_result(text)
        assert result == text

    def test_strips_commentary(self):
        text = "Here are the transactions:\n2026-03-15 Groceries\n    expenses:food  $50.00\n    assets:checking  -$50.00\nDone!"
        result = clean_result(text)
        assert "Here are" not in result
        assert "Done!" not in result
        assert "2026-03-15 Groceries" in result

    def test_empty_input(self):
        assert clean_result("") == ""

    def test_preserves_comments(self):
        text = "; imported\n2026-03-15 Groceries\n    expenses:food  $50.00"
        result = clean_result(text)
        assert "; imported" in result

    def test_preserves_blank_lines_between_entries(self):
        text = "2026-03-15 Groceries\n    expenses:food  $50.00\n\n2026-03-16 Gas\n    expenses:transportation  $30.00"
        result = clean_result(text)
        assert "Groceries" in result
        assert "Gas" in result


class TestResolveAccount:
    @pytest.fixture()
    def cfg(self):
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

    def test_matches_asset(self, cfg):
        assert resolve_account("ally-checking-2026.csv", cfg) == "assets:ally checking"

    def test_matches_liability(self, cfg):
        assert resolve_account("chase-march.csv", cfg) == "liabilities:chase visa"

    def test_no_match(self, cfg):
        assert resolve_account("unknown-bank.csv", cfg) is None

    def test_case_insensitive(self, cfg):
        assert resolve_account("Ally-Checking.CSV", cfg) == "assets:ally checking"

    def test_path_stripped(self, cfg):
        assert resolve_account("/tmp/csv/ally-checking.csv", cfg) == "assets:ally checking"


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
        original = config.TRANSACTIONS
        config.TRANSACTIONS = str(journal)
        try:
            mapping = build_merchant_map()
            assert mapping["Whole Foods"] == "expenses:food"
            assert mapping["Netflix"] == "expenses:subscriptions"
        finally:
            config.TRANSACTIONS = original

    def test_empty_journal(self, tmp_path):
        journal = tmp_path / "transactions.journal"
        journal.write_text("")
        original = config.TRANSACTIONS
        config.TRANSACTIONS = str(journal)
        try:
            assert build_merchant_map() == {}
        finally:
            config.TRANSACTIONS = original

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
        original = config.TRANSACTIONS
        config.TRANSACTIONS = str(journal)
        try:
            mapping = build_merchant_map()
            assert mapping["Starbucks"] == "expenses:subscriptions"
        finally:
            config.TRANSACTIONS = original


class TestFormatCurrency:
    def test_positive(self):
        assert format_currency(1234.56) == "$1,234.56"

    def test_negative(self):
        assert format_currency(-50.00) == "-$50.00"

    def test_zero(self):
        assert format_currency(0) == "$0.00"

    def test_custom_symbol(self):
        assert format_currency(100, "EUR ") == "EUR 100.00"

    def test_large_number(self):
        assert format_currency(1234567.89) == "$1,234,567.89"


class TestCleanResultSimpleFINComment:
    def test_preserves_indented_simplefin_id_comment(self):
        text = (
            "2026-04-12 Whole Foods\n"
            "    expenses:food              $45.99\n"
            "    assets:ally checking      -$45.99\n"
            "    ; simplefin-id:txn_abc"
        )
        result = clean_result(text)
        assert "simplefin-id:txn_abc" in result


class TestResolveSimpleFINAccount:
    @pytest.fixture()
    def cfg(self):
        return {"accounts": {
            "assets": [
                {"name": "ally checking", "simplefin_name": "Ally Checking"},
                {"name": "cash"},  # unmapped
            ],
            "liabilities": [
                {"name": "chase visa", "simplefin_name": "Chase Sapphire"},
            ],
        }}

    def test_matches_asset(self, cfg):
        assert simplefin.resolve_simplefin_account("Ally Checking", cfg) == "assets:ally checking"

    def test_matches_liability(self, cfg):
        assert simplefin.resolve_simplefin_account("Chase Sapphire", cfg) == "liabilities:chase visa"

    def test_case_insensitive(self, cfg):
        assert simplefin.resolve_simplefin_account("ally checking", cfg) == "assets:ally checking"
        assert simplefin.resolve_simplefin_account("CHASE SAPPHIRE", cfg) == "liabilities:chase visa"

    def test_no_match(self, cfg):
        assert simplefin.resolve_simplefin_account("Something Else", cfg) is None

    def test_empty_name(self, cfg):
        assert simplefin.resolve_simplefin_account("", cfg) is None


class TestSimpleFINNormalize:
    @pytest.fixture()
    def cfg(self):
        return {"accounts": {
            "assets": [{"name": "ally checking", "simplefin_name": "Checking"}],
            "liabilities": [{"name": "chase visa", "simplefin_name": "Visa"}],
        }}

    def test_asset_transaction(self, cfg):
        payload = {"accounts": [{
            "id": "acc1", "name": "Checking", "org": {"name": "Ally"},
            "transactions": [{
                "id": "t1", "posted": 1712000000, "amount": "-45.99",
                "description": "WHOLE FOODS", "payee": "Whole Foods", "memo": "",
            }],
        }]}
        txns = simplefin.normalize(payload, cfg)
        assert len(txns) == 1
        t = txns[0]
        assert t.account == "assets:ally checking"
        assert t.amount == Decimal("-45.99")  # asset — no sign flip
        assert t.transaction_id == "t1"
        assert t.description == "Whole Foods"  # payee preferred
        # 1712000000 UTC = 2024-04-01 21:33:20
        assert t.date == date(2024, 4, 1)
        assert t.source == "simplefin"

    def test_liability_sign_flip(self, cfg):
        payload = {"accounts": [{
            "id": "acc2", "name": "Visa", "org": {"name": "Chase"},
            "transactions": [
                {"id": "p1", "posted": 1712000000, "amount": "89.50",
                 "description": "Restaurant", "payee": "", "memo": ""},
                {"id": "p2", "posted": 1712086400, "amount": "-200.00",
                 "description": "AUTOPAY PAYMENT", "payee": "", "memo": ""},
            ],
        }]}
        txns = simplefin.normalize(payload, cfg)
        assert len(txns) == 2
        # Purchase: SimpleFIN +89.50 → hledger liability posting should be -89.50
        assert txns[0].amount == Decimal("-89.50")
        # Payment: SimpleFIN -200 → hledger liability posting should be +200
        assert txns[1].amount == Decimal("200.00")

    def test_unmapped_account_skipped(self, cfg, capsys):
        payload = {"accounts": [{
            "id": "x", "name": "Unmapped", "org": {"name": "?"},
            "transactions": [{"id": "t", "posted": 0, "amount": "1", "description": "x"}],
        }]}
        assert simplefin.normalize(payload, cfg) == []
        captured = capsys.readouterr()
        assert "Unmapped" in captured.err

    def test_description_fallback(self, cfg):
        payload = {"accounts": [{
            "id": "acc1", "name": "Checking", "org": {"name": "Ally"},
            "transactions": [
                {"id": "a", "posted": 0, "amount": "1", "payee": "P", "description": "D", "memo": "M"},
                {"id": "b", "posted": 0, "amount": "1", "payee": "", "description": "D", "memo": "M"},
                {"id": "c", "posted": 0, "amount": "1", "payee": "", "description": "", "memo": "M"},
                {"id": "d", "posted": 0, "amount": "1", "payee": "", "description": "", "memo": ""},
            ],
        }]}
        txns = simplefin.normalize(payload, cfg)
        assert [t.description for t in txns] == ["P", "D", "M", "(no description)"]

    def test_duplicate_simplefin_name_warning(self, capsys):
        cfg = {"accounts": {
            "assets": [{"name": "a1", "simplefin_name": "Same"}],
            "liabilities": [{"name": "l1", "simplefin_name": "Same"}],
        }}
        simplefin.normalize({"accounts": []}, cfg)
        assert "Same" in capsys.readouterr().err

    def test_skips_malformed_amount(self, cfg, capsys):
        payload = {"accounts": [{
            "id": "acc1", "name": "Checking", "org": {"name": "Ally"},
            "transactions": [
                {"id": "ok", "posted": 0, "amount": "1.00", "description": "ok"},
                {"id": "bad", "posted": 0, "amount": "not-a-number", "description": "bad"},
            ],
        }]}
        txns = simplefin.normalize(payload, cfg)
        assert [t.transaction_id for t in txns] == ["ok"]


class TestExistingSimpleFINIds:
    def test_extracts_ids(self, tmp_path):
        j = tmp_path / "t.journal"
        j.write_text(
            "2026-04-01 X\n"
            "    expenses:food $5\n"
            "    assets:c -$5\n"
            "    ; simplefin-id:txn_abc\n"
            "\n"
            "2026-04-02 Y\n"
            "    expenses:food $3\n"
            "    assets:c -$3\n"
            "    ; simplefin-id:txn_def\n"
        )
        assert existing_simplefin_ids(str(j)) == {"txn_abc", "txn_def"}

    def test_missing_file_returns_empty_set(self, tmp_path):
        assert existing_simplefin_ids(str(tmp_path / "nope.journal")) == set()

    def test_journal_without_tags(self, tmp_path):
        j = tmp_path / "t.journal"
        j.write_text("2026-04-01 X\n    expenses:food $5\n    assets:c -$5\n")
        assert existing_simplefin_ids(str(j)) == set()


class TestParseImportArgs:
    def test_dry_run(self):
        opts, pos = parse_import_args(["--dry-run"])
        assert opts.dry_run is True
        assert pos == []

    def test_from_to_spaced(self):
        opts, _ = parse_import_args(["--from", "2026-03-01", "--to", "2026-03-31"])
        assert opts.date_from == date(2026, 3, 1)
        assert opts.date_to == date(2026, 3, 31)

    def test_from_to_equals(self):
        opts, _ = parse_import_args(["--from=2026-03-01", "--to=2026-03-31"])
        assert opts.date_from == date(2026, 3, 1)
        assert opts.date_to == date(2026, 3, 31)

    def test_positional_preserved(self):
        _, pos = parse_import_args(["--dry-run", "file.csv"])
        assert pos == ["file.csv"]

    def test_unknown_flag_exits(self):
        with pytest.raises(SystemExit):
            parse_import_args(["--bogus"])

    def test_invalid_date_exits(self):
        with pytest.raises(SystemExit):
            parse_import_args(["--from", "not-a-date"])


class TestResolveDateRange:
    def test_default_is_first_of_month_to_today(self, monkeypatch):
        import acclaud.import_csv as ic
        class FakeDate(date):
            @classmethod
            def today(cls):
                return date(2026, 4, 16)
        monkeypatch.setattr(ic, "date", FakeDate)
        d_from, d_to = resolve_date_range(ImportOpts())
        assert d_from == date(2026, 4, 1)
        assert d_to == date(2026, 4, 16)

    def test_override_via_opts(self):
        opts = ImportOpts(date_from=date(2026, 2, 1), date_to=date(2026, 2, 28))
        d_from, d_to = resolve_date_range(opts)
        assert d_from == date(2026, 2, 1)
        assert d_to == date(2026, 2, 28)

    def test_from_after_to_errors(self):
        opts = ImportOpts(date_from=date(2026, 3, 31), date_to=date(2026, 3, 1))
        with pytest.raises(SystemExit):
            resolve_date_range(opts)


class TestAccountIsSimpleFINManaged:
    @pytest.fixture()
    def cfg(self):
        return {"accounts": {
            "assets": [
                {"name": "ally checking", "simplefin_name": "Ally Checking"},
                {"name": "ally savings"},  # no simplefin_name
            ],
            "liabilities": [
                {"name": "chase visa", "simplefin_name": "Chase Sapphire"},
                {"name": "old loan"},
            ],
        }}

    def test_asset_with_mapping(self, cfg):
        assert _account_is_simplefin_managed("assets:ally checking", cfg) is True

    def test_asset_without_mapping(self, cfg):
        assert _account_is_simplefin_managed("assets:ally savings", cfg) is False

    def test_liability_with_mapping(self, cfg):
        assert _account_is_simplefin_managed("liabilities:chase visa", cfg) is True

    def test_liability_without_mapping(self, cfg):
        assert _account_is_simplefin_managed("liabilities:old loan", cfg) is False

    def test_unknown_account(self, cfg):
        assert _account_is_simplefin_managed("assets:nonexistent", cfg) is False

    def test_empty_simplefin_name_is_not_managed(self):
        cfg = {"accounts": {"assets": [{"name": "a", "simplefin_name": ""}], "liabilities": []}}
        assert _account_is_simplefin_managed("assets:a", cfg) is False
