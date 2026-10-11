"""Regenerate the project sections of README.md from the GitHub API.

Featured  : public repos tagged with the `featured` topic (fallback: most-starred).
Recent    : most recently pushed public repos.

Runs in GitHub Actions; only standard library is used.
"""

import json
import os
import re
import urllib.request
from datetime import datetime
from pathlib import Path

USER = os.environ.get("GH_USER", "monitari")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
README = Path(__file__).resolve().parent.parent / "README.md"

FEATURED_TOPIC = "featured"
FEATURED_LIMIT = 6
RECENT_LIMIT = 5


def fetch_repos(user: str) -> list[dict]:
    repos, page = [], 1
    while True:
        url = (
            f"https://api.github.com/users/{user}/repos"
            f"?type=owner&sort=pushed&per_page=100&page={page}"
        )
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
        if TOKEN:
            req.add_header("Authorization", f"Bearer {TOKEN}")
        with urllib.request.urlopen(req) as resp:
            batch = json.load(resp)
        if not batch:
            return repos
        repos.extend(batch)
        page += 1


def eligible(repos: list[dict], user: str) -> list[dict]:
    return [
        r for r in repos
        if not r.get("fork")
        and not r.get("archived")
        and not r.get("private")
        and r["name"].lower() != user.lower()  # skip the profile repo itself
    ]


def clean(text: str | None) -> str:
    text = (text or "").replace("|", "\\|").replace("\n", " ").strip()
    return text or "—"


def date(iso: str) -> str:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%Y-%m-%d")


def featured_table(repos: list[dict]) -> str:
    picked = [r for r in repos if FEATURED_TOPIC in r.get("topics", [])]
    if not picked:
        picked = sorted(repos, key=lambda r: (r["stargazers_count"], r["pushed_at"]), reverse=True)
    picked = picked[:FEATURED_LIMIT]
    if not picked:
        return "_No public projects yet._"

    rows = ["| Project | Description | Stack | ⭐ |", "|---|---|---|---|"]
    for r in picked:
        lang = f"`{r['language']}`" if r.get("language") else "—"
        rows.append(
            f"| [**{r['name']}**]({r['html_url']}) | {clean(r.get('description'))} "
            f"| {lang} | {r['stargazers_count']} |"
        )
    return "\n".join(rows)


def recent_list(repos: list[dict]) -> str:
    picked = sorted(repos, key=lambda r: r["pushed_at"], reverse=True)[:RECENT_LIMIT]
    if not picked:
        return "_Nothing here yet._"
    lines = []
    for r in picked:
        desc = f" — {clean(r['description'])}" if r.get("description") else ""
        lines.append(
            f"- [{r['name']}]({r['html_url']}){desc} "
            f"<sub>· updated {date(r['pushed_at'])}</sub>"
        )
    return "\n".join(lines)


def replace_section(text: str, name: str, body: str) -> str:
    pattern = re.compile(
        rf"(<!-- {name}:START -->)(.*?)(<!-- {name}:END -->)", re.DOTALL
    )
    if not pattern.search(text):
        raise SystemExit(f"Marker <!-- {name}:START/END --> not found in README.md")
    return pattern.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(3)}", text)


def main() -> None:
    repos = eligible(fetch_repos(USER), USER)
    text = README.read_text(encoding="utf-8")
    new = replace_section(text, "FEATURED", featured_table(repos))
    new = replace_section(new, "RECENT", recent_list(repos))
    if new != text:
        README.write_text(new, encoding="utf-8")
        print("README.md updated")
    else:
        print("No changes")


if __name__ == "__main__":
    main()
