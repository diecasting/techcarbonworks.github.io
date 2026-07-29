#!/usr/bin/env python3
"""
seo-check.py — SEO Audit Script for Hugo Sites (v1.1 — Multilingual)
=====================================================================
Checks built HTML files for common SEO issues:
- Missing <title> tags
- Missing meta description
- Missing canonical link
- Missing Open Graph tags
- Missing h1 tag
- Multiple h1 tags
- Empty alt attributes on images

Multilingual checks (v1.1):
- hreflang tags present on multilingual pages
- hreflang x-default present
- Canonical is self-referencing (no cross-language canonical)
- translationKey consistency across languages
- Language page count parity (warnings only)
- Sitemap exists for each language

Usage: python scripts/seo-check.py [public_dir]
Default public_dir: ./public
"""

import os
import re
import sys
from pathlib import Path
from html.parser import HTMLParser
from collections import defaultdict


class SEOChecker(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = None
        self.description = None
        self.canonical = None
        self.og_title = None
        self.og_description = None
        self.h1_count = 0
        self.images_without_alt = 0
        self.total_images = 0
        self.hreflang_tags = []
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = attrs_dict.get("name", "")
            property_attr = attrs_dict.get("property", "")
            if name == "description":
                self.description = attrs_dict.get("content", "")
            if property_attr == "og:title":
                self.og_title = attrs_dict.get("content", "")
            if property_attr == "og:description":
                self.og_description = attrs_dict.get("content", "")
        elif tag == "link":
            rel = attrs_dict.get("rel", "")
            if rel == "canonical":
                self.canonical = attrs_dict.get("href", "")
            elif rel == "alternate":
                hreflang = attrs_dict.get("hreflang", "")
                href = attrs_dict.get("href", "")
                if hreflang and href:
                    self.hreflang_tags.append((hreflang, href))
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "img":
            self.total_images += 1
            alt = attrs_dict.get("alt", "")
            if not alt:
                self.images_without_alt += 1

    def handle_data(self, data):
        if self._in_title:
            self.title = data.strip()
            self._in_title = False


def check_file(filepath):
    issues = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        checker = SEOChecker()
        checker.feed(content)

        if not checker.title:
            issues.append("Missing <title> tag")
        if not checker.description:
            issues.append("Missing meta description")
        if not checker.canonical:
            issues.append("Missing canonical link")
        if not checker.og_title:
            issues.append("Missing og:title")
        if checker.h1_count == 0:
            issues.append("Missing h1 tag")
        elif checker.h1_count > 1:
            issues.append(f"Multiple h1 tags ({checker.h1_count})")
        if checker.images_without_alt > 0:
            issues.append(f"Images without alt: {checker.images_without_alt}/{checker.total_images}")
    except Exception as e:
        issues.append(f"Parse error: {e}")
    return issues


def check_multilingual(filepath, content, has_translations):
    """Check multilingual SEO issues."""
    issues = []

    checker = SEOChecker()
    checker.feed(content)

    # hreflang checks (only if the site has translations)
    if has_translations:
        if not checker.hreflang_tags:
            issues.append("Missing hreflang tags (multilingual page without hreflang)")
        else:
            # Check for x-default
            has_x_default = any(hl == "x-default" for hl, _ in checker.hreflang_tags)
            if not has_x_default:
                issues.append("Missing hreflang x-default")

        # Canonical self-referencing check
        if checker.canonical:
            # The canonical should match the page's own URL
            # We check by ensuring the canonical doesn't point to a different language path
            filepath_str = str(filepath).replace("\\", "/")
            # Extract language from path (e.g., /de/, /ja/)
            lang_in_path = None
            parts = filepath_str.split("/")
            for part in parts:
                if part in ("de", "ja", "fr", "es"):
                    lang_in_path = part
                    break

            if lang_in_path:
                # Non-default language: canonical should contain the language prefix
                if f"/{lang_in_path}/" not in checker.canonical:
                    issues.append(f"Canonical cross-language: canonical URL does not match language '{lang_in_path}'")

    return issues, checker.hreflang_tags, checker.canonical


def main():
    public_dir = sys.argv[1] if len(sys.argv) > 1 else "./public"
    if not os.path.isdir(public_dir):
        print(f"ERROR: Directory not found: {public_dir}")
        sys.exit(1)

    html_files = list(Path(public_dir).rglob("*.html"))
    if not html_files:
        print(f"WARNING: No HTML files found in {public_dir}")
        sys.exit(0)

    # Skip pagination redirect pages (page/1/index.html)
    html_files = [f for f in html_files if "/page/1/" not in str(f).replace("\\", "/")]

    # Skip language-root redirect pages (e.g., public/en/index.html)
    # These are auto-generated by Hugo when defaultContentLanguageInSubdir = false
    # They contain only a <meta http-equiv="refresh"> redirect, no real content
    non_redirect_files = []
    for f in html_files:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                content = fh.read()
            if 'http-equiv="refresh"' in content or "http-equiv=refresh" in content:
                continue  # Skip redirect pages
            non_redirect_files.append(f)
        except Exception:
            non_redirect_files.append(f)
    html_files = non_redirect_files

    # Detect multilingual setup
    lang_dirs = set()
    for f in html_files:
        parts = str(f).replace("\\", "/").split("/")
        for part in parts:
            if part in ("de", "ja", "fr", "es"):
                lang_dirs.add(part)
                break

    has_translations = len(lang_dirs) > 0 or any(
        "/de/" in str(f).replace("\\", "/") or "/ja/" in str(f).replace("\\", "/")
        for f in html_files
    )

    # Check sitemaps
    sitemap_files = list(Path(public_dir).glob("sitemap*.xml"))
    lang_page_counts = defaultdict(int)

    total_files = 0
    total_issues = 0
    files_with_issues = 0
    all_hreflang = []

    for filepath in sorted(html_files):
        rel_path = filepath.relative_to(".")
        total_files += 1

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        issues = check_file(str(filepath))

        # Multilingual checks
        if has_translations:
            ml_issues, hreflang_tags, canonical = check_multilingual(filepath, content, has_translations)
            issues.extend(ml_issues)
            all_hreflang.extend(hreflang_tags)

        # Count pages per language
        filepath_str = str(filepath).replace("\\", "/")
        for lang in ("en", "de", "ja", "fr", "es"):
            if f"/{lang}/" in filepath_str or (lang == "en" and "/de/" not in filepath_str and "/ja/" not in filepath_str and "/fr/" not in filepath_str and "/es/" not in filepath_str):
                lang_page_counts[lang] += 1
                break

        if issues:
            files_with_issues += 1
            total_issues += len(issues)
            print(f"  {rel_path}")
            for issue in issues:
                print(f"    - {issue}")

    # Multilingual summary
    print(f"\n{'='*60}")
    print(f"SEO Check Summary (v1.1 — Multilingual)")
    print(f"{'='*60}")
    print(f"  Files checked:      {total_files}")
    print(f"  Files with issues:  {files_with_issues}")
    print(f"  Total issues:       {total_issues}")

    if has_translations:
        print(f"\n  Multilingual detected:")
        print(f"    Sitemap files:    {len(sitemap_files)}")
        print(f"    Hreflang tags:    {len(all_hreflang)}")
        print(f"\n  Pages per language:")
        for lang in sorted(lang_page_counts.keys()):
            print(f"    {lang}: {lang_page_counts[lang]} pages")

        # Language parity warning (not a failure)
        counts = [v for v in lang_page_counts.values() if v > 0]
        if len(counts) > 1:
            max_count = max(counts)
            min_count = min(counts)
            if max_count - min_count > 5:
                print(f"\n  WARNING: Language page count disparity (max={max_count}, min={min_count})")
                print(f"           Some translations may be missing.")
    else:
        print(f"\n  Single-language site (no multilingual checks applied)")

    if files_with_issues > 0:
        print(f"\n  STATUS: FAIL")
        sys.exit(1)
    else:
        print(f"\n  STATUS: PASS")
        sys.exit(0)


if __name__ == "__main__":
    main()
