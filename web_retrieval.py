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

MAX_PRIMARY_CHARS = 26000
MAX_RELATED_CHARS = 10000

MAX_LINKED_PAGES = 5
MAX_SEARCH_PAGES = 4
SEARCH_RESULT_LIMIT = 10


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
    "step-free",
    "step free",
    "barrier-free",
    "barrier free",
    "ramp",
    "ramps",
    "elevator",
    "elevators",
    "lift",
    "lifts",
    "wheelchair available",
    "wheelchairs available",
    "disabled parking",
    "accessible facilities",
    "accessible venue",
    "people of determination",
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
    "travel": 5,
    "travel-info": 7,
    "getting-here": 7,
    "venue-info": 7,
    "facilities": 7,
    "sustainability": 3,
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


SPECIFIC_ACCESSIBILITY_TERMS = [
    "wheelchair",
    "step-free",
    "step free",
    "barrier-free",
    "barrier free",
    "accessible entrance",
    "accessible parking",
    "disabled parking",
    "accessible seating",
    "accessible restroom",
    "accessible toilet",
    "ramp",
    "elevator",
    "lift",
    "caption",
    "cart",
    "sign language",
    "asl",
    "hearing loop",
    "assistive listening",
    "mobility assistance",
]


def has_specific_accessibility_signal(text: str) -> bool:
    normalized = normalize_text(text)
    return any(term in normalized for term in SPECIFIC_ACCESSIBILITY_TERMS)


def has_contact_signal(text: str) -> bool:
    normalized = normalize_text(text)
    if re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text or "", flags=re.I):
        return True
    return any(phrase in normalized for phrase in [
        "contact us",
        "contact the organiser",
        "contact the organizer",
        "general enquiries",
        "general inquiries",
        "customer service",
        "whatsapp",
    ])



def extract_contact_candidates(markdown: str, links: list[str], source_url: str) -> list[dict]:
    """Extract official contact/form candidates with nearby source context.

    These are evidence candidates only. The agent still decides whether a channel
    is accessibility-specific, event-specific, or merely general.
    """
    candidates: list[dict] = []
    seen: set[tuple[str, str]] = set()
    text = markdown or ""

    def add(kind: str, value: str, context: str = ""):
        clean_value = value.strip().rstrip('.,);]')
        key = (kind, clean_value.casefold())
        if not clean_value or key in seen:
            return
        seen.add(key)
        candidates.append({
            "type": kind,
            "value": clean_value,
            "source_url": source_url,
            "context": re.sub(r"\s+", " ", context).strip()[:500],
        })

    # Email addresses with nearby words so the agent can label their purpose.
    for match in re.finditer(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, flags=re.I):
        left = max(0, match.start() - 220)
        right = min(len(text), match.end() + 220)
        add("email", match.group(0), text[left:right])

    # International-style phone numbers. Require a leading + to avoid dates and IDs.
    for match in re.finditer(r"\+[0-9][0-9() .-]{7,}[0-9]", text):
        left = max(0, match.start() - 180)
        right = min(len(text), match.end() + 180)
        add("phone", match.group(0), text[left:right])

    # Form-like links, including trusted external form platforms linked by the
    # official event page. Being linked does not itself prove accessibility use;
    # the surrounding page text remains the evidence for that classification.
    for link in links or []:
        low = (link or "").lower()
        if not link:
            continue
        if any(token in low for token in (
            "docs.google.com/forms",
            "forms.gle",
            "forms.office.com",
            "formstack.com",
            "jotform.com",
            "/form/",
            "/forms/",
            "accommodation",
            "accessibility-request",
        )):
            add("form", link, "Linked from this official source page")

    return candidates


def page_role(url: str, primary_url: str) -> str:
    """Give the agent a simple source-role hint without making a verdict."""
    if url.rstrip('/') == primary_url.rstrip('/'):
        return "exact_event_page"
    low = url.lower()
    if "accessib" in low or "accommodation" in low:
        return "accessibility_or_accommodation_page"
    if "contact" in low or "enquir" in low or "inquir" in low:
        return "contact_page"
    if "faq" in low:
        return "faq_page"
    if any(x in low for x in ("venue", "visit", "travel", "getting-here", "facilities")):
        return "venue_or_visit_page"
    return "related_official_page"


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

        "has_specific_accessibility_signal":
            has_specific_accessibility_signal(
                markdown
            ),

        "has_request_signal":
            has_request_signal(
                markdown
            ),

        "has_contact_signal":
            has_contact_signal(
                markdown
            ),

        "contact_candidates":
            extract_contact_candidates(
                markdown,
                list(links)[:100],
                document_url(document) or url
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
    seen = {primary_url.rstrip("/")}

    for url in links:
        normalized_url = url.rstrip("/")
        if normalized_url in seen:
            continue
        seen.add(normalized_url)

        score = score_link(url, official_domain)
        if score <= 0:
            continue
        candidates.append((score, url))

    candidates.sort(key=lambda item: item[0], reverse=True)
    selected = [url for _, url in candidates[:MAX_LINKED_PAGES]]

    # Preserve source diversity. Contact pages can otherwise lose to several
    # high-scoring venue/accessibility pages even though the request path matters.
    contact_candidates = [
        url for _, url in candidates
        if any(token in url.lower() for token in ('contact', 'enquir', 'inquir', 'support', 'help'))
    ]
    if contact_candidates and not any(url in selected for url in contact_candidates):
        if len(selected) >= MAX_LINKED_PAGES:
            selected[-1] = contact_candidates[0]
        else:
            selected.append(contact_candidates[0])

    return selected


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

    # ONE bounded official-domain search. Do not require the event name because
    # venue/accessibility/contact pages often omit it entirely. Event-name overlap
    # is applied later as a ranking boost instead of a hard search constraint.
    query = (
        f'site:{official_domain} '
        f'accessibility accommodations contact venue wheelchair '
        f'"step free" ramps elevators captions'
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

        if "step free" in text or "step-free" in text:
            score += 7

        if "ramp" in text or "elevator" in text or "lift" in text:
            score += 6

        if "disabled parking" in text or "accessible parking" in text:
            score += 6

        if "caption" in text or "cart" in text:
            score += 6

        if "contact" in text or "enquir" in text or "inquir" in text:
            score += 3

        # Event-name overlap is a useful boost, but never a hard requirement.
        event_tokens = [
            token for token in re.findall(r"[a-z0-9]+", safe_event_name.lower())
            if len(token) >= 4
        ]
        if event_tokens and any(token in text for token in event_tokens[:8]):
            score += 3

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

        # Deterministically extracted channels from official pages. These are
        # candidates, not automatically accessibility-specific contacts.
        "contact_candidates": [],
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

    primary["source_role"] = "exact_event_page"

    result[
        "primary_source"
    ] = primary

    for candidate in primary.get("contact_candidates", []):
        enriched = dict(candidate)
        enriched["source_role"] = "exact_event_page"
        enriched["priority"] = 1
        result["contact_candidates"].append(enriched)

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

        role = page_role(page["url"], event_url)
        page["source_role"] = role
        priority = {
            "accessibility_or_accommodation_page": 2,
            "contact_page": 3,
            "faq_page": 3,
            "venue_or_visit_page": 3,
            "related_official_page": 4,
        }.get(role, 4)
        for candidate in page.get("contact_candidates", []):
            enriched = dict(candidate)
            enriched["source_role"] = role
            enriched["priority"] = priority
            result["contact_candidates"].append(enriched)

        # Keep accessibility/request evidence plus official contact pages.
        if (
            page["has_accessibility_signal"]
            or page["has_request_signal"]
            or page["has_contact_signal"]
        ):
            result["related_sources"].append(page)

    if selected_links:

        result[
            "retrieval_methods"
        ].append(
            "official_link_inspection"
        )

    # -----------------------------------------------------
    # 3. Decide whether we need Search fallback
    # -----------------------------------------------------

    specific_evidence_found = (
        primary["has_specific_accessibility_signal"]
        or any(
            source.get("has_specific_accessibility_signal")
            for source in result["related_sources"]
        )
    )

    request_path_found = (
        primary["has_request_signal"]
        or primary["has_contact_signal"]
        or any(
            source.get("has_request_signal") or source.get("has_contact_signal")
            for source in result["related_sources"]
        )
    )

    # A generic accessibility sentence is not enough to stop discovery.
    # Search once when either concrete accessibility evidence OR a usable
    # official request/contact path is still missing.
    needs_search = not specific_evidence_found or not request_path_found

    # -----------------------------------------------------
    # 4. ONE search fallback
    # -----------------------------------------------------

    if needs_search:

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

            role = page_role(page["url"], event_url)
            page["source_role"] = role
            priority = {
                "accessibility_or_accommodation_page": 2,
                "contact_page": 3,
                "faq_page": 3,
                "venue_or_visit_page": 3,
                "related_official_page": 4,
            }.get(role, 4)
            for contact in page.get("contact_candidates", []):
                enriched = dict(contact)
                enriched["source_role"] = role
                enriched["priority"] = priority
                result["contact_candidates"].append(enriched)

            if (
                page["has_accessibility_signal"]
                or page["has_request_signal"]
                or page["has_contact_signal"]
            ):
                result["related_sources"].append(page)

    # Deduplicate contact candidates and put event-specific evidence first.
    deduped_contacts = []
    seen_contacts = set()
    for candidate in sorted(
        result["contact_candidates"],
        key=lambda item: (item.get("priority", 9), item.get("type", ""), item.get("value", ""))
    ):
        key = (candidate.get("type"), str(candidate.get("value", "")).casefold())
        if key in seen_contacts:
            continue
        seen_contacts.add(key)
        deduped_contacts.append(candidate)
    result["contact_candidates"] = deduped_contacts[:20]

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