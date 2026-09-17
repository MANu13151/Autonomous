"""Discord webhook is the path of least resistance: create one in a channel's
Integrations settings, no bot/OAuth setup needed. Swap this for Telegram/email
later without touching graph.py — it only calls send_alert(message)."""
import requests


def send_alert(webhook_url: str, message: str) -> None:
    resp = requests.post(webhook_url, json={"content": message[:1900]}, timeout=10)
    resp.raise_for_status()
