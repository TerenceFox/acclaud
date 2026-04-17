"""SimpleFIN API client: credentials, token exchange, fetch, normalization."""
import base64
import binascii
import calendar
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

import requests


CREDENTIALS_PATH = os.path.expanduser("~/.config/acclaud/credentials")
ENV_VAR = "SIMPLEFIN_ACCESS_URL"
HTTP_TIMEOUT = 30


class SimpleFINError(Exception):
    pass


def get_access_url():
    """Return access URL from env or credentials file, or None."""
    env = os.environ.get(ENV_VAR)
    if env:
        return env.strip()
    if os.path.isfile(CREDENTIALS_PATH):
        try:
            with open(CREDENTIALS_PATH, encoding="utf-8") as f:
                val = f.read().strip()
            return val or None
        except OSError:
            return None
    return None


def is_configured():
    return get_access_url() is not None


def exchange_setup_token(setup_token):
    """Base64-decode the setup token, POST to that URL, return the access URL."""
    try:
        url = base64.b64decode(setup_token).decode("utf-8").strip()
    except (binascii.Error, UnicodeDecodeError, ValueError) as e:
        raise SimpleFINError(f"Malformed setup token: {e}")
    if not url.startswith("http"):
        raise SimpleFINError("Setup token did not decode to a valid URL.")
    try:
        resp = requests.post(url, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise SimpleFINError(f"Token exchange request failed: {e}")
    access_url = resp.text.strip()
    if not access_url.startswith("http"):
        raise SimpleFINError(f"Unexpected response from SimpleFIN: {access_url[:100]!r}")
    return access_url


def write_credentials(access_url):
    """Write access URL to ~/.config/acclaud/credentials at mode 0600."""
    os.makedirs(os.path.dirname(CREDENTIALS_PATH), mode=0o700, exist_ok=True)
    # Use os.open with explicit mode to avoid a transient 0644 window.
    fd = os.open(CREDENTIALS_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(access_url.rstrip() + "\n")


@dataclass
class Transaction:
    date: date
    amount: Decimal
    description: str
    account: str           # e.g. "assets:ally checking"
    transaction_id: str
    source: str            # "simplefin" | "csv"


def _pick_description(txn):
    for key in ("payee", "description", "memo"):
        val = (txn.get(key) or "").strip()
        if val:
            return val
    return "(no description)"


def resolve_simplefin_account(sf_name, cfg):
    """Case-insensitive match of SimpleFIN account name to an hledger account."""
    if not sf_name:
        return None
    target = sf_name.strip().lower()
    for acct in cfg.get("accounts", {}).get("assets", []):
        if (acct.get("simplefin_name") or "").strip().lower() == target:
            return f"assets:{acct['name']}"
    for acct in cfg.get("accounts", {}).get("liabilities", []):
        if (acct.get("simplefin_name") or "").strip().lower() == target:
            return f"liabilities:{acct['name']}"
    return None


def _warn_duplicate_mappings(cfg):
    seen = {}
    all_accts = (
        [("assets", a) for a in cfg.get("accounts", {}).get("assets", [])]
        + [("liabilities", a) for a in cfg.get("accounts", {}).get("liabilities", [])]
    )
    for section, a in all_accts:
        sf = (a.get("simplefin_name") or "").strip().lower()
        if not sf:
            continue
        if sf in seen:
            print(
                f"Warning: simplefin_name {a.get('simplefin_name')!r} is set on both "
                f"{seen[sf]} and {section}:{a['name']}. First match wins. "
                f"Remove the duplicate in config.json.",
                file=sys.stderr,
            )
        else:
            seen[sf] = f"{section}:{a['name']}"


def fetch_transactions(access_url, start, end):
    """GET /accounts?start-date=<utc>&end-date=<utc> and return decoded JSON."""
    start_ts = calendar.timegm(
        datetime(start.year, start.month, start.day, 0, 0, 0, tzinfo=timezone.utc).utctimetuple()
    )
    end_ts = calendar.timegm(
        datetime(end.year, end.month, end.day, 23, 59, 59, tzinfo=timezone.utc).utctimetuple()
    )
    url = access_url.rstrip("/") + "/accounts"
    try:
        resp = requests.get(
            url,
            params={"start-date": start_ts, "end-date": end_ts},
            timeout=HTTP_TIMEOUT,
        )
    except (requests.Timeout, requests.ConnectionError) as e:
        raise SimpleFINError(
            f"Could not reach SimpleFIN ({e}). Retry, or provide a CSV file: "
            "acclaud import transactions.csv"
        )
    except requests.RequestException as e:
        raise SimpleFINError(f"SimpleFIN request failed: {e}")
    if resp.status_code == 401 or resp.status_code == 403:
        raise SimpleFINError(
            "SimpleFIN access URL is invalid or expired. "
            "Run 'acclaud setup' or check SIMPLEFIN_ACCESS_URL."
        )
    if not resp.ok:
        raise SimpleFINError(f"SimpleFIN returned HTTP {resp.status_code}: {resp.text[:200]}")
    try:
        return resp.json()
    except ValueError as e:
        raise SimpleFINError(f"SimpleFIN response was not JSON: {e}")


def list_accounts(access_url):
    """Fetch live account metadata (id, name, org) for setup-time discovery.

    Uses a 1-day date range to minimize data transferred — we only care about
    which accounts exist, not their transactions.
    """
    today = date.today()
    payload = fetch_transactions(access_url, today, today)
    out = []
    for a in payload.get("accounts", []):
        out.append({
            "id": a.get("id", ""),
            "name": a.get("name", ""),
            "org": (a.get("org") or {}).get("name", ""),
        })
    return out


def normalize(payload, cfg):
    """Convert SimpleFIN /accounts JSON into a list of Transaction objects."""
    _warn_duplicate_mappings(cfg)
    out = []
    for account in payload.get("accounts", []):
        sf_name = account.get("name", "")
        hledger_account = resolve_simplefin_account(sf_name, cfg)
        if hledger_account is None:
            print(
                f"Warning: no simplefin_name mapping for SimpleFIN account "
                f"{sf_name!r} — skipping its transactions. "
                f"Run 'acclaud setup' to map it to an account.",
                file=sys.stderr,
            )
            continue
        for txn in account.get("transactions", []):
            posted = txn.get("posted")
            if posted is None:
                continue
            txn_date = datetime.fromtimestamp(int(posted), tz=timezone.utc).date()
            amount_str = txn.get("amount", "0")
            try:
                amount = Decimal(str(amount_str))
            except (InvalidOperation, ValueError):
                print(f"Warning: could not parse amount {amount_str!r} — skipping transaction.", file=sys.stderr)
                continue
            # Sign-flip for liabilities so downstream rendering rule is uniform:
            # source_account posting = amount, balancing posting = -amount.
            # SimpleFIN reports +amount = money entering the account; for a credit
            # card, a purchase (balance owed up) comes as +, but in hledger with
            # liability-as-negative convention that posting should be -.
            if hledger_account.startswith("liabilities:"):
                amount = -amount
            out.append(Transaction(
                date=txn_date,
                amount=amount,
                description=_pick_description(txn),
                account=hledger_account,
                transaction_id=str(txn.get("id", "")),
                source="simplefin",
            ))
    return out
