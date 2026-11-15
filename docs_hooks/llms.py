"""MkDocs hook: write llms-full.txt, every page in the nav as one Markdown file for AI tools.

docs/llms.txt (the index) is copied to the site like any other file.
"""
from pathlib import Path


def _pages(nav):
    for item in nav or []:
        if isinstance(item, dict):
            for title, value in item.items():
                if isinstance(value, str):
                    yield title, value
                else:
                    yield from _pages(value)
        elif isinstance(item, str):
            yield None, item


def build_llms_full(docs_dir, nav, site_url=""):
    docs_dir = Path(docs_dir)
    parts = ["# PythonFMU3 documentation\n\n"
             "All pages of the PythonFMU3 docs in one file. The index is llms.txt.\n"]
    for title, page in _pages(nav):
        source = docs_dir / page
        if not source.is_file() or source.suffix != ".md":
            continue
        url = site_url.rstrip("/") + "/" + ("" if page == "index.md" else page[:-3] + "/") if site_url else page
        parts.append(f"\n\n---\n\n<!-- {title or page}: {url} -->\n\n{source.read_text(encoding='utf-8').strip()}\n")
    return "".join(parts)


def on_post_build(config, **kwargs):
    text = build_llms_full(config["docs_dir"], config["nav"], config.get("site_url") or "")
    Path(config["site_dir"], "llms-full.txt").write_text(text, encoding="utf-8")
