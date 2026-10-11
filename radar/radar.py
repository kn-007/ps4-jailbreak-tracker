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


# ---------------------------------------------------------
# QUERIES MAIS PRECISAS
# ---------------------------------------------------------

SEARCH_VARIANTS = [
    "PS4 14.00",
    '"PS4" "14.00"',
    "PS4 firmware 14.00",
    "PS4 14.00 exploit",
    "PS4 14.00 jailbreak",
    "PS4 14.00 WebKit",
    "PS4 14.00 kernel",
    "PS4 14.00 offset",
    "PS4 14.00 primitive",
    "PS4 14.00 payload",
    "PS4 14.00 HEN",
    "PS4 14.00 GoldHEN",
    '"14.00" WebKit PS4',
    '"14.00" offset PS4',
    '"14.00" kernel PS4',
]


# ---------------------------------------------------------
# PALAVRAS DE ALTO VALOR (pesquisa real)
# ---------------------------------------------------------

HIGH_VALUE_KEYWORDS = [
    "webkit",
    "kernel",
    "offset",
    "primitive",
    "rop",
    "chain",
    "syscall",
    "arbitrary read",
    "arbitrary write",
    "memory corruption",
    "vulnerability",
    "exploit",
    "payload",
    "bd-jb",
    "pppwn",
]

MEDIUM_VALUE_KEYWORDS = [
    "jailbreak",
    "hen",
    "goldhen",
    "homebrew",
    "debug",
]


def api_get(path):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "PS4-14.00-Radar/4.0"
    }

    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    req = Request(API + path, headers=headers)

    with urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def clean(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def is_target_firmware(text):
    text = clean(text).lower()

    if not re.search(r"\bps4\b", text):
        return False

    # Exige menção clara de 14.00
    patterns = [
        r"\b14\.00\b",
        r"\bfirmware\s*14\.00\b",
        r"\bfw\s*14\.00\b",
        r"\bversion\s*14\.00\b",
    ]

    return any(re.search(p, text) for p in patterns)


def score_item(item):
    blob = clean(" ".join([
        item.get("title", ""),
        item.get("body", ""),
        item.get("summary", ""),
        item.get("name", ""),
        item.get("full_name", "")
    ])).lower()

    if not is_target_firmware(blob):
        return 0, []

    score = 10
    reasons = ["PS4", "14.00"]

    # Alto valor
    for kw in HIGH_VALUE_KEYWORDS:
        if kw in blob:
            score += 5
            if kw not in reasons:
                reasons.append(kw)

    # Médio valor
    for kw in MEDIUM_VALUE_KEYWORDS:
        if kw in blob:
            score += 2
            if kw not in reasons:
                reasons.append(kw)

    # Penaliza pedidos genéricos
    if any(x in blob for x in ["please", "por favor", "when", "quando sai", "support 14.00"]):
        if "exploit" not in blob and "webkit" not in blob and "kernel" not in blob:
            score -= 8

    # Penaliza repos vazios ou só README
    if item.get("type") == "repository":
        if not item.get("summary") or len(item.get("summary", "")) < 20:
            score -= 6

    return max(score, 0), reasons[:12]


def search_query(query, per_page=30):
    q = quote(query + " in:name,description,readme,topics")
    return api_get(f"/search/repositories?q={q}&sort=updated&order=desc&per_page={per_page}")


def search_issues(query, per_page=25):
    q = quote(query)
    return api_get(f"/search/issues?q={q}&sort=updated&order=desc&per_page={per_page}")


def load_existing():
    if not os.path.exists(OUTPUT_PATH):
        return {
            "version": 4,
            "updated_at": None,
            "new_items_this_run": 0,
            "new_items": [],
            "errors": [],
            "items": []
        }

    try:
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "version": 4,
            "updated_at": None,
            "new_items_this_run": 0,
            "new_items": [],
            "errors": [],
            "items": []
        }


def add_repository(items, repo):
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

    score, reasons = score_item(item)

    if score >= 18:  # Filtro mais rigoroso
        item["score"] = score
        item["reasons"] = reasons
        items[item["id"]] = item


def add_issue(items, issue):
    item = {
        "id": f"issue:{issue['id']}",
        "type": "pull_request" if "pull_request" in issue else "issue",
        "title": clean(issue.get("title")),
        "summary": clean(issue.get("body") or "")[:900],
        "author": issue.get("user", {}).get("login", ""),
        "url": issue.get("html_url"),
        "updated_at": issue.get("updated_at"),
        "source": "GitHub"
    }

    score, reasons = score_item(item)

    if score >= 18:
        item["score"] = score
        item["reasons"] = reasons
        items[item["id"]] = item


def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    existing = load_existing()
    old_items = existing.get("items", [])
    old_ids = {item.get("id") for item in old_items if item.get("id")}

    items = {}
    errors = []

    queries = list(SEARCH_VARIANTS)
    for q in config.get("queries", []):
        if q not in queries:
            queries.append(q)

    print(f"Buscas de repositórios: {len(queries)}")

    for query in queries:
        try:
            print(f"→ Repos: {query}")
            data = search_query(query)
            for repo in data.get("items", []):
                add_repository(items, repo)
            time.sleep(0.5)
        except Exception as e:
            errors.append(f"repo: {query}: {e}")

    print(f"\nBuscas de issues: {min(10, len(queries))}")

    for query in queries[:10]:
        try:
            print(f"→ Issues: {query}")
            data = search_issues(query)
            for issue in data.get("items", []):
                add_issue(items, issue)
            time.sleep(6)
        except Exception as e:
            errors.append(f"issue: {query}: {e}")

    new_items = [item for item_id, item in items.items() if item_id not in old_ids]

    merged = {item.get("id"): item for item in old_items if item.get("id")}
    merged.update(items)

    ordered = sorted(
        merged.values(),
        key=lambda x: (x.get("score", 0), x.get("updated_at") or ""),
        reverse=True
    )[:config.get("max_items", 100)]

    result = {
        "version": 4,
        "target_firmware": TARGET_FIRMWARE,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "new_items_this_run": len(new_items),
        "new_items": new_items,
        "searches_performed": len(queries),
        "errors": errors,
        "items": ordered
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 50)
    print(f"Radar PS4 {TARGET_FIRMWARE} finalizado")
    print(f"Itens novos: {len(new_items)}")
    print(f"Itens relevantes: {len(items)}")
    print(f"Total armazenado: {len(ordered)}")
    print("=" * 50)

    if errors:
        print(f"\nAvisos ({len(errors)}):")
        for e in errors:
            print(f" - {e}")


if __name__ == "__main__":
    main()
