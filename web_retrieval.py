"""
Accessly Web Retrieval Layer - V2

Flow:
1. Scrape the exact event URL.
2. Inspect useful official links already present on the event page.
3. Scrape only the best linked pages.
4. If accessibility evidence is still missing, run ONE official-domain search.
5. Scrape only the best search results.
6. Return evidence to the Accessly agent.

The retrieval layer does NOT decide:
AVAILABLE / UNKNOWN / NOT APPLICABLE.
"""

import json
import os
import re
import sys
from copy import deepcopy
from typing import Any
from urllib.parse import urlparse

import tldextract
from dotenv import load_dotenv
from firecrawl import Firecrawl


# ---------------------------------------------------------
# Environment
# ---------------------------------------------------------

load_dotenv()

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")

if not FIRECRAWL_API_KEY:
    raise RuntimeError(
        "FIRECRAWL_API_KEY is missing. Add it to your .env file."
    )

firecrawl = Firecrawl(
    api_key=FIRECRAWL_API_KEY
)

_tld_extract = tldextract.TLDExtract(
    suffix_list_urls=()
)

# Cache completed research by original event URL during the current process.
_RESEARCH_CACHE: dict[str, dict] = {}


# ---------------------------------------------------------
# Limits
# ---------------------------------------------------------

MAX_PRIMARY_CHARS = 18000
MAX_RELATED_CHARS = 8000

MAX_LINKED_PAGES = 2
MAX_SEARCH_PAGES = 2
SEARCH_RESULT_LIMIT = 5


# ---------------------------------------------------------
# Accessibility vocabulary
# ---------------------------------------------------------

ACCESSIBILITY_TERMS = [
    "wheelchair accessible",
    "wheelchair access",
    "wheelchair users",
    "accessible entrance",
    "accessible parking",
    "accessible seating",
    "accessible restroom",
    "accessible restrooms",
    "disability accommodation",
    "disability accommodations",
    "accessibility accommodation",
    "accessibility accommodations",
    "request accommodations",
    "request accommodation",
    "special assistance",
    "access needs",
    "sign language interpreter",
    "asl interpreter",
    "captioning",
    "closed captions",
    "disabled visitors",
    "visitors with disabilities",
    "mobility assistance",
]

REQUEST_TERMS = [
    "request accommodations",
    "request accommodation",
    "request disability accommodations",
    "accessibility request",
    "special assistance request",
    "accessibility contact",
    "accommodation request form",
]

POSITIVE_PATH_HINTS = {
    "accessibility": 10,
    "accommodation": 10,
    "special-assistance": 9,
    "visitor-guide": 8,
    "plan-visit": 8,
    "plan-your-visit": 8,
    "venue": 7,
    "visit": 6,
    "faq": 6,
    "contact": 5,
    "attendee": 5,
    "registration": 4,
    "register": 4,
    "travel": 4,
    "help": 4,
    "support": 4,
}

NEGATIVE_PATH_HINTS = [
    "/product/",
    "/products/",
    "/exhibitor/",
    "/exhibitors/",
    "/speaker/",
    "/speakers/",
    "/sponsor/",
    "/sponsors/",
    "/news/",
    "/blog/",
    "/blogs/",
    "/press/",
    "/careers/",
]


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def normalize_text(value: str | None) -> str:
    if not value:
        return ""

    return re.sub(
        r"\s+",
        " ",
        value
    ).strip().lower()


def registered_domain(url_or_host: str) -> str:
    host = urlparse(url_or_host).hostname

    if not host:
        host = url_or_host

    host = host.lower().strip(".")

    extracted = _tld_extract(host)

    return (
        extracted.top_domain_under_public_suffix
        or host
    )


def same_domain(
    url: str,
    official_domain: str
) -> bool:
    try:
        return (
            registered_domain(url)
            == official_domain
        )
    except Exception:
        return False


def safe_attribute(
    obj: Any,
    *names: str,
    default=None
):
    if obj is None:
        return default

    for name in names:

        if isinstance(obj, dict):
            value = obj.get(name)

            if value is not None:
                return value

        value = getattr(
            obj,
            name,
            None
        )

        if value is not None:
            return value

    return default


def document_url(
    document: Any
) -> str | None:

    direct = safe_attribute(
        document,
        "url"
    )

    if direct:
        return direct

    metadata = safe_attribute(
        document,
        "metadata"
    )

    return safe_attribute(
        metadata,
        "source_url",
        "sourceURL",
        "url"
    )


def document_title(
    document: Any
) -> str:

    title = safe_attribute(
        document,
        "title"
    )

    if title:
        return str(title)

    metadata = safe_attribute(
        document,
        "metadata"
    )

    return str(
        safe_attribute(
            metadata,
            "title",
            default=""
        )
        or ""
    )


def document_description(
    document: Any
) -> str:

    value = safe_attribute(
        document,
        "description"
    )

    if value:
        return str(value)

    metadata = safe_attribute(
        document,
        "metadata"
    )

    return str(
        safe_attribute(
            metadata,
            "description",
            default=""
        )
        or ""
    )


def has_accessibility_signal(
    text: str
) -> bool:

    text = normalize_text(text)

    return any(
        term in text
        for term in ACCESSIBILITY_TERMS
    )


def has_request_signal(
    text: str
) -> bool:

    text = normalize_text(text)

    return any(
        term in text
        for term in REQUEST_TERMS
    )


def extract_event_name(
    markdown: str,
    title: str,
    fallback_url: str
) -> str:

    headings = re.findall(
        r"^#\s+(.+?)\s*$",
        markdown or "",
        flags=re.MULTILINE
    )

    generic = {
        "home",
        "search",
        "events",
        "event",
        "welcome",
    }

    for heading in headings:

        cleaned = re.sub(
            r"[*_`]",
            "",
            heading
        ).strip()

        if (
            len(cleaned) >= 4
            and cleaned.lower()
            not in generic
        ):
            return cleaned[:180]

    if title:
        return title[:180]

    slug = (
        urlparse(fallback_url)
        .path
        .strip("/")
        .split("/")[-1]
    )

    return (
        slug
        .replace("-", " ")
        .replace("_", " ")
        .title()
    )


# ---------------------------------------------------------
# Page scraping
# ---------------------------------------------------------

def scrape_page(
    url: str,
    char_limit: int
) -> dict:

    document = firecrawl.scrape(
        url,
        formats=[
            "markdown",
            "links"
        ]
    )

    markdown = (
        safe_attribute(
            document,
            "markdown",
            default=""
        )
        or ""
    )

    links = (
        safe_attribute(
            document,
            "links",
            default=[]
        )
        or []
    )

    return {
        "url":
            document_url(document)
            or url,

        "title":
            document_title(document),

        "markdown":
            markdown[:char_limit],

        "links":
            list(links)[:100],

        "has_accessibility_signal":
            has_accessibility_signal(
                markdown
            ),

        "has_request_signal":
            has_request_signal(
                markdown
            ),
    }


# ---------------------------------------------------------
# Rank links already found on the event page
# ---------------------------------------------------------

def score_link(
    url: str,
    official_domain: str
) -> int:

    if not url:
        return -100

    if not same_domain(
        url,
        official_domain
    ):
        return -100

    lowered = url.lower()

    if any(
        hint in lowered
        for hint in NEGATIVE_PATH_HINTS
    ):
        return -100

    score = 0

    for hint, points in (
        POSITIVE_PATH_HINTS.items()
    ):
        if hint in lowered:
            score += points

    return score


def select_primary_links(
    links: list[str],
    primary_url: str,
    official_domain: str
) -> list[str]:

    candidates = []

    seen = {
        primary_url.rstrip("/")
    }

    for url in links:

        normalized = url.rstrip("/")

        if normalized in seen:
            continue

        seen.add(normalized)

        score = score_link(
            url,
            official_domain
        )

        if score <= 0:
            continue

        candidates.append(
            (
                score,
                url
            )
        )

    candidates.sort(
        key=lambda item: item[0],
        reverse=True
    )

    return [
        url
        for _, url in candidates[
            :MAX_LINKED_PAGES
        ]
    ]


# ---------------------------------------------------------
# Search fallback
# ---------------------------------------------------------

def search_official_domain(
    event_name: str,
    official_domain: str
) -> list[dict]:

    safe_event_name = (
        event_name
        .replace('"', "")
        .strip()
    )[:120]

    # ONE search instead of multiple searches.
    query = (
        f'site:{official_domain} '
        f'"{safe_event_name}" '
        f'accessibility wheelchair accommodations '
        f'"special assistance"'
    )

    result = firecrawl.search(
        query,
        limit=SEARCH_RESULT_LIMIT
    )

    web_results = (
        safe_attribute(
            result,
            "web",
            default=[]
        )
        or []
    )

    ranked = []

    for item in web_results:

        url = document_url(
            item
        )

        if not url:
            continue

        if not same_domain(
            url,
            official_domain
        ):
            continue

        lowered = url.lower()

        if any(
            hint in lowered
            for hint in NEGATIVE_PATH_HINTS
        ):
            continue

        title = document_title(
            item
        )

        description = document_description(
            item
        )

        text = normalize_text(
            f"{title} {description} {url}"
        )

        score = 0

        for hint, points in (
            POSITIVE_PATH_HINTS.items()
        ):
            if hint in lowered:
                score += points

        if (
            "accessibility" in text
            or "accommodation" in text
        ):
            score += 8

        if "wheelchair" in text:
            score += 6

        if "special assistance" in text:
            score += 6

        if score <= 0:
            continue

        ranked.append(
            {
                "url": url,
                "title": title,
                "description": description,
                "score": score,
            }
        )

    ranked.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    return ranked[
        :MAX_SEARCH_PAGES
    ]


# ---------------------------------------------------------
# Main retrieval pipeline
# ---------------------------------------------------------

def research_event(
    event_url: str
) -> dict:

    if not event_url.startswith(
        ("http://", "https://")
    ):
        raise ValueError(
            "A valid HTTP(S) event URL is required."
        )

    if not urlparse(
        event_url
    ).hostname:
        raise ValueError(
            "The event URL does not contain a valid hostname."
        )

    normalized_url = event_url.strip().rstrip("/")

    if normalized_url in _RESEARCH_CACHE:
        cached = deepcopy(_RESEARCH_CACHE[normalized_url])
        cached["cache_hit"] = True
        return cached

    official_domain = registered_domain(
        event_url
    )

    result = {
        "status": "unknown",
        "event_url": event_url,
        "event_name": None,
        "official_domain":
            official_domain,

        "primary_source":
            None,

        "related_sources":
            [],

        "retrieval_methods":
            [],

        "errors":
            [],

        "cache_hit": False,

        "retrieval_complete": False,

        "pages_checked": [],
    }

    # -----------------------------------------------------
    # 1. Direct event-page scrape
    # -----------------------------------------------------

    try:

        primary = scrape_page(
            event_url,
            MAX_PRIMARY_CHARS
        )

    except Exception as error:

        result[
            "errors"
        ].append(
            {
                "stage":
                    "direct_scrape",

                "error":
                    str(error),
            }
        )

        return result

    event_name = extract_event_name(
        markdown=
            primary["markdown"],

        title=
            primary["title"],

        fallback_url=
            event_url
    )

    primary[
        "event_name"
    ] = event_name

    result[
        "event_name"
    ] = event_name

    result[
        "primary_source"
    ] = primary

    if primary["url"] not in result["pages_checked"]:
        result["pages_checked"].append(primary["url"])

    result[
        "retrieval_methods"
    ].append(
        "firecrawl_direct_scrape"
    )

    # -----------------------------------------------------
    # 2. Inspect useful links already present on page
    # -----------------------------------------------------

    selected_links = (
        select_primary_links(
            links=
                primary["links"],

            primary_url=
                event_url,

            official_domain=
                official_domain
        )
    )

    for url in selected_links:

        try:

            page = scrape_page(
                url,
                MAX_RELATED_CHARS
            )

        except Exception as error:

            result[
                "errors"
            ].append(
                {
                    "stage":
                        "linked_page_scrape",

                    "url":
                        url,

                    "error":
                        str(error),
                }
            )

            continue

        if page["url"] not in result["pages_checked"]:
            result["pages_checked"].append(page["url"])

        # Only keep actual useful evidence pages.
        if (
            page[
                "has_accessibility_signal"
            ]
            or page[
                "has_request_signal"
            ]
        ):
            result[
                "related_sources"
            ].append(
                page
            )

    if selected_links:

        result[
            "retrieval_methods"
        ].append(
            "official_link_inspection"
        )

    # -----------------------------------------------------
    # 3. Decide whether we need Search fallback
    # -----------------------------------------------------

    evidence_found = (
        primary[
            "has_accessibility_signal"
        ]
        or primary[
            "has_request_signal"
        ]
        or bool(
            result[
                "related_sources"
            ]
        )
    )

    # -----------------------------------------------------
    # 4. ONE search fallback
    # -----------------------------------------------------

    if not evidence_found:

        try:

            search_results = (
                search_official_domain(
                    event_name=
                        event_name,

                    official_domain=
                        official_domain
                )
            )

            result[
                "retrieval_methods"
            ].append(
                "firecrawl_official_domain_search"
            )

        except Exception as error:

            result[
                "errors"
            ].append(
                {
                    "stage":
                        "official_domain_search",

                    "error":
                        str(error),
                }
            )

            search_results = []

        existing_urls = {
            primary[
                "url"
            ].rstrip("/")
        }

        existing_urls.update(
            source[
                "url"
            ].rstrip("/")
            for source in result[
                "related_sources"
            ]
        )

        for candidate in search_results:

            url = candidate[
                "url"
            ]

            if (
                url.rstrip("/")
                in existing_urls
            ):
                continue

            try:

                page = scrape_page(
                    url,
                    MAX_RELATED_CHARS
                )

            except Exception as error:

                result[
                    "errors"
                ].append(
                    {
                        "stage":
                            "search_result_scrape",

                        "url":
                            url,

                        "error":
                            str(error),
                    }
                )

                continue

            if page["url"] not in result["pages_checked"]:
                result["pages_checked"].append(page["url"])

            if (
                page[
                    "has_accessibility_signal"
                ]
                or page[
                    "has_request_signal"
                ]
            ):
                result[
                    "related_sources"
                ].append(
                    page
                )

    result[
        "status"
    ] = "success"

    result["retrieval_complete"] = True

    result["tool_guidance"] = (
        "Research for this event is complete. "
        "Do not call research_event again for links discovered in this result. "
        "Use the returned primary_source, related_sources, and pages_checked. "
        "Only use the browser if retrieval failed or interactive form inspection is required."
    )

    _RESEARCH_CACHE[normalized_url] = deepcopy(result)

    return result


# ---------------------------------------------------------
# Local test
# ---------------------------------------------------------

if __name__ == "__main__":

    if len(sys.argv) != 2:

        print(
            "Usage:\n"
            "python web_retrieval.py "
            "https://example.com/event"
        )

        raise SystemExit(1)

    result = research_event(
        sys.argv[1]
    )

    # Short summary first.
    print("\n=== ACCESSLY RETRIEVAL SUMMARY ===")
    print(
        "Status:",
        result["status"]
    )
    print(
        "Event:",
        result["event_name"]
    )
    print(
        "Domain:",
        result["official_domain"]
    )
    print(
        "Methods:",
        result["retrieval_methods"]
    )
    print(
        "Related sources:",
        len(
            result[
                "related_sources"
            ]
        )
    )
    print(
        "Errors:",
        len(
            result["errors"]
        )
    )

    print(
        "\n=== RESULT JSON ==="
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        )
    )