#!/usr/bin/env python3
"""
SLM Website Structure & Readability Auditor
=============================================

Fetches a URL, extracts a sanitized DOM, segments it into semantic regions,
computes structural metrics, runs a small local LLM (via Ollama) to score
human/AI readability and flag problem regions, then writes a timestamped
Markdown report.

Usage:
    python web_audit.py https://example.com
    python web_audit.py https://example.com --model llama3.2:3b --out-dir reports/
    python web_audit.py https://example.com --no-cache --max-regions 6

    python web_audit.py https://example.com --profile remora
    python web_audit.py https://example.com --profile-file my_remora_tuned.json
"""

import argparse
import hashlib
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import ollama
import requests
from bs4 import BeautifulSoup, Comment, NavigableString, Tag

# Deeply nested page builders (Wix/Squarespace-style markup) can exceed
# Python's default recursion limit during DOM serialization.
sys.setrecursionlimit(5000)

CACHE_DIR = Path(".cache")
DEFAULT_MODEL = "llama3.2:3b"
DEFAULT_TIMEOUT = 20
DEFAULT_TEXT_EXCERPT_CHARS = 3000
DEFAULT_MAX_REGIONS = 8
DEFAULT_REGION_MIN_CHARS = 120
DEFAULT_REGION_EXCERPT_CHARS = 280
MAX_SERIALIZE_DEPTH = 200  # hard safety cap, independent of region segmentation


# =========================================================
# SAFE FILENAME / HASHING
# =========================================================

def url_hash(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]


def safe_report_name(url: str) -> str:
    parsed = urlparse(url)
    netloc = parsed.netloc.split("@")[-1] if "@" in parsed.netloc else parsed.netloc
    path = parsed.path.strip("/").replace("/", "_")
    base = f"{netloc}_{path}" if path else netloc
    base = "".join(c if c.isalnum() or c in "._-" else "_" for c in base)
    return f"{base}_{url_hash(url)}"


# =========================================================
# HTML CACHE (speeds up iterating on prompts)
# =========================================================

def _cache_path(url: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"{url_hash(url)}.html"


def load_cached_html(url: str):
    p = _cache_path(url)
    return p.read_text(encoding="utf-8") if p.exists() else None


def save_cached_html(url: str, html: str) -> None:
    _cache_path(url).write_text(html, encoding="utf-8")


# =========================================================
# FETCH
# =========================================================

def fetch_html(url: str, timeout: int, use_cache: bool) -> str:
    if use_cache:
        cached = load_cached_html(url)
        if cached is not None:
            print("Using cached HTML (use --no-cache to refetch)")
            return cached

    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; SLM-Auditor/1.0)"},
            timeout=timeout,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"ERROR: failed to fetch {url}: {e}")
        sys.exit(1)

    # requests' header-based encoding guess defaults to ISO-8859-1 when a
    # page doesn't declare a charset, which mangles non-ASCII text. The
    # apparent_encoding (content-sniffing) guess is usually more accurate.
    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding

    html = resp.text

    if use_cache:
        save_cached_html(url, html)

    return html


# =========================================================
# STAGE 1 - DOM EXTRACTION (LOSSLESS, WITH SAFETY GUARDS)
# =========================================================

def sanitize(soup: BeautifulSoup) -> BeautifulSoup:
    for script in soup.find_all("script"):
        if script.get("type") == "application/ld+json":
            continue
        script.decompose()

    for style in soup.find_all("style"):
        style.decompose()

    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    for tag in soup.find_all(True):
        for attr in list(tag.attrs):
            if attr.startswith("on"):
                del tag.attrs[attr]

    return soup


def serialize(node, depth: int = 0):
    if depth > MAX_SERIALIZE_DEPTH:
        return {"type": "tag", "name": "truncated-too-deep", "attrs": {}, "depth": depth, "children": []}

    if isinstance(node, NavigableString):
        text = str(node).strip()
        if not text:
            return None
        return {"type": "text", "text": text, "depth": depth}

    if isinstance(node, Tag):
        children = []
        for c in node.children:
            r = serialize(c, depth + 1)
            if r:
                children.append(r)
        return {
            "type": "tag",
            "name": node.name,
            "attrs": dict(node.attrs),
            "depth": depth,
            "children": children,
        }

    return None


_OG_PROPERTY_RE = re.compile(r"^og:")
_TWITTER_NAME_RE = re.compile(r"^twitter:")
_BREADCRUMB_RE = re.compile(r"breadcrumb", re.I)
_HEADING_TAG_RE = re.compile(r"^h[1-6]$")


def extract_structured_data(soup: BeautifulSoup) -> dict:
    """Deterministic extraction of JSON-LD, OpenGraph, Twitter Card, and
    basic meta tags. This is exactly the kind of thing that should NOT be
    left to a small (or any) LLM -- it's either valid, parseable structured
    data or it isn't, with no judgment call involved."""
    json_ld = []
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text()
        entry = {"valid_json": False, "types": []}
        try:
            parsed = json.loads(raw or "")
            entry["valid_json"] = True
            items = parsed if isinstance(parsed, list) else [parsed]
            for item in items:
                if isinstance(item, dict):
                    t = item.get("@type")
                    if isinstance(t, list):
                        entry["types"].extend(t)
                    elif t:
                        entry["types"].append(t)
        except (json.JSONDecodeError, TypeError):
            pass
        json_ld.append(entry)

    open_graph = {m.get("property"): m.get("content") for m in soup.find_all("meta", property=_OG_PROPERTY_RE)}
    twitter_card = {m.get("name"): m.get("content") for m in soup.find_all("meta", attrs={"name": _TWITTER_NAME_RE})}

    meta_description = None
    desc_tag = soup.find("meta", attrs={"name": "description"})
    if desc_tag:
        meta_description = desc_tag.get("content")

    return {
        "json_ld": json_ld,
        "open_graph": open_graph,
        "twitter_card": twitter_card,
        "meta_description": meta_description,
        "microdata_itemscope_count": len(soup.find_all(attrs={"itemscope": True})),
    }


def audit_structure(soup: BeautifulSoup) -> list:
    """Deterministic, rule-based HTML structure / landmark / accessibility
    checks -- no LLM involved, so these are exact and reproducible every
    run, unlike the LLM-judged heatmap. Covers universal best practices
    (one <main>, one <h1>, labeled <nav> landmarks when there's more than
    one, alt text, etc.) -- NOT site/theme-specific region naming, which
    belongs in a separate configurable profile instead of being guessed at
    here."""
    findings = []

    def flag(severity, message):
        findings.append({"severity": severity, "message": message})

    h1s = soup.find_all("h1")
    if len(h1s) == 0:
        flag("critical", "No <h1> found on the page.")
    elif len(h1s) > 1:
        flag("moderate", f"{len(h1s)} <h1> elements found -- a page should generally have exactly one.")

    mains = soup.find_all("main")
    if len(mains) == 0:
        flag("critical", "No <main> landmark -- nav, header, and content are structurally "
                         "indistinguishable to assistive tech and extractors.")
    elif len(mains) > 1:
        flag("moderate", f"{len(mains)} <main> elements found -- there should only be one.")

    navs = soup.find_all("nav")
    unlabeled_navs = [n for n in navs if not (n.get("aria-label") or n.get("aria-labelledby"))]
    if len(navs) > 1 and unlabeled_navs:
        flag("moderate", f"{len(unlabeled_navs)} of {len(navs)} <nav> elements have no aria-label "
                         "-- indistinguishable to screen readers when there's more than one nav.")

    if not soup.find("footer"):
        flag("minor", "No <footer> landmark found.")
    if not soup.find("header"):
        flag("minor", "No <header> landmark found.")

    headings = soup.find_all(_HEADING_TAG_RE)
    levels = [int(h.name[1]) for h in headings]
    for prev, curr in zip(levels, levels[1:]):
        if curr - prev > 1:
            flag("minor", f"Heading level jumps from h{prev} to h{curr} without an intermediate level.")
            break  # one mention is enough, avoid spamming for repeated occurrences

    imgs = soup.find_all("img")
    missing_alt = [i for i in imgs if i.get("alt") is None]
    if missing_alt:
        flag("moderate", f"{len(missing_alt)} of {len(imgs)} <img> elements have no alt attribute at all.")

    icon_only = 0
    for b in soup.find_all(["button", "a"]):
        if not b.get_text(strip=True) and not (b.get("aria-label") or b.get("title")):
            icon_only += 1
    if icon_only:
        flag("moderate", f"{icon_only} buttons/links have no visible text and no aria-label/title.")

    has_breadcrumb = bool(
        soup.find(attrs={"aria-label": _BREADCRUMB_RE}) or soup.find(attrs={"class": _BREADCRUMB_RE})
    )
    findings.append({"severity": "info", "message": f"Breadcrumb navigation {'found' if has_breadcrumb else 'not found'}."})

    return findings


# =========================================================
# STRUCTURE PROFILES
# (opt-in, theme/CMS-specific region checks on top of the
# universal audit_structure() rules above)
# =========================================================

# A profile is just data: a name, a list of selector-based presence rules,
# and a list of DOM-order rules. The engine below (run_profile) is generic
# -- it doesn't know anything about Drupal or Remora specifically. New
# profiles can be added here, or loaded from an external JSON file via
# --profile-file, without touching the matching logic.
#
# Rule fields:
#   id        - short label, shown in output
#   selector  - any CSS selector BeautifulSoup's .select() supports
#   required  - True: flag if NOT found. False: just informational presence note.
#   severity  - "critical" | "moderate" | "minor" (used when required and missing)
#   message   - shown when the rule fails
#
# Order-check fields:
#   before / after - CSS selectors; the FIRST match of `before` must appear
#                    earlier in the HTML source than the first match of `after`
#   message         - shown when the order is violated

PROFILES = {
    "generic": {
        "name": "generic",
        "rules": [],
        "order_checks": [],
    },
    # STARTER profile based on the Remora region structure as described --
    # NOT verified against actual rendered markup with real data-region/
    # aria-label attributes (only checked via a markdown-converted fetch,
    # which strips attributes). Treat this as a template: run it, see what
    # it flags, and adjust selectors/requiredness to match what your
    # templates actually output. Easiest way to iterate: copy this dict (or
    # export it) to a JSON file and pass --profile-file, rather than
    # editing the script each time.
    "remora": {
        "name": "remora",
        "rules": [
            {"id": "header", "selector": "header", "required": True, "severity": "moderate",
             "message": "No <header> region found."},
            {"id": "menu_primary", "selector": "header nav[aria-label], header nav[aria-labelledby]",
             "required": False, "severity": "minor",
             "message": "Header has no labeled primary/secondary menu <nav>."},
            {"id": "breadcrumbs", "selector": "[aria-label*='breadcrumb' i], .breadcrumb, [class*='breadcrumb' i]",
             "required": False, "severity": "minor",
             "message": "No breadcrumb element found in header."},
            {"id": "hero", "selector": "[data-region='hero'], [class*='hero' i]",
             "required": False, "severity": "minor",
             "message": "No element tagged as the hero region (data-region='hero' or class containing 'hero')."},
            {"id": "main", "selector": "main", "required": True, "severity": "critical",
             "message": "No <main> region for primary content."},
            {"id": "postscript", "selector": "section[data-region='postscript'], section[aria-label*='additional' i]",
             "required": False, "severity": "minor",
             "message": "No postscript <section> (expected data-region='postscript' or a labeled aria-label)."},
            {"id": "aside", "selector": "aside", "required": False, "severity": "minor",
             "message": "No <aside> sidebar region found (fine if this page has none by design)."},
            {"id": "footer", "selector": "footer", "required": True, "severity": "moderate",
             "message": "No <footer> region found."},
            {"id": "footer_secondary",
             "selector": "[data-region='footer-secondary'], [aria-label*='additional footer' i]",
             "required": False, "severity": "minor",
             "message": "No footer-secondary region found (expected data-region='footer-secondary' "
                        "with an aria-label)."},
        ],
        "order_checks": [
            {"before": "main", "after": "aside",
             "message": "<main> should appear before <aside> in HTML source order, even if CSS "
                        "repositions it visually -- helps assistive tech and extractors treat it "
                        "as primary content."},
        ],
    },
}


def load_profile(profile_name: str, profile_file: str = None) -> dict:
    """Loads a profile by name from PROFILES, or from an external JSON file
    if provided (the JSON file should have the same shape as the dicts in
    PROFILES above). External file takes precedence if given."""
    if profile_file:
        with open(profile_file, "r", encoding="utf-8") as f:
            return json.load(f)
    if profile_name not in PROFILES:
        print(f"WARNING: unknown profile '{profile_name}', falling back to 'generic'")
        return PROFILES["generic"]
    return PROFILES[profile_name]


def run_profile(soup: BeautifulSoup, profile: dict) -> list:
    """Generic engine: runs a profile's selector-presence rules and DOM-
    order rules against soup. Knows nothing about any specific CMS/theme --
    all of that lives in the profile data itself."""
    findings = []

    for rule in profile.get("rules", []):
        try:
            matches = soup.select(rule["selector"])
        except Exception as e:
            findings.append({"severity": "minor", "message": f"Profile rule '{rule['id']}' has an invalid selector: {e}"})
            continue
        if matches:
            continue
        if rule.get("required"):
            findings.append({"severity": rule.get("severity", "minor"), "message": rule["message"]})
        else:
            # Optional rules still surface when missing, just at info level --
            # otherwise a required=False rule produces no output ever, which
            # makes it pointless to have in the profile at all.
            findings.append({"severity": "info", "message": f"[{rule['id']}] {rule['message']}"})

    for check in profile.get("order_checks", []):
        try:
            before_el = soup.select_one(check["before"])
            after_el = soup.select_one(check["after"])
        except Exception:
            continue
        if before_el is None or after_el is None:
            continue  # presence rules above already cover "missing entirely"
        before_pos = (before_el.sourceline or 0, before_el.sourcepos or 0)
        after_pos = (after_el.sourceline or 0, after_el.sourcepos or 0)
        if before_pos > after_pos:
            findings.append({"severity": "minor", "message": check["message"]})

    return findings


def extract_dom(html: str, profile_name: str = "generic", profile_file: str = None) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    # Structured data and the structure audit need the FULL document
    # (meta/JSON-LD live in <head>, landmarks span the whole <body>) --
    # extract both before sanitize() and before we narrow to body-only.
    structured_data = extract_structured_data(soup)
    structure_findings = audit_structure(soup)

    if profile_name != "generic" or profile_file:
        profile = load_profile(profile_name, profile_file)
        structure_findings = structure_findings + run_profile(soup, profile)

    soup = sanitize(soup)

    title = ""
    if soup.title:
        title = (soup.title.string or soup.title.get_text()).strip()

    return {
        "title": title,
        "dom": serialize(soup.body if soup.body else soup),
        "structured_data": structured_data,
        "structure_findings": structure_findings,
    }


# =========================================================
# STAGE 2 - METRICS
# =========================================================

def walk(root, stats: dict) -> None:
    """Iterative traversal -- avoids RecursionError on pathologically deep DOMs."""
    stack = [root]
    while stack:
        node = stack.pop()
        if not node:
            continue
        if node["type"] == "text":
            stats["text_nodes"] += 1
            stats["text_length"] += len(node["text"])
            continue
        tag = node.get("name", "")
        stats["tags"][tag] = stats["tags"].get(tag, 0) + 1
        stats["max_depth"] = max(stats["max_depth"], node.get("depth", 0))
        stack.extend(node.get("children", []))


def compute_metrics(dom) -> dict:
    stats = {"text_nodes": 0, "text_length": 0, "tags": {}, "max_depth": 0}
    walk(dom, stats)

    total = sum(stats["tags"].values()) or 1
    entropy = 0.0
    for v in stats["tags"].values():
        p = v / total
        entropy -= p * math.log2(p)

    return {
        "text_nodes": stats["text_nodes"],
        "text_length": stats["text_length"],
        "max_depth": stats["max_depth"],
        "tag_entropy": round(entropy, 3),
        "tag_distribution": stats["tags"],
    }


# =========================================================
# STAGE 2.5 - TEXT EXCERPT + REGION SEGMENTATION
# (the structural work a small model shouldn't have to do)
# =========================================================

def _collect_text(node, parts) -> None:
    if not node:
        return
    if node["type"] == "text":
        parts.append(node["text"])
        return
    for c in node.get("children", []):
        _collect_text(c, parts)


def _count_tag(node, tag_name: str) -> int:
    if not node or node["type"] == "text":
        return 0
    count = 1 if node.get("name") == tag_name else 0
    for c in node.get("children", []):
        count += _count_tag(c, tag_name)
    return count


_CHROME_TAGS = {"nav", "header", "footer", "aside", "form", "button", "label", "script", "style"}

# Matches leaked PHP/Symfony VarDumper-style debug output, e.g. a Twig
# {{ dump(var) }} call left in production renders literally as
# 'Drupal\Core\Template\Attribute { #15166 ... }' in the visible page text.
_DEBUG_DUMP_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_\\]*\s*\{\s*#\d+")


def strip_debug_dump(text: str) -> tuple:
    """Truncates text at the point a leaked debug dump begins. Returns
    (cleaned_text, found). Once this pattern starts, everything after it in
    that text node is object internals, not real content -- and feeding raw
    dump syntax (heavy on backslashes/braces/colons) to the model reliably
    produces malformed JSON in its own response, since it has something
    broken-looking to imitate."""
    match = _DEBUG_DUMP_RE.search(text)
    if not match:
        return text, False
    return text[: match.start()].rstrip(), True


def extract_text_excerpt(dom, max_chars: int = DEFAULT_TEXT_EXCERPT_CHARS) -> str:
    """Plain-text reading-order excerpt of the page's actual content --
    this is what gets judged for human/AI readability and article
    detection, instead of a JSON tree dump. Chrome (nav/header/footer/etc.)
    is deliberately excluded here: those elements are already handled as
    their own regions in the heatmap call, and including them risks eating
    the whole character budget with navigation before reaching any real
    content on chrome-heavy pages."""

    def collect(node, parts, in_chrome):
        if not node:
            return
        if node["type"] == "text":
            if not in_chrome:
                parts.append(node["text"])
            return
        nested_chrome = in_chrome or node.get("name") in _CHROME_TAGS
        for c in node.get("children", []):
            collect(c, parts, nested_chrome)

    parts = []
    collect(dom, parts, False)
    text = "\n".join(parts)

    # Chrome-only pages (rare, but possible) would otherwise yield nothing --
    # fall back to the unfiltered text rather than sending an empty excerpt.
    if not text.strip():
        parts = []
        _collect_text(dom, parts)
        text = "\n".join(parts)

    text, _ = strip_debug_dump(text)

    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + " ...[truncated]"
    return text


_LOREM_IPSUM_MARKERS = {"lorem", "ipsum", "dolor", "amet", "consectetur", "adipiscing"}
_COMMON_ENGLISH_STOPWORDS = {
    "the", "and", "is", "of", "to", "in", "for", "on", "with", "as", "at",
    "by", "an", "be", "this", "that", "it", "are", "was", "we", "our", "you",
    "your", "from", "or", "not", "have", "has", "will", "can", "more",
}
_LATIN_ENDINGS = ("us", "um", "is", "it", "unt", "ae", "orum", "ibus", "ut")


def looks_like_placeholder_text(text: str) -> bool:
    """Heuristic flag for lorem-ipsum or other fake-Latin filler content
    (e.g. Drupal's devel_generate dummy text, which uses a different fake-
    Latin word pool than classic Lorem Ipsum and won't match a plain
    'lorem ipsum' substring check). This is NOT a real language-detection
    model -- it's a word-shape heuristic and can misfire on genuinely
    Latin-heavy real content (legal/medical text, scientific names). Good
    enough to flag the common case: a dev/staging page with unfinished
    placeholder copy, which shouldn't be graded for prose quality."""
    words = re.findall(r"[a-zA-Z]+", text.lower())
    if len(words) < 6:
        return False

    if len(set(words) & _LOREM_IPSUM_MARKERS) >= 2:
        return True

    latin_like = sum(1 for w in words if len(w) >= 4 and w.endswith(_LATIN_ENDINGS))
    english_hits = sum(1 for w in words if w in _COMMON_ENGLISH_STOPWORDS)
    latin_ratio = latin_like / len(words)
    english_ratio = english_hits / len(words)

    return latin_ratio > 0.2 and english_ratio < 0.1


SEMANTIC_REGION_TAGS = {"header", "nav", "main", "article", "aside", "footer", "section"}


def segment_regions(
        dom,
        max_regions: int = DEFAULT_MAX_REGIONS,
        min_chars: int = DEFAULT_REGION_MIN_CHARS,
        excerpt_chars: int = DEFAULT_REGION_EXCERPT_CHARS,
) -> list:
    """
    Deterministically splits the page into regions in Python rather than
    asking a small model to both invent a segmentation AND judge it in the
    same breath. Each region gets a short text excerpt plus a few
    structural stats; the model is only asked to score regions it's handed.
    """
    candidates = []

    def has_semantic_descendant(node) -> bool:
        for c in node.get("children", []):
            if c["type"] == "text":
                continue
            if c.get("name") in SEMANTIC_REGION_TAGS:
                return True
            if has_semantic_descendant(c):
                return True
        return False

    def visit(node):
        if not node or node["type"] == "text":
            return
        name = node.get("name", "")
        if name in SEMANTIC_REGION_TAGS:
            if has_semantic_descendant(node):
                # A more specific semantic tag is nested inside (e.g. <article>
                # inside <main>) -- prefer that one, don't double-capture here.
                for c in node.get("children", []):
                    visit(c)
                return
            parts = []
            _collect_text(node, parts)
            text = " ".join(parts).strip()
            text, has_debug_dump = strip_debug_dump(text)
            # always keep chrome regions (nav/header/footer) even if short --
            # they're common offenders worth flagging regardless of length.
            if len(text) >= min_chars or name in ("header", "nav", "footer"):
                candidates.append(
                    {
                        "tag": name,
                        "text": text,
                        "word_count": len(text.split()),
                        "link_count": _count_tag(node, "a"),
                        "heading_count": sum(_count_tag(node, h) for h in ("h1", "h2", "h3", "h4", "h5", "h6")),
                        "has_debug_dump": has_debug_dump,
                    }
                )
            return  # don't descend further -- avoid nested duplicate regions
        for c in node.get("children", []):
            visit(c)

    visit(dom)

    # Fallback for pages built entirely out of generic divs with no
    # semantic tags at all: treat the largest direct children as regions.
    if not candidates:
        for c in dom.get("children", []):
            parts = []
            _collect_text(c, parts)
            text = " ".join(parts).strip()
            text, has_debug_dump = strip_debug_dump(text)
            if len(text) >= min_chars:
                candidates.append(
                    {
                        "tag": c.get("name", "div"),
                        "text": text,
                        "word_count": len(text.split()),
                        "link_count": _count_tag(c, "a"),
                        "heading_count": sum(_count_tag(c, h) for h in ("h1", "h2", "h3", "h4", "h5", "h6")),
                        "has_debug_dump": has_debug_dump,
                    }
                )

    def rank_key(r):
        density_penalty = r["link_count"] / max(r["word_count"], 1)
        score = r["word_count"] * (1.0 - min(density_penalty, 0.9))
        if r["tag"] in ("nav", "header", "footer"):
            score += 50  # guarantee chrome regions surface for review even if link-dense
        return score

    candidates.sort(key=rank_key, reverse=True)
    candidates = candidates[:max_regions]

    regions = []
    for i, r in enumerate(candidates, 1):
        excerpt = r["text"][:excerpt_chars]
        if len(r["text"]) > excerpt_chars:
            excerpt += " ...[truncated]"
        regions.append(
            {
                "region_id": f"r{i}",
                "tag": r["tag"],
                "word_count": r["word_count"],
                "link_count": r["link_count"],
                "heading_count": r["heading_count"],
                "excerpt": excerpt,
                "likely_placeholder": looks_like_placeholder_text(r["text"]),
                "has_debug_dump": r.get("has_debug_dump", False),
            }
        )

    return regions


# =========================================================
# STAGE 3 - SLM ANALYSIS (FLAT SCHEMAS, REAL FEW-SHOT EXAMPLES,
# OPTIONAL JSON-MODE, SELF-REPAIR + LOW-EFFORT RETRY)
# =========================================================

READABILITY_EXAMPLE = """{
  "page_score": 58,
  "human_score": 6,
  "human_summary": "Body copy is clear sentence-by-sentence, but the actual point doesn't show up until several paragraphs of throat-clearing and is interrupted twice by unrelated promo blocks.",
  "ai_score": 4,
  "ai_summary": "No clear heading hierarchy separates sections, so an extractor would have a hard time telling promotional asides apart from the actual subject matter.",
  "is_article": true,
  "confidence": 0.7,
  "page_type": "blog",
  "reasoning": "Has a byline, a publish date, and several paragraphs of prose, but is interrupted by enough non-editorial content that confidence isn't higher.",
  "top_issue": "Promotional content is interleaved with editorial content with no visual or structural separation.",
  "top_issue_fix": "Move promotional blocks to a sidebar or clearly-labeled section, separate from the article body."
}"""

HEATMAP_ENTRIES_EXAMPLE = """[
  {"region_id": "r1", "human_readability": 3, "ai_readability": 2, "semantic_quality": 3, "issue": "47 nearly-identical links with no grouping or labeling", "fix": "Group related links under labeled <ul> sections, or collapse into a dropdown"},
  {"region_id": "r2", "human_readability": 8, "ai_readability": 7, "semantic_quality": 8, "issue": "Minor: heading jumps from h1 directly to h4", "fix": "Use h2/h3 for intermediate sections"}
]"""

GLOBAL_ISSUES_EXAMPLE = """{
  "global_issues": {
    "critical": ["Checkout button has no visible label, only an icon"],
    "moderate": ["Two different sections use inconsistent date formats (Jan 5 vs 01/05)"],
    "minor": ["Footer social links open in the same tab instead of a new one"]
  },
  "fix_priority": [
    {"task": "Add a text label or aria-label to the checkout button", "reason": "Screen readers and AI agents currently can't tell what it does"},
    {"task": "Standardize date formatting across sections", "reason": "Inconsistent formats look unpolished and can confuse date-parsing extractors"}
  ]
}"""

# Safety net: if the model still falls back to copying example text verbatim
# instead of grounding its answer in the actual regions, these exact strings
# from the examples above are the tell. Checked against, never about the
# user's real page -- if any of these show up unmodified, the response gets
# treated as low-effort and retried.
_EXAMPLE_ECHO_STRINGS = {
    "47 nearly-identical links with no grouping or labeling",
    "Group related links under labeled <ul> sections, or collapse into a dropdown",
    "Minor: heading jumps from h1 directly to h4",
    "Use h2/h3 for intermediate sections",
    "Checkout button has no visible label, only an icon",
    "Two different sections use inconsistent date formats (Jan 5 vs 01/05)",
    "Footer social links open in the same tab instead of a new one",
    "Add a text label or aria-label to the checkout button",
    "Screen readers and AI agents currently can't tell what it does",
    "Standardize date formatting across sections",
    "Inconsistent formats look unpolished and can confuse date-parsing extractors",
    # Strings from an earlier version of this prompt that real runs have
    # echoed verbatim -- kept here so old habits get caught too.
    "No <main> landmark wraps the primary content",
    "Several buttons have no visible text, only icons",
    "Inconsistent date formatting between sections",
    "Add a <main> landmark around the primary content",
    "Currently nav and content are structurally indistinguishable to assistive tech and extractors",
    "Label icon-only buttons",
    "Screen readers and AI agents can't tell what they do",
}


def summarize_structured_data(structured_data: dict) -> str:
    """Short, code-generated summary of structured data for the model to use
    as context -- the parsing/validity check already happened deterministically
    in extract_structured_data(); this just states the findings in prose."""
    lines = []
    json_ld = structured_data.get("json_ld", [])
    if not json_ld:
        lines.append("No JSON-LD structured data found.")
    else:
        for i, block in enumerate(json_ld, 1):
            if block["valid_json"]:
                types = ", ".join(block["types"]) if block["types"] else "(no @type declared)"
                lines.append(f"JSON-LD block {i}: valid, declares type(s): {types}")
            else:
                lines.append(f"JSON-LD block {i}: present but NOT valid JSON (broken structured data).")

    og = structured_data.get("open_graph", {})
    lines.append(f"OpenGraph tags found: {len(og)}" + (f" (og:type={og.get('og:type')})" if og.get("og:type") else ""))
    if not structured_data.get("meta_description"):
        lines.append("No meta description tag found.")

    return "\n".join(lines)


def build_readability_prompt(title: str, text_excerpt: str, metrics_json: str, structured_data: dict, placeholder_warning: bool = False) -> str:
    structured_summary = summarize_structured_data(structured_data)
    placeholder_note = (
        "\nNOTE: this excerpt appears to contain lorem-ipsum-style placeholder/filler text "
        "(common on dev or staging sites). Do not penalize prose quality for gibberish text -- "
        "judge the structure (headings, organization) but call out in your reasoning that the "
        "content itself looks like placeholder copy, not a real readability problem.\n"
        if placeholder_warning else ""
    )
    return (
        "You are a senior web + AI readability auditor.\n"
        f"Page title: {title!r}\n\n"
        "Below is the page's visible text in reading order (it may be truncated if long):\n"
        "---\n"
        f"{text_excerpt}\n"
        "---\n"
        f"{placeholder_note}\n"
        f"Structured data found on this page (already parsed/validated -- use as context, you "
        f"don't need to re-derive it):\n{structured_summary}\n\n"
        f"Structural metrics for context:\n{metrics_json}\n\n"
        "Judge this page's human readability, AI/LLM extractability, and whether it's an "
        "article (vs. a landing/listing/product page). If structured data already declares a "
        "type (e.g. JSON-LD @type or og:type), weigh that as a strong signal.\n\n"
        "Here is an EXAMPLE response, for a completely different, unrelated page, showing the "
        "format and level of specificity expected. Do not reuse its wording or values -- it is "
        "only here to show you what 'real analysis' looks like instead of generic filler:\n\n"
        f"{READABILITY_EXAMPLE}\n\n"
        "Now write your own JSON object in the exact same shape, based on the actual page text "
        "above. Be specific -- reference what's actually in the excerpt. "
        "Return ONLY the JSON object, no commentary, no markdown fences."
    )


def build_heatmap_entries_prompt(regions: list, metrics_json: str) -> str:
    regions_json = json.dumps(regions, indent=2)
    placeholder_ids = [r["region_id"] for r in regions if r.get("likely_placeholder")]
    placeholder_note = (
        f"\nNOTE: regions {', '.join(placeholder_ids)} appear to contain lorem-ipsum-style "
        "placeholder/filler text. For those, don't critique the gibberish prose -- just set "
        "issue to something like 'Contains placeholder/lorem-ipsum text, not real content' and "
        "still score semantic_quality based on the HTML structure itself.\n"
        if placeholder_ids else ""
    )
    return (
        "You are a senior web + AI readability auditor.\n"
        "Below are pre-identified regions of a page -- they have already been segmented for "
        "you, so you do not need to find regions yourself, only judge the ones given:\n\n"
        f"{regions_json}\n"
        f"{placeholder_note}\n"
        f"Structural metrics for the whole page:\n{metrics_json}\n\n"
        "Here is an EXAMPLE response, for different, unrelated regions, showing the format and "
        "level of specificity expected. Do not reuse its wording or values -- it is only here "
        "to show you what 'real analysis' looks like instead of generic filler:\n\n"
        f"{HEATMAP_ENTRIES_EXAMPLE}\n\n"
        "Now return a JSON array with exactly one entry per region_id above (there are "
        f"{len(regions)}). Every entry MUST include numeric human_readability, ai_readability, "
        "and semantic_quality scores (1-10) -- never omit them. The 'issue' field must be an "
        "actual diagnosis of a problem, not a restatement of the region's excerpt text -- if "
        "there's genuinely no issue, set issue and fix to empty strings rather than copying the "
        "excerpt back. Return ONLY the JSON array, no commentary, no markdown fences, no "
        "wrapper object -- just the array."
    )


def build_global_issues_prompt() -> str:
    return (
        "Now summarize the page as a whole, based ONLY on the issues you just identified for "
        "the regions above -- do not introduce a new issue you haven't already flagged.\n\n"
        "Give up to 3 CRITICAL issues, up to 3 MODERATE issues, up to 3 MINOR issues, and up "
        "to 3 fix priorities (task + reason). Every single item must trace back to something "
        "you specifically said about one of the regions above.\n\n"
        "Here is an EXAMPLE of the format, for a different, unrelated page -- do not reuse its "
        "wording or its specific issues (this example's issues will not match your page):\n\n"
        f"{GLOBAL_ISSUES_EXAMPLE}\n\n"
        "Return ONLY a JSON object in that same shape, no commentary, no markdown fences."
    )


def extract_json_block(text: str) -> str:
    """Strip markdown code fences and isolate the outermost JSON value
    (object OR array), since models often wrap JSON in commentary or
    ```json fences despite being told not to, and some prompts here ask
    for a bare array rather than a wrapper object."""
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    text = text.strip()

    # Try to parse just the FIRST complete JSON value starting at the first
    # bracket. This correctly handles "extra data" -- e.g. the model emits
    # one valid array/object followed by more text (or even a second JSON
    # blob) -- which naive last-bracket matching below can't distinguish
    # from one big malformed value spanning everything in between.
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if starts:
        start = min(starts)
        try:
            _, end = json.JSONDecoder().raw_decode(text, start)
            return text[start:end]
        except json.JSONDecodeError:
            pass  # fall through to the bracket-matching heuristic below

    candidates = []
    obj_start, obj_end = text.find("{"), text.rfind("}")
    if obj_start != -1 and obj_end != -1 and obj_end > obj_start:
        candidates.append((obj_start, text[obj_start : obj_end + 1]))
    arr_start, arr_end = text.find("["), text.rfind("]")
    if arr_start != -1 and arr_end != -1 and arr_end > arr_start:
        candidates.append((arr_start, text[arr_start : arr_end + 1]))

    if not candidates:
        return text
    candidates.sort(key=lambda c: c[0])  # whichever bracket opens first is the root
    return candidates[0][1]


_READABILITY_REQUIRED = [
    "page_score", "human_score", "human_summary", "ai_score", "ai_summary",
    "is_article", "confidence", "page_type", "reasoning",
]


def _is_low_effort_readability(result: dict) -> bool:
    """Flags responses that are missing fields, or that technically have
    every field but with no real content (all-zero scores and no prose
    anywhere) -- the 'gave up but stayed valid JSON' failure mode."""
    if not isinstance(result, dict):
        return True
    if any(k not in result for k in _READABILITY_REQUIRED):
        return True
    has_prose = any(
        isinstance(result.get(k), str) and len(result.get(k, "")) > 15
        for k in ("human_summary", "ai_summary", "reasoning", "top_issue")
    )
    all_zero = result.get("page_score") in (0, None) and result.get("human_score") in (0, None) \
               and result.get("ai_score") in (0, None)
    return all_zero and not has_prose


_HEATMAP_SCORE_KEYS = ("human_readability", "ai_readability", "semantic_quality")


def _is_low_effort_heatmap_entries(result, region_lookup: dict = None) -> bool:
    """result is expected to be a list here, not a dict. Catches three
    distinct failure modes seen in real runs: missing entries entirely,
    missing/null numeric scores, and an 'issue' field that's just the
    region's own excerpt copied back rather than an actual diagnosis."""
    if not isinstance(result, list) or not result:
        return True

    region_lookup = region_lookup or {}
    for r in result:
        if not isinstance(r, dict):
            return True
        if any(r.get(k) is None for k in _HEATMAP_SCORE_KEYS):
            return True
        issue = (r.get("issue") or "").strip()
        fix = (r.get("fix") or "").strip()
        if issue:
            excerpt = region_lookup.get(r.get("region_id"), {}).get("excerpt", "")
            if excerpt and (issue in excerpt or excerpt[:80] in issue):
                return True  # just echoed the excerpt back, not a diagnosis
            if not fix:
                return True  # named a real problem but gave no fix -- incomplete
    return False


def _contains_echoed_example_text(result: dict) -> bool:
    all_strings = []
    gi = result.get("global_issues", {})
    if isinstance(gi, dict):
        for lvl in ("critical", "moderate", "minor"):
            all_strings.extend(s for s in gi.get(lvl, []) if isinstance(s, str))
    for f in result.get("fix_priority", []):
        if isinstance(f, dict):
            all_strings.append(f.get("task", ""))
            all_strings.append(f.get("reason", ""))
    return any(s.strip() in _EXAMPLE_ECHO_STRINGS for s in all_strings)


def _clean_global_issues(result: dict) -> dict:
    """Defensive cleanup: drop any global_issues/fix_priority entries that
    are empty or whitespace-only. Belt-and-suspenders so a blank '- [ ] ()'
    line never reaches the report even if validation upstream let a mixed
    good/empty list through (a list with SOME real content can still pass
    the 'has_any' check while carrying a few empty entries alongside it)."""
    if not isinstance(result, dict):
        return {"global_issues": {"critical": [], "moderate": [], "minor": []}, "fix_priority": []}

    gi = result.get("global_issues", {})
    cleaned_gi = {
        lvl: [s for s in gi.get(lvl, []) if isinstance(s, str) and s.strip()]
        for lvl in ("critical", "moderate", "minor")
    } if isinstance(gi, dict) else {"critical": [], "moderate": [], "minor": []}

    cleaned_fp = [
        f for f in result.get("fix_priority", [])
        if isinstance(f, dict) and ((f.get("task") or "").strip() or (f.get("reason") or "").strip())
    ]

    return {"global_issues": cleaned_gi, "fix_priority": cleaned_fp}


def _is_low_effort_global_issues(result: dict) -> bool:
    if not isinstance(result, dict):
        return True
    cleaned = _clean_global_issues(result)
    has_any = any(cleaned["global_issues"].values()) or bool(cleaned["fix_priority"])
    if not has_any:
        return True
    return _contains_echoed_example_text(result)


_LOW_EFFORT_FEEDBACK = (
    "Your previous response was valid JSON but didn't contain real analysis -- fields were "
    "empty, zeroed out, or missing entirely instead of reflecting the actual content given "
    "earlier in this conversation. Look at that content again and write specific, concrete "
    "values referencing what's actually there. "
    "Return ONLY the corrected JSON, no commentary, no markdown fences."
)

_HEATMAP_ENTRIES_FEEDBACK = (
    "Your previous response had one or both of these problems: (1) some entries were missing "
    "numeric human_readability/ai_readability/semantic_quality scores -- every entry needs all "
    "three, as numbers 1-10, never omitted; (2) some 'issue' fields were just the region's "
    "excerpt text copied back, not an actual diagnosis -- either identify a real, specific "
    "problem, or leave issue/fix as empty strings if there's nothing to flag. "
    "Return ONLY the corrected JSON array, no commentary, no markdown fences."
)

_ECHOED_EXAMPLE_FEEDBACK = (
    "That reused wording from the example almost verbatim instead of describing your own page. "
    "The example was about a completely different, unrelated page -- its specific issues "
    "(checkout buttons, date formats, etc.) have nothing to do with what you're analyzing. "
    "Go back to the regions you scored above and summarize THOSE, in your own words. "
    "Return ONLY the corrected JSON, no commentary, no markdown fences."
)


def _chat_json_with_repair(model, messages, num_predict, temperature, strict_json, max_retries):
    """
    Sends `messages` to Ollama and parses the reply as JSON, retrying with
    corrective feedback if the reply isn't valid JSON. Pure JSON-validity
    concern only -- callers handle content-quality (low-effort) validation
    and retries on top of this, since what counts as "low effort" differs
    per call.

    Returns (parsed_value_or_error_dict, messages_with_the_reply_appended).
    """
    for attempt in range(max_retries + 1):
        kwargs = dict(
            model=model,
            messages=messages,
            options={"num_predict": num_predict, "temperature": temperature},
        )
        if strict_json:
            kwargs["format"] = "json"

        try:
            res = ollama.chat(**kwargs)
        except Exception as e:
            print(f"  ollama call failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
            if attempt == max_retries:
                return {"parse_error": True, "raw": f"ollama call failed: {e}"}, messages
            continue

        text = res["message"]["content"]
        candidate = extract_json_block(text)

        try:
            parsed = json.loads(candidate)
            return parsed, messages + [{"role": "assistant", "content": text}]
        except json.JSONDecodeError as e:
            print(f"  JSON parse failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
            if attempt == max_retries:
                return {"parse_error": True, "raw": text}, messages
            messages = messages + [
                {"role": "assistant", "content": text},
                {
                    "role": "user",
                    "content": (
                        f"That was not valid JSON ({e}). Return ONLY the corrected, "
                        "complete, valid JSON -- no commentary, no markdown fences."
                    ),
                },
            ]

    return {"parse_error": True, "raw": ""}, messages


def call_llm_json(
        model: str,
        prompt: str,
        validator=None,
        max_retries: int = 2,
        num_predict: int = 1500,
        temperature: float = 0.4,
        strict_json: bool = False,
) -> dict:
    """
    Single-turn call: get valid JSON (via _chat_json_with_repair), then, if
    `validator` flags the content as low-effort/placeholder-shaped, retry
    with corrective feedback before giving up.
    """
    messages = [{"role": "user", "content": prompt}]

    for attempt in range(max_retries + 1):
        remaining = max_retries - attempt
        parsed, messages = _chat_json_with_repair(model, messages, num_predict, temperature, strict_json, remaining)

        if isinstance(parsed, dict) and parsed.get("parse_error"):
            return parsed

        if validator and validator(parsed):
            print(f"  Low-effort/empty response detected (attempt {attempt + 1}/{max_retries + 1})")
            if attempt == max_retries:
                if isinstance(parsed, dict):
                    parsed["low_effort_warning"] = True
                    return parsed
                return {"items": parsed, "low_effort_warning": True}
            messages = messages + [{"role": "user", "content": _LOW_EFFORT_FEEDBACK}]
            continue

        return parsed

    return {"parse_error": True, "raw": ""}


def call_heatmap_pipeline(
        model: str,
        regions: list,
        metrics_json: str,
        max_retries: int = 2,
        num_predict: int = 1500,
        temperature: float = 0.4,
        strict_json: bool = False,
) -> dict:
    """
    Two sequential turns in one conversation:
      1. Score each pre-segmented region (flat array, no global synthesis yet).
      2. Ask for page-wide global_issues/fix_priority, explicitly grounded
         in the model's OWN answer from turn 1 (not a fresh, ungrounded ask).
    Splitting these turns -- rather than asking for everything at once --
    is what stops the model from falling back to copying the few-shot
    example for the more abstract "summarize the page" half of the task.
    """
    messages = [{"role": "user", "content": build_heatmap_entries_prompt(regions, metrics_json)}]
    region_lookup = {r["region_id"]: r for r in regions}

    entries = None
    for attempt in range(max_retries + 1):
        remaining = max_retries - attempt
        parsed, messages = _chat_json_with_repair(model, messages, num_predict, temperature, strict_json, remaining)

        if isinstance(parsed, dict) and parsed.get("parse_error"):
            return {"parse_errors": [{"stage": "heatmap_entries", "raw": parsed.get("raw", "")}]}

        if _is_low_effort_heatmap_entries(parsed, region_lookup):
            print(f"  Low-effort/empty heatmap entries detected (attempt {attempt + 1}/{max_retries + 1})")
            if attempt == max_retries:
                entries = parsed if isinstance(parsed, list) else []
                break
            messages = messages + [{"role": "user", "content": _HEATMAP_ENTRIES_FEEDBACK}]
            continue

        entries = parsed
        break

    result = {"heatmap": entries or []}
    warnings = []
    if not entries:
        warnings.append(
            "Heatmap entries stage returned no real findings after retries -- this may mean "
            "the model gave up rather than that the page is genuinely issue-free."
        )

    messages = messages + [{"role": "user", "content": build_global_issues_prompt()}]

    for attempt in range(max_retries + 1):
        remaining = max_retries - attempt
        parsed, messages = _chat_json_with_repair(model, messages, num_predict, temperature, strict_json, remaining)

        if isinstance(parsed, dict) and parsed.get("parse_error"):
            result.setdefault("parse_errors", []).append({"stage": "heatmap_global", "raw": parsed.get("raw", "")})
            break

        if _is_low_effort_global_issues(parsed):
            echoed = _contains_echoed_example_text(parsed) if isinstance(parsed, dict) else False
            print(f"  {'Echoed example text' if echoed else 'Low-effort/empty global issues'} "
                  f"detected (attempt {attempt + 1}/{max_retries + 1})")
            if attempt == max_retries:
                warnings.append(
                    "Global issues / fix priority still looked like copied example text or "
                    "empty placeholders after retries -- treat that section with skepticism."
                )
                cleaned = _clean_global_issues(parsed if isinstance(parsed, dict) else {})
                result["global_issues"] = cleaned["global_issues"]
                result["fix_priority"] = cleaned["fix_priority"]
                break
            feedback = _ECHOED_EXAMPLE_FEEDBACK if echoed else _LOW_EFFORT_FEEDBACK
            messages = messages + [{"role": "user", "content": feedback}]
            continue

        cleaned = _clean_global_issues(parsed)
        result["global_issues"] = cleaned["global_issues"]
        result["fix_priority"] = cleaned["fix_priority"]
        break

    if warnings:
        result["warnings"] = warnings

    return result


def analyze_page(
        model: str,
        title: str,
        text_excerpt: str,
        regions: list,
        metrics_json: str,
        structured_data: dict,
        temperature: float = 0.4,
        strict_json: bool = False,
) -> dict:
    print("SLM analysis: readability + article detection")
    page_placeholder = looks_like_placeholder_text(text_excerpt)
    readability = call_llm_json(
        model, build_readability_prompt(title, text_excerpt, metrics_json, structured_data, page_placeholder),
        validator=_is_low_effort_readability, temperature=temperature, strict_json=strict_json,
    )

    print("SLM analysis: heatmap (per-region, then page-wide synthesis)")
    heatmap = call_heatmap_pipeline(
        model, regions, metrics_json, temperature=temperature, strict_json=strict_json,
    )

    result = {}
    result.update({k: v for k, v in readability.items() if k not in ("parse_error", "low_effort_warning")})
    result.update({k: v for k, v in heatmap.items() if k not in ("parse_errors", "warnings")})

    parse_errors = []
    if readability.get("parse_error"):
        parse_errors.append({"stage": "readability", "raw": readability.get("raw", "")})
    parse_errors.extend(heatmap.get("parse_errors", []))
    if parse_errors:
        result["parse_errors"] = parse_errors

    warnings = []
    if readability.get("low_effort_warning"):
        warnings.append(
            "Readability/article-detection stage still looked empty/placeholder-shaped after "
            "retries -- treat those scores with skepticism."
        )
    warnings.extend(heatmap.get("warnings", []))
    if warnings:
        result["warnings"] = warnings

    return result


# =========================================================
# STAGE 4 - MARKDOWN GENERATION
# =========================================================

def build_markdown(
        url: str, title: str, result: dict, regions: list, metrics: dict,
        structured_data: dict, structure_findings: list, model: str, generated_at: str,
        profile_name: str = "generic",
) -> str:
    md = []

    md.append("# Semantic Heatmap Report\n")
    md.append(f"## URL\n{url}\n")
    if title:
        md.append(f"## Page Title\n{title}\n")
    md.append(f"## Generated\n{generated_at}\n")
    md.append(f"## Model\n{model}\n")

    md.append("---\n")
    md.append(f"## Page Score\n{result.get('page_score', 'N/A')}\n")

    if result.get("parse_errors"):
        md.append("---\n## ⚠ Parse Errors\n")
        md.append("One or more model calls did not return valid JSON even after a repair attempt. "
                  "Sections below from the failing stage(s) may be incomplete.\n")
        for err in result["parse_errors"]:
            md.append(f"### Stage: {err.get('stage')}")
            md.append("```")
            md.append((err.get("raw") or "")[:2000])
            md.append("```")

    if result.get("warnings"):
        md.append("---\n## ⚠ Low-Confidence Results\n")
        for w in result["warnings"]:
            md.append(f"- {w}")

    # ----------------------------
    # READABILITY
    # ----------------------------
    md.append("\n---\n## Readability\n")
    md.append(f"### Human Readability Score: {result.get('human_score', 'N/A')}/10")
    md.append(f"{result.get('human_summary', '')}\n")
    md.append(f"### AI Readability Score: {result.get('ai_score', 'N/A')}/10")
    md.append(f"{result.get('ai_summary', '')}\n")

    if result.get("top_issue"):
        md.append("#### Top Issue")
        md.append(f"- [ ] {result.get('top_issue')}")
        md.append(f"  - Fix: {result.get('top_issue_fix', '')}")

    # ----------------------------
    # ARTICLE DETECTION
    # ----------------------------
    md.append("\n---\n## Article Detection\n")
    md.append(f"- Is article: {result.get('is_article')}")
    md.append(f"- Type: {result.get('page_type')}")
    md.append(f"- Confidence: {result.get('confidence')}")
    md.append(f"- Reasoning: {result.get('reasoning')}")

    # ----------------------------
    # HEATMAP
    # ----------------------------
    md.append("\n---\n## Heatmap\n")
    region_lookup = {r["region_id"]: r for r in regions}

    for h in result.get("heatmap", []):
        rid = h.get("region_id")
        meta = region_lookup.get(rid, {})
        md.append(f"### Region {rid} ({meta.get('tag', '?')})")
        if meta.get("likely_placeholder"):
            md.append("> ⚠ Likely placeholder/lorem-ipsum text -- not real content")
        if meta.get("excerpt"):
            snippet = meta["excerpt"][:200].replace("\n", " ")
            md.append(f"> {snippet}")
        md.append(
            f"- Scores: H={h.get('human_readability')} | "
            f"AI={h.get('ai_readability')} | Semantic={h.get('semantic_quality')}"
        )
        if h.get("issue"):
            md.append(f"- [ ] Issue: {h.get('issue')}")
            md.append(f"  - Fix: {h.get('fix', '')}")

    # ----------------------------
    # GLOBAL ISSUES
    # ----------------------------
    md.append("\n---\n## Global Issues\n")
    for level in ["critical", "moderate", "minor"]:
        md.append(f"### {level.capitalize()}")
        for i in result.get("global_issues", {}).get(level, []):
            md.append(f"- [ ] {i}")

    # ----------------------------
    # FIX PRIORITY
    # ----------------------------
    md.append("\n---\n## Fix Priority\n")
    for f in result.get("fix_priority", []):
        md.append(f"- [ ] {f.get('task')} ({f.get('reason')})")

    # ----------------------------
    # PLACEHOLDER CONTENT (deterministic, computed in segment_regions)
    # ----------------------------
    placeholder_regions = [r for r in regions if r.get("likely_placeholder")]
    if placeholder_regions:
        md.append("\n---\n## ⚠ Placeholder Content Detected\n")
        md.append("These regions look like lorem-ipsum/fake-Latin filler text (heuristic match, "
                  "not a real language detector -- spot-check before trusting):\n")
        for r in placeholder_regions:
            md.append(f"- [ ] {r['region_id']} ({r['tag']}): {r['excerpt'][:100]}...")

    # ----------------------------
    # DEBUG OUTPUT (deterministic -- leaked PHP/template debug dumps)
    # ----------------------------
    debug_regions = [r for r in regions if r.get("has_debug_dump")]
    if debug_regions:
        md.append("\n---\n## 🚨 Exposed Debug Output Detected\n")
        md.append("These regions contain what looks like a leaked debug dump (e.g. a Twig "
                  "`{{ dump(var) }}` call left in a production template) -- raw object internals "
                  "rendering as visible page text. This is a real bug, not a content-quality issue:\n")
        for r in debug_regions:
            md.append(f"- [ ] {r['region_id']} ({r['tag']}) -- truncated content was excluded from analysis here")

    # ----------------------------
    # STRUCTURED DATA (deterministic -- parsed/validated in code, not LLM-judged)
    # ----------------------------
    md.append("\n---\n## Structured Data\n")
    json_ld = structured_data.get("json_ld", [])
    if not json_ld:
        md.append("- No JSON-LD found.")
    else:
        for i, block in enumerate(json_ld, 1):
            if block["valid_json"]:
                types = ", ".join(block["types"]) if block["types"] else "(no @type declared)"
                md.append(f"- JSON-LD block {i}: valid -- type(s): {types}")
            else:
                md.append(f"- [ ] JSON-LD block {i}: present but **not valid JSON** -- broken structured data")
    og = structured_data.get("open_graph", {})
    md.append(f"- OpenGraph tags: {len(og)} found" + (f" (og:type={og.get('og:type')})" if og.get("og:type") else ""))
    if not structured_data.get("meta_description"):
        md.append("- [ ] No meta description tag found")
    if structured_data.get("microdata_itemscope_count"):
        md.append(f"- Microdata itemscope elements: {structured_data['microdata_itemscope_count']}")

    # ----------------------------
    # STRUCTURAL BEST PRACTICES (deterministic, rule-based -- see audit_structure())
    # ----------------------------
    md.append("\n---\n## Structural Best Practices\n")
    profile_note = f" + '{profile_name}' profile" if profile_name != "generic" else ""
    md.append(f"*(Rule-based checks, not LLM-judged -- exact and reproducible every run. "
              f"Universal checks{profile_note}.)*\n")
    for level in ["critical", "moderate", "minor"]:
        level_findings = [f for f in structure_findings if f["severity"] == level]
        if level_findings:
            md.append(f"### {level.capitalize()}")
            for f in level_findings:
                md.append(f"- [ ] {f['message']}")
    info_findings = [f for f in structure_findings if f["severity"] == "info"]
    for f in info_findings:
        md.append(f"- ℹ {f['message']}")

    # ----------------------------
    # METRICS
    # ----------------------------
    md.append("\n---\n## Structural Metrics\n")
    md.append("```json")
    md.append(json.dumps(metrics, indent=2))
    md.append("```")

    return "\n".join(md)


# =========================================================
# PIPELINE
# =========================================================

def run(
        url: str,
        model: str,
        timeout: int,
        text_excerpt_chars: int,
        max_regions: int,
        use_cache: bool,
        out_dir: str,
        temperature: float = 0.4,
        strict_json: bool = False,
        profile_name: str = "generic",
        profile_file: str = None,
) -> Path:
    print("Fetching:", url)
    html = fetch_html(url, timeout=timeout, use_cache=use_cache)

    print("DOM extraction")
    extracted = extract_dom(html, profile_name=profile_name, profile_file=profile_file)

    print("Metrics")
    metrics = compute_metrics(extracted["dom"])

    print("Segmenting regions")
    regions = segment_regions(extracted["dom"], max_regions=max_regions)
    text_excerpt = extract_text_excerpt(extracted["dom"], max_chars=text_excerpt_chars)
    metrics_json = json.dumps(metrics, indent=2)

    result = analyze_page(
        model=model,
        title=extracted.get("title", ""),
        text_excerpt=text_excerpt,
        regions=regions,
        metrics_json=metrics_json,
        structured_data=extracted["structured_data"],
        temperature=temperature,
        strict_json=strict_json,
    )

    print("Markdown build")
    generated_at = datetime.now(timezone.utc)
    name = safe_report_name(url)
    timestamp = generated_at.strftime("%Y%m%dT%H%M%SZ")

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    path = out_path / f"report_{name}_{timestamp}.md"

    md = build_markdown(
        url=url,
        title=extracted.get("title", ""),
        result=result,
        regions=regions,
        metrics=metrics,
        structured_data=extracted["structured_data"],
        structure_findings=extracted["structure_findings"],
        model=model,
        generated_at=generated_at.isoformat(),
        profile_name=profile_name if not profile_file else f"custom ({profile_file})",
    )
    path.write_text(md, encoding="utf-8")

    print("Saved:", path)
    return path


# =========================================================
# CLI
# =========================================================

def main():
    parser = argparse.ArgumentParser(description="SLM-based website structure & readability auditor")
    parser.add_argument("url", help="URL to analyze")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Ollama model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTP fetch timeout in seconds")
    parser.add_argument(
        "--text-chars", type=int, default=DEFAULT_TEXT_EXCERPT_CHARS,
        help="Max characters of page text sent for the readability call",
    )
    parser.add_argument(
        "--max-regions", type=int, default=DEFAULT_MAX_REGIONS,
        help="Max number of segmented regions sent for the heatmap call",
    )
    parser.add_argument("--out-dir", default=".", help="Directory to write the report into")
    parser.add_argument("--no-cache", action="store_true", help="Bypass the local HTML cache and refetch")
    parser.add_argument(
        "--temperature", type=float, default=0.4,
        help="Sampling temperature for the model (default: 0.4)",
    )
    parser.add_argument(
        "--strict-json", action="store_true",
        help="Re-enable Ollama's format=\"json\" grammar-constrained decoding "
             "(guarantees valid JSON syntax but tends to thin out content on small models)",
    )
    parser.add_argument(
        "--profile", default="generic", choices=sorted(PROFILES.keys()),
        help=f"Structure profile for theme/CMS-specific region checks (default: generic). "
             f"Available: {', '.join(sorted(PROFILES.keys()))}",
    )
    parser.add_argument(
        "--profile-file", default=None,
        help="Path to a custom JSON profile (same shape as PROFILES entries in the script). "
             "Overrides --profile if given.",
    )
    args = parser.parse_args()

    run(
        url=args.url,
        model=args.model,
        timeout=args.timeout,
        text_excerpt_chars=args.text_chars,
        max_regions=args.max_regions,
        use_cache=not args.no_cache,
        out_dir=args.out_dir,
        temperature=args.temperature,
        strict_json=args.strict_json,
        profile_name=args.profile,
        profile_file=args.profile_file,
    )


if __name__ == "__main__":
    main()
