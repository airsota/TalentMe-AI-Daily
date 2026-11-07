#!/usr/bin/env python3
"""Build the TalentMe AI Daily repository from the website content.

For every date that has a news / papers / projects edition, this script writes:

    digests/YYYY-MM-DD.en.md
    digests/YYYY-MM-DD.zh.md

and rebuilds `README.md` with a "Latest" table, a full archive, and UTM-tagged
links back to the formatted editions on talentme.airsota.com.

Usage
-----
  python3 scripts/sync_daily.py                 # sync content + rebuild README
  python3 scripts/sync_daily.py --dry-run
  python3 scripts/sync_daily.py --check         # exit 1 if out of date
  python3 scripts/sync_daily.py --index-only    # rebuild README from digests/
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = Path(
    os.environ.get(
        "TALENTME_CONTENT_ROOT",
        "/home/suiyaoc/TalentMe/website/frontend/content",
    )
)

SITE = "https://talentme.airsota.com"
UTM = "utm_source=github&utm_medium=daily&utm_campaign=ai-daily"
CATEGORIES = ("news", "papers", "projects")
DATE_FILE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.(en|zh)\.md$")
FM_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n", re.DOTALL)

LABELS = {
    "en": {
        "news": "📰 News",
        "papers": "📄 Papers",
        "projects": "🚀 Projects",
        "intro": "AI news, papers, and open-source projects — curated for ML engineers.",
        "read": "Read the formatted edition on TalentMe",
        "practice": "Practice with 1,898 free flashcards",
        "coach": "Book a 1:1 mock interview",
        "watch": "Watch → Releases to get each daily digest.",
    },
    "zh": {
        "news": "📰 行业动态",
        "papers": "📄 前沿论文",
        "projects": "🚀 开源项目",
        "intro": "面向 AI/ML 工程师的每日资讯、论文与开源项目精选。",
        "read": "在 TalentMe 阅读排版版",
        "practice": "练习 1,898 张免费闪卡",
        "coach": "预约 1v1 模拟面试",
        "watch": "Watch → Releases，每天接收新一期日报。",
    },
}


# --------------------------------------------------------------------------- #
# Frontmatter
# --------------------------------------------------------------------------- #
def parse_frontmatter(raw: str) -> tuple[dict, str]:
    match = FM_RE.match(raw)
    if not match:
        return {}, raw

    data: dict = {}
    lines = match.group(1).splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        item = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$", line)
        if not item:
            index += 1
            continue
        key, rest = item.group(1), item.group(2).strip()

        if rest in (">", ">-", "|", "|-"):
            parts: List[str] = []
            index += 1
            while index < len(lines):
                candidate = lines[index]
                if candidate.strip() and not candidate.startswith((" ", "\t")):
                    break
                if candidate.strip():
                    parts.append(candidate.strip())
                index += 1
            data[key] = " ".join(parts)
            continue

        if rest.startswith("[") and rest.endswith("]"):
            data[key] = [
                value.strip().strip("\"'")
                for value in rest[1:-1].split(",")
                if value.strip()
            ]
        elif len(rest) >= 2 and rest[0] == rest[-1] and rest[0] in "\"'":
            data[key] = rest[1:-1]
        else:
            data[key] = rest
        index += 1

    return data, raw[match.end():]


def pick(frontmatter: dict, *keys: str, default: str = "") -> str:
    for key in keys:
        value = frontmatter.get(key)
        if value:
            return str(value)
    return default


# --------------------------------------------------------------------------- #
# Rendering helpers
# --------------------------------------------------------------------------- #
def demote_headings(markdown: str, levels: int = 2) -> str:
    """Push body headings down so they nest under the category heading."""
    output: List[str] = []
    in_fence = False
    for line in markdown.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            output.append(line)
            continue
        if not in_fence:
            heading = re.match(r"^(#{1,6})(\s+.*)$", line)
            if heading:
                hashes = heading.group(1)
                line = "#" * min(6, len(hashes) + levels) + heading.group(2)
        output.append(line)
    return "\n".join(output)


def article_url(category: str, date: str) -> str:
    return f"{SITE}/resources/p/{category}/{date}?{UTM}&utm_content={category}-{date}"


def flashcards_url() -> str:
    return f"{SITE}/tools/flashcards?{UTM}"


def coaching_url() -> str:
    return f"{SITE}/contact?{UTM}"


def render_digest(date: str, lang: str, items: Dict[str, dict]) -> str:
    labels = LABELS[lang]
    ordered = [category for category in CATEGORIES if category in items]
    header_title = (
        f"# 🗓️ TalentMe AI Daily — {date}"
        if lang == "en"
        else f"# 🗓️ TalentMe AI 日报 — {date}"
    )
    if lang == "en":
        unit = "edition" if len(ordered) == 1 else "editions"
        count_label = f"{len(ordered)} {unit}"
    else:
        count_label = f"{len(ordered)} 期"
    lines: List[str] = [
        "---",
        f'date: "{date}"',
        f"lang: {lang}",
        f"categories: [{', '.join(ordered)}]",
        "---",
        "",
        header_title,
        "",
        f"> {labels['intro']} · **{count_label}**",
        "",
        f"> [🌐 Read on TalentMe]({SITE}/resources?{UTM}) · "
        f"[🃏 {labels['practice']}]({flashcards_url()}) · "
        f"[🎯 {labels['coach']}]({coaching_url()})",
        "",
        "---",
        "",
    ]

    for category in ordered:
        item = items[category]
        lines.extend([f"## {labels[category]}", "", f"### {item['title']}", ""])
        summary = item.get("summary", "")
        if summary:
            lines.extend([f"> {summary}", ""])
        body = demote_headings(item.get("body", "").strip())
        if body:
            lines.extend([body, ""])
        lines.extend(
            [
                f"[{labels['read']} →]({article_url(category, date)})",
                "",
                "---",
                "",
            ]
        )

    lines.extend(
        [
            f"🎯 [{labels['practice']}]({flashcards_url()}) · "
            f"[{labels['coach']}]({coaching_url()})",
            "",
            f"_{labels['watch']}_",
            "",
        ]
    )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Source collection
# --------------------------------------------------------------------------- #
def collect(source: Path) -> Dict[str, Dict[str, Dict[str, dict]]]:
    """date -> lang -> category -> {title, summary, body}."""
    tree: Dict[str, Dict[str, Dict[str, dict]]] = {}
    for category in CATEGORIES:
        directory = source / category
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            match = DATE_FILE_RE.match(path.name)
            if not match:
                continue
            date, lang = match.groups()
            frontmatter, body = parse_frontmatter(path.read_text(encoding="utf-8"))
            title = pick(
                frontmatter,
                f"title{lang.capitalize()}",
                "title",
                default=f"{category} · {date}",
            )
            summary = pick(
                frontmatter,
                f"summary{lang.capitalize()}",
                f"excerpt{lang.capitalize()}",
                "summary",
                "excerpt",
            )
            tree.setdefault(date, {}).setdefault(lang, {})[category] = {
                "title": title,
                "summary": summary,
                "body": body,
            }
    return tree


# --------------------------------------------------------------------------- #
# README
# --------------------------------------------------------------------------- #
def read_digest_meta(path: Path) -> dict:
    frontmatter, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    return frontmatter


def scan_digests() -> Dict[str, Dict[str, Set[str]]]:
    """date -> lang -> categories, from the generated files."""
    tree: Dict[str, Dict[str, Set[str]]] = {}
    for path in sorted((REPO_ROOT / "digests").glob("*.md")):
        match = DATE_FILE_RE.match(path.name)
        if not match:
            continue
        date, lang = match.groups()
        frontmatter = read_digest_meta(path)
        categories = frontmatter.get("categories", [])
        if isinstance(categories, str):
            categories = [value.strip() for value in categories.split(",") if value.strip()]
        tree.setdefault(date, {})[lang] = set(categories)
    return tree


def render_readme(tree: Dict[str, Dict[str, Set[str]]]) -> str:
    dates = sorted(tree, reverse=True)
    total = len(dates)

    lines: List[str] = [
        '<div align="center">',
        "",
        "# 🗓️ TalentMe AI Daily",
        "",
        "**A bilingual daily digest of AI news, papers, and open-source projects — for ML engineers.**",
        "",
        f"**{total} daily editions** · English + 中文 · updated from [talentme.airsota.com]({SITE})",
        "",
        '<p align="center">',
        f'  <a href="{SITE}/resources?{UTM}"><img src="https://img.shields.io/badge/Read%20on%20TalentMe%20%E2%86%92-7C3AED?style=for-the-badge&logo=bookstack&logoColor=white" alt="Read on TalentMe"></a>',
        f'  <a href="{flashcards_url()}"><img src="https://img.shields.io/badge/Practice%201%2C898%20Flashcards-0E7C66?style=for-the-badge&logo=lightning&logoColor=white" alt="Practice flashcards"></a>',
        f'  <a href="{coaching_url()}"><img src="https://img.shields.io/badge/Book%20a%201%3A1%20Mock%20Interview-1F2937?style=for-the-badge&logo=googlecalendar&logoColor=white" alt="Book a mock interview"></a>',
        "</p>",
        "",
        f'<a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-10b981?style=flat-square" alt="MIT License"></a>',
        '  <img src="https://img.shields.io/badge/Language-English%20%7C%20%E4%B8%AD%E6%96%87-3b82f6?style=flat-square" alt="Bilingual">',
        f'  <img src="https://img.shields.io/badge/Editions-{total}-8b5cf6?style=flat-square" alt="{total} editions">',
        "",
        "<sub>⭐ Star the repo and <b>Watch → Releases</b> to receive each daily digest.</sub>",
        "",
        "</div>",
        "",
        "---",
        "",
        "## 📌 Latest editions",
        "",
        "| Date | News | Papers | Projects | Digest |",
        "|---|:--:|:--:|:--:|---|",
    ]

    for date in dates[:10]:
        lines.append(_readme_row(date, tree[date]))

    lines.extend(
        [
            "",
            "---",
            "",
            "## 🗂️ What you get",
            "",
            "- **📰 AI news** — the day's highest-signal releases, funding, and infra changes, with interview-relevant takeaways.",
            "- **📄 Papers** — new research that actually changes engineering practice, summarised in 3-5 minutes.",
            "- **🚀 Projects** — open-source launches worth cloning, with architecture notes.",
            "- **🎯 Interview angle** — every edition ends with the questions an interviewer would ask about it.",
            "",
            "Each digest links back to the formatted edition on TalentMe, where you can practice the topic with **1,898 free flashcards**, interactive mindmaps, and a **1:1 mock interview**.",
            "",
            "---",
            "",
            "## 🗄️ Full archive",
            "",
            f"<details>",
            f"<summary>All {total} editions</summary>",
            "",
            "| Date | News | Papers | Projects | Digest |",
            "|---|:--:|:--:|:--:|---|",
        ]
    )
    for date in dates:
        lines.append(_readme_row(date, tree[date]))
    lines.extend(["", "</details>"])

    lines.extend(
        [
            "",
            "---",
            "",
            "## ⚙️ How it works",
            "",
            "The digests are generated from the TalentMe content pipeline:",
            "",
            "```bash",
            "# sync content + rebuild this README",
            "python3 scripts/sync_daily.py",
            "",
            "# rebuild the README only (used by GitHub Actions)",
            "python3 scripts/sync_daily.py --index-only",
            "```",
            "",
            "The `publish_daily.sh` helper runs the sync, commits, and pushes. You can wire it to cron:",
            "",
            "```bash",
            "0 8 * * * /path/to/TalentMe-AI-Daily/scripts/publish_daily.sh",
            "```",
            "",
            "Every outbound link carries `utm_source=github&utm_medium=daily&utm_campaign=ai-daily` so the site can attribute GitHub traffic.",
            "",
            "---",
            "",
            "## 🔗 Links",
            "",
            f"- **Website**: [talentme.airsota.com]({SITE})",
            f"- **Interactive vault**: [Tech Vault & mindmaps]({SITE}/resources/tech?{UTM})",
            f"- **1,898 flashcards**: [Practice free]({flashcards_url()})",
            f"- **Interview question bank**: [477 cards · 2,385 questions](https://github.com/airsota/TalentMe-Awesome-AI-ML-Interview-Vault)",
            f"- **1:1 mock interviews**: [Book a session]({coaching_url()})",
            "",
            "---",
            "",
            "## 📄 License",
            "",
            "[MIT](LICENSE) © TalentMe AI Team",
            "",
            '<div align="center">',
            '  <sub>Built by the TalentMe AI Team · Synced from <a href="https://talentme.airsota.com">talentme.airsota.com</a></sub>',
            "</div>",
            "",
        ]
    )
    return "\n".join(lines)


def _readme_row(date: str, languages: Dict[str, object]) -> str:
    categories: Set[str] = set()
    for values in languages.values():
        categories |= set(values.keys()) if isinstance(values, dict) else set(values)
    marks = " | ".join("✅" if category in categories else "—" for category in CATEGORIES)
    links = []
    for lang, label in (("en", "EN"), ("zh", "中文")):
        if lang in languages:
            links.append(f"[{label}](digests/{date}.{lang}.md)")
    return f"| {date} | {marks} | {' · '.join(links) if links else '—'} |"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def write_if_changed(path: Path, content: str, dry_run: bool) -> bool:
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old == content:
        return False
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    print(f"{'would write' if dry_run else 'wrote'}: {path.relative_to(REPO_ROOT)}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--index-only", action="store_true")
    args = parser.parse_args()

    dry_run = args.dry_run or args.check
    changed = 0

    if args.index_only:
        tree = scan_digests()
    else:
        source = args.source.expanduser().resolve()
        if not source.is_dir():
            print(f"error: content source not found: {source}", file=sys.stderr)
            return 2
        tree = collect(source)
        if not tree:
            print("error: no dated editions found", file=sys.stderr)
            return 2

        for date in sorted(tree):
            for lang, items in sorted(tree[date].items()):
                changed += write_if_changed(
                    REPO_ROOT / "digests" / f"{date}.{lang}.md",
                    render_digest(date, lang, items),
                    dry_run,
                )

    changed += write_if_changed(REPO_ROOT / "README.md", render_readme(tree), dry_run)

    dates = len(tree)
    editions = sum(len(languages) for languages in tree.values())
    print()
    print(f"dates:      {dates}")
    print(f"digests:    {editions}")
    print(f"files:      {changed} changed")

    if args.check:
        if changed:
            print("\ncheck failed: daily repo is out of date.")
            return 1
        print("\ncheck passed: daily repo is up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
