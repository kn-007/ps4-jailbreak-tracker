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
# VARIAÇÕES DE BUSCA
# ---------------------------------------------------------

SEARCH_VARIANTS = [
    "PS4 14.00",
    '"PS4" "14.00"',
    "PS4 firmware 14.00",
    "PS4 exploit 14.00",
    "PS4 jailbreak 14.00",
    "PS4 HEN 14.00",
    "PS4 payload 14.00",
    "PS4 WebKit 14.00",
    "PS4 kernel 14.00",
    "PS4 GoldHEN 14.00",
    "PS4 exploit firmware 14.00",
    "PS4 jailbreak firmware 14.00",
]


def api_get(path):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "PS4-14.00-Radar/2.0"
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

    score = 15
    reasons = ["PS4", "14.00"]

    # Termos importantes recebem pontuação extra
    important_keywords = [
        "exploit",
        "jailbreak",
        "hen",
        "goldhen",
        "payload",
        "webkit",
        "kernel",
        "firmware",
        "vulnerability",
        "vulnerabilidade",
        "pppwn",
        "eta",
        "hack",
        "homebrew",
        "debug",
        "bd-jb"
    ]

    for keyword in important_keywords:
        if keyword in blob:
            score += 2

            if keyword not in [r.lower() for r in reasons]:
                reasons.append(keyword)

    # Mantém também as palavras configuradas no config.json
    for keyword in config.get("keywords_optional", []):
        keyword = keyword.lower().strip()

        if keyword and keyword in blob:
            score += 1

            if keyword not in [r.lower() for r in reasons]:
                reasons.append(keyword)

    return score, reasons[:10]


def search_query(query, per_page=30):
    q = quote(
        query +
        " in:name,description,readme,topics"
    )

    return api_get(
        f"/search/repositories?q={q}"
        f"&sort=updated&order=desc&per_page={per_page}"
    )


def search_issues(query, per_page=30):
    q = quote(query)

    return api_get(
        f"/search/issues?q={q}"
        f"&sort=updated&order=desc&per_page={per_page}"
    )


def load_existing():
    if not os.path.exists(OUTPUT_PATH):
        return {
            "version": 2,
            "updated_at": None,
            "new_items_this_run": 0,
            "errors": [],
            "items": []
        }

    try:
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return {
            "version": 2,
            "updated_at": None,
            "new_items_this_run": 0,
            "errors": [],
            "items": []
        }


def add_repository(items, repo, config):
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

    if score >= 15:
        item["score"] = score
        item["reasons"] = reasons
        items[item["id"]] = item


def add_issue(items, issue, config):
    item = {
        "id": f"issue:{issue['id']}",
        "type": (
            "pull_request"
            if "pull_request" in issue
            else "issue"
        ),
        "title": clean(issue.get("title")),
        "summary": clean(issue.get("body"))[:1000],
        "author": issue.get("user", {}).get("login", ""),
        "url": issue.get("html_url"),
        "updated_at": issue.get("updated_at"),
        "source": "GitHub"
    }

    score, reasons = score_item(item, config)

    if score >= 15:
        item["score"] = score
        item["reasons"] = reasons
        items[item["id"]] = item


def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    existing = load_existing()

    old_items = existing.get("items", [])

    old_ids = {
        item.get("id")
        for item in old_items
        if item.get("id")
    }

    items = {}
    errors = []

    # -----------------------------------------------------
    # BUSCA DE REPOSITÓRIOS
    # -----------------------------------------------------

    queries = []

    # Primeiro usa as buscas novas
    queries.extend(SEARCH_VARIANTS)

    # Depois adiciona as buscas personalizadas do config.json
    for query in config.get("queries", []):
        if query not in queries:
            queries.append(query)

    print(f"Buscas de repositórios: {len(queries)}")

    for query in queries:
        try:
            print(f"Pesquisando repositórios: {query}")

            data = search_query(query)

            for repo in data.get("items", []):
                add_repository(items, repo, config)

            time.sleep(0.4)

        except Exception as e:
            errors.append(
                f"repository search: {query}: {e}"
            )

    # -----------------------------------------------------
    # BUSCA DE ISSUES E PULL REQUESTS
    # -----------------------------------------------------

    issue_queries = queries[:12]

    print(f"Buscas de issues: {len(issue_queries)}")

    for query in issue_queries:
        try:
            print(f"Pesquisando issues: {query}")

            data = search_issues(query)

            for issue in data.get("items", []):
                add_issue(items, issue, config)

            time.sleep(0.4)

        except Exception as e:
            errors.append(
                f"issue search: {query}: {e}"
            )

    # -----------------------------------------------------
    # NOVOS RESULTADOS
    # -----------------------------------------------------

    new_items = [
        item
        for item_id, item in items.items()
        if item_id not in old_ids
    ]

    # -----------------------------------------------------
    # MESCLAR RESULTADOS ANTIGOS + NOVOS
    # -----------------------------------------------------

    merged = {
        item.get("id"): item
        for item in old_items
        if item.get("id")
    }

    merged.update(items)

    # -----------------------------------------------------
    # ORDENAR
    # -----------------------------------------------------

    ordered = sorted(
        merged.values(),
        key=lambda item: (
            item.get("score", 0),
            item.get("updated_at") or ""
        ),
        reverse=True
    )

    ordered = ordered[:config.get("max_items", 150)]

    # -----------------------------------------------------
    # RESULTADO FINAL
    # -----------------------------------------------------

    result = {
        "version": 2,
        "target_firmware": TARGET_FIRMWARE,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "new_items_this_run": len(new_items),
        "searches_performed": len(queries),
        "errors": errors,
        "items": ordered
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(
            result,
            f,
            ensure_ascii=False,
            indent=2
        )

    # -----------------------------------------------------
    # LOG
    # -----------------------------------------------------

    print("")
    print("=" * 50)
    print(f"Radar PS4 {TARGET_FIRMWARE} concluído.")
    print(f"Buscas realizadas: {len(queries)}")
    print(f"Itens novos: {len(new_items)}")
    print(f"Itens relevantes encontrados: {len(items)}")
    print(f"Itens armazenados: {len(ordered)}")
    print("=" * 50)

    if errors:
        print(f"Avisos: {len(errors)}")


if __name__ == "__main__":
    main()
