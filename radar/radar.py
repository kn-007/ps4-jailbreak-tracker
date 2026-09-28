#!/usr/bin/env python3
import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RADAR_DIR = os.path.join(ROOT, "radar")
CONFIG_PATH = os.path.join(RADAR_DIR, "config.json")
OUTPUT_PATH = os.path.join(RADAR_DIR, "radar.json")

API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")

TARGET_FIRMWARE = "14.00"


def api_get(path):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "PS4-14.00-Radar/1.0"
    }

    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    req = Request(API + path, headers=headers)

    with urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def clean(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def is_target_firmware(text):
    """
    Aceita somente PS4 14.00.

    Exemplos aceitos:
      PS4 14.00
      PS4 firmware 14.00
      firmware 14.00 PS4

    Exemplos rejeitados:
      PS4 14.0
      PS4 13.00
      PS4 15.00
      PS4 14.01
    """

    text = clean(text).lower()

    has_ps4 = re.search(r"\bps4\b", text)
    has_1400 = re.search(r"\b14\.00\b", text)

    return bool(has_ps4 and has_1400)


def score_item(item, config):
    blob = clean(" ".join([
        item.get("title", ""),
        item.get("body", ""),
        item.get("summary", ""),
        item.get("name", ""),
        item.get("full_name", "")
    ])).lower()

    if not is_target_firmware(blob):
        return 0, []

    score = 0
    reasons = []

    score += 5
    reasons.append("PS4")

    score += 10
    reasons.append("14.00")

    for keyword in config.get("keywords_optional", []):
        keyword = keyword.lower()

        if keyword in blob:
            score += 1

            if keyword not in [r.lower() for r in reasons]:
                reasons.append(keyword)

    return score, reasons[:8]


def search_query(query, per_page=20):
    q = quote(query + " in:name,description,readme")

    return api_get(
        f"/search/repositories?q={q}"
        f"&sort=updated&order=desc&per_page={per_page}"
    )


def search_issues(query, per_page=20):
    q = quote(query)

    return api_get(
        f"/search/issues?q={q}"
        f"&sort=updated&order=desc&per_page={per_page}"
    )


def load_existing():
    if not os.path.exists(OUTPUT_PATH):
        return {
            "version": 1,
            "updated_at": None
