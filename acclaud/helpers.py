"""Pure utilities, hledger wrappers, and interactive prompts."""
import json
import subprocess
import sys

from acclaud import config


def hledger(*args):
    cmd = ["hledger", "-f", config.JOURNAL] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: hledger failed.\n{result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def hledger_json(*args):
    return json.loads(hledger(*args, "-O", "json"))


def amount_value(amount_obj):
    return float(amount_obj["aquantity"]["floatingPoint"])


def format_currency(value, symbol="$"):
    if value < 0:
        return f"-{symbol}{abs(value):,.2f}"
    return f"{symbol}{value:,.2f}"


def ask(prompt, default=None):
    if default is not None:
        result = input(f"{prompt} [{default}]: ").strip()
        return result if result else default
    return input(f"{prompt}: ").strip()


def yes_no(prompt, default=True):
    suffix = "[Y/n]" if default else "[y/N]"
    result = input(f"{prompt} {suffix}: ").strip().lower()
    if not result:
        return default
    return result in ("y", "yes")
