"""Shared HTTP helpers for the collector scripts.

Collectors must never crash a research run, so these return (value, error) instead of raising.
"""
import datetime
import json
import urllib.error
import urllib.request

USER_AGENT = "tech-research-skill/1.0"


def get_text(url, timeout=20, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace"), None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        return None, f"HTTP {e.code} {e.reason} {body}".strip()
    except Exception as e:  # network errors, timeouts, bad URLs
        return None, f"{type(e).__name__}: {e}"


def get_json(url, timeout=20, headers=None):
    text, err = get_text(url, timeout, headers)
    if err:
        return None, err
    try:
        return json.loads(text), None
    except json.JSONDecodeError as e:
        return None, f"invalid JSON: {e}"


def today():
    return datetime.date.today().isoformat()
