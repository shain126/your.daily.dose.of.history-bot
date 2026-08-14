"""Fetch a high-quality, permissively-licensed image from Wikimedia Commons.

The image is the hook on X, so this ranks candidates (resolution, real photo vs.
icon/map, permissive license) instead of grabbing the first search hit. Returns the
best match with an attribution string, or None so the caller can post text-only.

The interface (fetch_image -> dict|None) is intentionally simple so a paid AI-image
API can later be added as a fallback branch without touching callers.
"""
import html
import json
import re
import sys

import requests

API = "https://commons.wikimedia.org/w/api.php"
# Wikimedia requires a descriptive User-Agent.
USER_AGENT = "yddoseOfHistory-bot/1.0 (https://x.com/yddoseOfHistory)"
MIN_WIDTH = 1200      # minimum SOURCE resolution to consider an image
THUMB_WIDTH = 2048    # width of the scaled thumbnail we actually upload (keeps <5MB for X)
BAD_WORDS = (
    "logo", "icon", "map", "diagram", "flag", "coat_of_arms",
    "seal", "chart", "graph", "locator", "svg", "blank", "symbol",
)
GOOD_MIME = ("image/jpeg", "image/png")
PERMISSIVE = (
    "public domain", "pd", "cc0", "cc-zero", "cc by", "cc-by",
    "attribution", "creative commons",
)


def _strip_html(s):
    if not s:
        return ""
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def _is_permissive(license_short):
    ls = (license_short or "").lower()
    return any(p in ls for p in PERMISSIVE)


def _search(query, limit=12):
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": query, "gsrnamespace": "6", "gsrlimit": str(limit),
        "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
        # Ask Wikimedia for a scaled thumbnail too. X caps image uploads at ~5MB,
        # while Commons originals are often 10-30MB, so we upload the thumbnail.
        "iiurlwidth": str(THUMB_WIDTH),
    }
    r = requests.get(API, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})
    return list(pages.values())


def _evaluate(page):
    ii = (page.get("imageinfo") or [{}])[0]
    title = page.get("title", "").lower()
    mime = ii.get("mime", "")
    width = ii.get("width", 0) or 0
    meta = ii.get("extmetadata", {})
    license_short = meta.get("LicenseShortName", {}).get("value", "")

    if mime not in GOOD_MIME:
        return None
    if width < MIN_WIDTH:
        return None
    if any(b in title for b in BAD_WORDS):
        return None
    if not _is_permissive(license_short):
        return None

    artist = _strip_html(meta.get("Artist", {}).get("value", "")) or "Unknown"
    # Prefer the scaled thumbnail (small enough for X); fall back to the original.
    # `width` (the source resolution) is still used for ranking/filtering above.
    upload_url = ii.get("thumburl") or ii.get("url")
    return {
        "url": upload_url,
        "full_url": ii.get("url"),
        "width": width,
        "height": ii.get("height", 0),
        "mime": mime,
        "license": license_short,
        "attribution": f"{artist} / Wikimedia Commons ({license_short})",
        "descurl": ii.get("descriptionurl", ""),
        "title": page.get("title", ""),
    }


def fetch_image(query):
    try:
        pages = _search(query)
    except Exception as e:
        print(f"[image] search failed: {e}")
        return None
    candidates = [c for c in (_evaluate(p) for p in pages) if c]
    if not candidates:
        return None
    candidates.sort(key=lambda c: c["width"], reverse=True)
    return candidates[0]


def download_image(url, dest):
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60, stream=True)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
    return dest


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "Konark Sun Temple"
    img = fetch_image(q)
    print(json.dumps(img, indent=2, ensure_ascii=False) if img else "No suitable image found")
