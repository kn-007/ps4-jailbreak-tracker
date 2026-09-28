#!/usr/bin/env python3
import json
import os
import re
import sys
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


def api_get(path):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "PS4-14v-Radar/1.0"
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = Request(API + path, headers=headers)
    with urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def clean(text):
    return re.sub(r"\\s+", " ", (text or "")).strip()


def score_item(item, config):
    blob = clean(" ".join([
        item.get("title", ""),
        item.get("body", ""),
        item.get("name", ""),
        item.get("full_name", "")
    ])).lower()
    score = 0
    reasons = []

    if "ps4" in blob:
        score += 5
        reasons.append("PS4")
    if "14.00" in blob:
        score += 8
        reasons.append("14.00")
    elif "14.0" in blob:
        score += 4
        reasons.append("14.0")

    for kw in config.get("keywords_optional", []):
        if kw.lower() in blob:
            score += 1
            if kw.lower() not in [r.lower() for r in reasons]:
                reasons.append(kw)

    return score, reasons[:8]


def search_query(query, per_page=20):
    # GitHub search API. Sort by recently updated to keep the radar fresh.
    q = quote(query + " in:name,description,readme")
    return api_get(f"/search/repositories?q={q}&sort=updated&order=desc&per_page={per_page}")


def search_issues(query, per_page=20):
    q = quote(query)
    return api_get(f"/search/issues?q={q}&sort=updated&order=desc&per_page={per_page}")


def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    existing = {"items": [], "updated_at": None, "version": 1}
    if os.path.exists(OUTPUT_PATH):
        try:
            with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            pass

    items = {}
    errors = []

    # Repository discovery.
    for query in config["queries"]:
        try:
            data = search_query(query)
            for repo in data.get("items", []):
                item = {
                    "id": f"repo:{repo['id']}",
                    "type": "repository",
                    "title": clean(repo.get("full_name")),
                    "summary": clean(repo.get("description")),
                    "author": repo.get("owner", {}).get("login", ""),
                    "url": repo.get("html_url"),
                    "updated_at": repo.get("updated_at"),
                    "source": "GitHub"
                }
                score, reasons = score_item(item, config)
                if score >= 9:
                    item["score"] = score
                    item["reasons"] = reasons
                    items[item["id"]] = item
            time.sleep(0.4)
        except Exception as e:
            errors.append(f"repository search: {query}: {e}")

    # Issue / PR discovery.
    for query in config["queries"][:6]:
        try:
            data = search_issues(query)
            for issue in data.get("items", []):
                item = {
                    "id": f"issue:{issue['id']}",
                    "type": "pull_request" if "pull_request" in issue else "issue",
                    "title": clean(issue.get("title")),
                    "summary": clean(issue.get("body"))[:500],
                    "author": issue.get("user", {}).get("login", ""),
                    "url": issue.get("html_url"),
                    "updated_at": issue.get("updated_at"),
                    "source": "GitHub"
                }
                score, reasons = score_item(item, config)
                if score >= 9:
                    item["score"] = score
                    item["reasons"] = reasons
                    items[item["id"]] = item
            time.sleep(0.4)
        except Exception as e:
            errors.append(f"issue search: {query}: {e}")

    old = existing.get("items", [])
    merged = {x.get("id"): x for x in old if x.get("id")}
    merged.update(items)

    ordered = sorted(
        merged.values(),
        key=lambda x: (x.get("updated_at") or "", x.get("score", 0)),
        reverse=True
    )[: config.get("max_items", 100)]

    result = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "new_items_this_run": len(items),
        "errors": errors,
        "items": ordered
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Radar concluído: {len(items)} itens relevantes encontrados nesta execução.")
    if errors:
        print(f"Avisos: {len(errors)}")


if __name__ == "__main__":
    main()
