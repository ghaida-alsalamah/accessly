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
from urllib.parse import urlparse, urljoin

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
MAX_DISCOVERED_LINKS = 300


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
    "show-info": 8,
    "show-information": 8,
    "event-info": 7,
    "event-information": 7,
    "opening-hours": 8,
    "show-dates": 8,
    "show-times": 8,
    "visitor-information": 8,
    "visitor-info": 8,
    "planning-preparation": 8,
    "why-visit": 7,
    "schedule": 6,
    "agenda": 5,
    "when-where": 7,
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



YEAR_RE = re.compile(r"\b(20[1-3]\d)\b")
TIME_RE = re.compile(
    r"\b(?:[01]?\d|2[0-3])(?::[0-5]\d)?\s*(?:a\.?m\.?|p\.?m\.?)\b"
    r"|\b(?:[01]?\d|2[0-3]):[0-5]\d\b",
    flags=re.I,
)
MONTH_RE = re.compile(
    r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\b",
    flags=re.I,
)


def extract_years(text: str) -> list[int]:
    """Return distinct plausible calendar years in first-occurrence order."""
    seen = set()
    years = []
    for match in YEAR_RE.finditer(text or ""):
        year = int(match.group(1))
        if year not in seen:
            seen.add(year)
            years.append(year)
    return years


def infer_event_year(markdown: str, title: str = "") -> int | None:
    """Infer an event-year hint from the exact event page for evidence ranking."""
    title_years = extract_years(title)
    if title_years:
        return title_years[0]

    lines = (markdown or "").splitlines()[:180]
    for line in lines:
        low = normalize_text(line)
        if MONTH_RE.search(line) or any(k in low for k in ("date", "event date", "when")):
            years = extract_years(line)
            if years:
                return years[0]

    top_years = extract_years("\n".join(lines))
    return top_years[0] if top_years else None


def year_relevance(text: str, event_year: int | None) -> tuple[list[int], str]:
    """Describe source-year relevance without discarding any official evidence."""
    years = extract_years(text)
    if event_year is None:
        return years, "event_year_unknown"
    if not years:
        return years, "undated_or_not_year_specific"
    if event_year in years:
        return years, "matches_event_year"
    if max(years) < event_year:
        return years, "older_year_only"
    if min(years) > event_year:
        return years, "newer_year_only"
    return years, "other_years_only"


def extract_event_fact_snippets(markdown: str) -> dict[str, list[str]]:
    """Keep compact fact windows from full text before markdown truncation."""
    lines = [re.sub(r"\s+", " ", line).strip() for line in (markdown or "").splitlines()]
    categories: dict[str, list[str]] = {
        "time": [], "date": [], "location": [], "organizer": [], "contact": []
    }
    seen: dict[str, set[str]] = {key: set() for key in categories}

    def add(kind: str, idx: int):
        if len(categories[kind]) >= 6:
            return
        start = max(0, idx - 1)
        end = min(len(lines), idx + 2)
        window = " | ".join(x for x in lines[start:end] if x)[:700]
        key = normalize_text(window)
        if window and key not in seen[kind]:
            seen[kind].add(key)
            categories[kind].append(window)

    for idx, line in enumerate(lines):
        if not line:
            continue
        low = normalize_text(line)
        if TIME_RE.search(line) or any(k in low for k in (
            "opening hours", "show hours", "event hours", "event timings",
            "show timings", "visiting hours", "visitor hours", "opening times",
            "show times", "timings", "time:"
        )):
            add("time", idx)
        if (MONTH_RE.search(line) and YEAR_RE.search(line)) or any(k in low for k in ("event date", "date:")):
            add("date", idx)
        if any(k in low for k in ("location", "venue", "address", "getting here", "where:")):
            add("location", idx)
        if any(k in low for k in ("organised by", "organized by", "hosted by", "presented by", "event organiser", "event organizer")):
            add("organizer", idx)
        if ("@" in line or re.search(r"\+[0-9][0-9() .-]{7,}[0-9]", line)
                or any(k in low for k in ("contact us", "whatsapp", "general enquiries", "general inquiries", "customer service"))):
            add("contact", idx)

    return categories


def annotate_page_year_context(page: dict, event_year: int | None) -> dict:
    """Attach edition/freshness hints to a scraped official page.

    Use the title and leading content rather than the whole page so a footer
    copyright year does not make an older event-edition page look current.
    """
    leading = str(page.get("markdown", ""))[:7000]
    combined = f"{page.get('title', '')}\n{leading}"
    years, relevance = year_relevance(combined, event_year)
    page["years_mentioned"] = years
    page["year_relevance"] = relevance
    return page


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
    if any(x in low for x in (
        "show-info", "show-information", "event-info", "event-information",
        "opening-hours", "show-dates", "show-times", "visitor-information",
        "visitor-info", "planning-preparation", "why-visit", "schedule",
        "agenda", "when-where"
    )):
        return "event_information_page"
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

    page_url = document_url(document) or url
    normalized_links = []
    seen_links = set()
    for link in links:
        if not isinstance(link, str) or not link.strip():
            continue
        absolute = urljoin(page_url, link.strip())
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https"):
            continue
        absolute = absolute.split("#", 1)[0]
        key = absolute.rstrip("/")
        if key in seen_links:
            continue
        seen_links.add(key)
        normalized_links.append(absolute)
        if len(normalized_links) >= MAX_DISCOVERED_LINKS:
            break

    return {
        "url":
            page_url,

        "title":
            document_title(document),

        "markdown":
            markdown[:char_limit],

        "links":
            normalized_links,

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

        # Extract from FULL markdown so facts near the bottom of long pages are
        # not lost when the returned markdown is truncated.
        "event_fact_snippets":
            extract_event_fact_snippets(markdown),

        "contact_candidates":
            extract_contact_candidates(
                markdown,
                normalized_links,
                page_url
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
    """Select a small but functionally diverse set of official pages.

    Event homepages often contain hundreds of links. Pure score sorting can pick
    several pages from one category and miss the one page that contains opening
    hours or the current contact channel. We therefore reserve category slots,
    then fill remaining capacity by score. This is URL-pattern based and does not
    depend on any specific event or organization.
    """
    candidates = []
    seen = {primary_url.rstrip("/")}

    for raw_url in links:
        url = urljoin(primary_url, raw_url)
        normalized_url = url.rstrip("/")
        if normalized_url in seen:
            continue
        seen.add(normalized_url)

        score = score_link(url, official_domain)
        if score <= 0:
            continue
        candidates.append((score, url))

    candidates.sort(key=lambda item: item[0], reverse=True)

    category_tokens = {
        "accessibility": ("accessib", "accommodation", "special-assistance", "facilities"),
        "timing": (
            "show-info", "show-information", "event-info", "event-information",
            "opening-hours", "show-dates", "show-times", "visitor-information",
            "visitor-info", "planning-preparation", "why-visit", "schedule",
            "agenda", "when-where", "dates-times", "dates-and-times", "timings"
        ),
        "contact": ("contact", "enquir", "inquir", "customer-service", "support", "help"),
        "venue": ("venue", "travel", "getting-here", "location", "visit"),
        "faq": ("faq", "frequently-asked"),
    }

    selected: list[str] = []
    selected_keys: set[str] = set()

    def add(url: str) -> None:
        key = url.rstrip("/")
        if key in selected_keys or len(selected) >= MAX_LINKED_PAGES:
            return
        selected.append(url)
        selected_keys.add(key)

    # Reserve one slot for each useful page role when that role exists.
    for tokens in category_tokens.values():
        for _, url in candidates:
            low = url.lower()
            if any(token in low for token in tokens):
                add(url)
                break

    # Fill remaining slots by overall relevance.
    for _, url in candidates:
        add(url)
        if len(selected) >= MAX_LINKED_PAGES:
            break

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
        f'"step free" ramps elevators captions '
        f'"opening hours" timings "visitor information" schedule'
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

        if any(term in text for term in (
            "opening hours", "show hours", "event hours", "show timings",
            "event timings", "visitor information", "schedule", "agenda"
        )):
            score += 6

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
        "preferred_contact_candidates": [],
        "event_year_hint": None,
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

    event_year_hint = infer_event_year(primary.get("markdown", ""), primary.get("title", ""))
    result["event_year_hint"] = event_year_hint
    annotate_page_year_context(primary, event_year_hint)
    primary["source_role"] = "exact_event_page"

    result[
        "primary_source"
    ] = primary

    for candidate in primary.get("contact_candidates", []):
        enriched = dict(candidate)
        enriched["source_role"] = "exact_event_page"
        enriched["priority"] = 1
        enriched["source_year_relevance"] = primary.get("year_relevance")
        enriched["source_years"] = primary.get("years_mentioned", [])
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

        annotate_page_year_context(page, event_year_hint)
        role = page_role(page["url"], event_url)
        page["source_role"] = role
        priority = {
            "accessibility_or_accommodation_page": 2,
            "contact_page": 3,
            "event_information_page": 3,
            "faq_page": 3,
            "venue_or_visit_page": 3,
            "related_official_page": 4,
        }.get(role, 4)
        for candidate in page.get("contact_candidates", []):
            enriched = dict(candidate)
            enriched["source_role"] = role
            enriched["priority"] = priority
            enriched["source_year_relevance"] = page.get("year_relevance")
            enriched["source_years"] = page.get("years_mentioned", [])
            result["contact_candidates"].append(enriched)

        # Keep accessibility/request evidence plus official contact pages.
        if (
            page["has_accessibility_signal"]
            or page["has_request_signal"]
            or page["has_contact_signal"]
            or any(page.get("event_fact_snippets", {}).values())
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

    timing_found = bool(primary.get("event_fact_snippets", {}).get("time")) or any(
        source.get("event_fact_snippets", {}).get("time")
        for source in result["related_sources"]
    )

    # A generic accessibility sentence is not enough to stop discovery. Search
    # once when concrete accessibility evidence, a usable request/contact path,
    # OR basic event timing is still missing. This makes homepage research more
    # complete without crawling the whole site.
    needs_search = (
        not specific_evidence_found
        or not request_path_found
        or not timing_found
    )

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

            annotate_page_year_context(page, event_year_hint)
            role = page_role(page["url"], event_url)
            page["source_role"] = role
            priority = {
                "accessibility_or_accommodation_page": 2,
                "contact_page": 3,
                "event_information_page": 3,
                "faq_page": 3,
                "venue_or_visit_page": 3,
                "related_official_page": 4,
            }.get(role, 4)
            for contact in page.get("contact_candidates", []):
                enriched = dict(contact)
                enriched["source_role"] = role
                enriched["priority"] = priority
                enriched["source_year_relevance"] = page.get("year_relevance")
                enriched["source_years"] = page.get("years_mentioned", [])
                result["contact_candidates"].append(enriched)

            if (
                page["has_accessibility_signal"]
                or page["has_request_signal"]
                or page["has_contact_signal"]
                or any(page.get("event_fact_snippets", {}).values())
            ):
                result["related_sources"].append(page)

    # Deduplicate and rank contacts using generalized provenance signals.
    # A dedicated current contact/accessibility page may be more authoritative
    # than a generic widget on the event homepage, while an event-specific
    # channel still outranks unrelated organization-wide contacts.
    year_score = {
        "matches_event_year": 40,
        "undated_or_not_year_specific": 28,
        "event_year_unknown": 24,
        "other_years_only": 5,
        "newer_year_only": 0,
        "older_year_only": -80,
    }
    role_score = {
        "accessibility_or_accommodation_page": 55,
        "contact_page": 48,
        "exact_event_page": 45,
        "event_information_page": 36,
        "faq_page": 30,
        "venue_or_visit_page": 28,
        "related_official_page": 18,
    }

    def contact_context_score(candidate: dict) -> int:
        text = normalize_text(
            f"{candidate.get('context', '')} {candidate.get('source_url', '')}"
        )
        score = 0
        if any(x in text for x in (
            "accessibility", "accommodation", "disability", "special assistance"
        )):
            score += 45
        if any(x in text for x in (
            "visitor enquiries", "visitor inquiries", "attendee", "customer service",
            "event enquiries", "event inquiries", "contact us", "general enquiries",
            "general inquiries", "whatsapp"
        )):
            score += 22
        if any(x in text for x in (
            "sponsor", "exhibitor", "speaker", "media enquiry", "media inquiry",
            "press enquiry", "press inquiry", "careers", "recruitment"
        )):
            score -= 70
        return score

    # Count independent official-page support for each exact channel. Repetition
    # is only a modest boost; it never rescues an older-edition contact.
    support_urls: dict[tuple[str, str], set[str]] = {}
    for candidate in result["contact_candidates"]:
        key = (candidate.get("type", ""), str(candidate.get("value", "")).casefold())
        support_urls.setdefault(key, set()).add(str(candidate.get("source_url", "")))

    ranked_contacts = []
    for candidate in result["contact_candidates"]:
        key = (candidate.get("type", ""), str(candidate.get("value", "")).casefold())
        support_count = len(support_urls.get(key, set()))
        candidate = dict(candidate)
        candidate["supporting_source_count"] = support_count
        candidate["ranking_score"] = (
            year_score.get(candidate.get("source_year_relevance"), 0)
            + role_score.get(candidate.get("source_role"), 0)
            + contact_context_score(candidate)
            + min(max(support_count - 1, 0), 3) * 4
        )
        ranked_contacts.append(candidate)

    deduped_contacts = []
    seen_contacts = set()
    for candidate in sorted(
        ranked_contacts,
        key=lambda item: (
            -item.get("ranking_score", 0),
            item.get("priority", 9),
            item.get("type", ""),
            item.get("value", ""),
        )
    ):
        key = (candidate.get("type"), str(candidate.get("value", "")).casefold())
        if key in seen_contacts:
            continue
        seen_contacts.add(key)
        deduped_contacts.append(candidate)
    result["contact_candidates"] = deduped_contacts[:20]

    preferred = [
        c for c in deduped_contacts
        if c.get("source_year_relevance") != "older_year_only"
        and c.get("ranking_score", 0) > -20
    ]
    result["preferred_contact_candidates"] = (preferred or deduped_contacts)[:8]

    result[
        "status"
    ] = "success"

    result["retrieval_complete"] = True

    result["tool_guidance"] = (
        "Research for this event is complete. "
        "Do not call research_event again for links discovered in this result. "
        "Use primary_source, related_sources, event_fact_snippets, and pages_checked. "
        "Before saying a time or contact is not stated, inspect event_fact_snippets from every "
        "retrieved page and preferred_contact_candidates. For generic contact channels, a current "
        "dedicated official contact/customer-service page can outrank a homepage widget when its "
        "context is clearer. Prefer exact-event/current or undated official evidence "
        "over older_year_only evidence. Older-year-only evidence may describe a prior edition "
        "and must not silently be presented as current. "
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