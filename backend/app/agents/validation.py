"""Claim validation: the gate between any generated text and the user.

A claim is rejected when

1. it cites an evidence id that does not exist,
2. it is a ``fact`` with no citations,
3. it contains a number that does not appear, with the same sign (after
   rounding to the claim's own precision), in the evidence it cites. This
   catches fabricated, mis-transcribed, and sign-flipped metrics, including
   ones injected through documents,
4. it contains a date (ISO or month-name) that is not in its cited evidence,
5. it states a percentage in words, or writes a number in a form the
   extractor cannot verify ("x52%", ".52", "was_52%"),
6. it is empty or unreasonably long,
7. it contains investment advice (buy/sell, price targets, upside) outside a
   verbatim quotation,
8. it is a ``fact`` that relies only on third-party text (headlines, user
   documents) without quoting it verbatim or attributing it to its source,
9. it names a metric next to a number ("volatility was 35%") and the number
   does not match that metric's cited value, or
10. it is an uncited interpretation (unless it states that evidence is
    insufficient), or mentions a year that its cited evidence does not.

Trust levels: numbers in the claim's own words must be supported by trusted
evidence (ARGUS-computed metrics, quotes, profile data). Third-party text can
only support a claim that quotes it verbatim or attributes it ("According to
the 10-K, ..."), so an instruction planted in a document cannot make ARGUS
state its contents as fact.

Syntactic validity of a citation is not treated as support: rules 3 and 4
check the claim's content against the cited items. Interpretations may draw
conclusions, but they may not introduce numbers or dates of their own.

Known limits: a number not directly bound to a metric name is matched
against any trusted number in the cited items; period descriptors such as
"over 5 years" are not compared with the analysis window.
"""

import re
import unicodedata
from dataclasses import dataclass

from app.agents.evidence import EvidenceLedger
from app.agents.models import Claim, ClaimKind, RejectedClaim, Section, ValidationSummary

MAX_CLAIM_CHARS = 700

# Models often emit typographic dashes/minus signs and non-breaking spaces
# (e.g. "2025‑10‑10" with U+2011). Normalize them so dates and numbers written
# that way are still checked instead of silently escaping validation.
_TYPOGRAPHY = str.maketrans({
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-",
    "―": "-", "−": "-", " ": " ", " ": " ", " ": " ",
})


def normalize_typography(text: str) -> str:
    # NFKC folds compatibility forms (fullwidth or small minus signs, fullwidth
    # digits) into ASCII before the typographic map handles dashes and spaces.
    return unicodedata.normalize("NFKC", text).translate(_TYPOGRAPHY)


_ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_MONTHS = {m: i for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), start=1)}
_MONTH_WORD = (
    r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?"
    r"|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
_DATE_MDY = re.compile(_MONTH_WORD + r"\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", re.IGNORECASE)
_DATE_DMY = re.compile(r"(\d{1,2})(?:st|nd|rd|th)?\s+" + _MONTH_WORD + r"\.?,?\s+(\d{4})", re.IGNORECASE)
# Proper names that contain numbers but are not quantities.
_NAMED_NUMBERS = re.compile(
    r"(?:S&P\s?(?:500|400|600)|Russell\s?(?:1000|2000|3000)|Nasdaq[- ]?100|"
    r"FTSE\s?(?:100|250)|Nikkei\s?225|DAX\s?40|CAC\s?40|Euro\s?Stoxx\s?50|Stoxx\s?600)\b",
    re.IGNORECASE,
)
# Period descriptors ("1-year window", "63-day", "52 weeks") are not quantities.
_PERIOD = re.compile(
    r"(?<![\w.])\d+\s?-?\s?(?:y|yr|yrs|years?|mo|months?|weeks?|days?|d|hours?|h)\b", re.IGNORECASE
)
_RANGE = re.compile(
    r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)\s?(%|percent)?\s?(?:-|to)\s?(\d[\d,]*(?:\.\d+)?)\s?(%|percent\b)",
    re.IGNORECASE,
)
_SPELLED_PERCENT = re.compile(
    r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
    r"fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|"
    r"eighty|ninety|hundred)(?:[\s-](?:one|two|three|four|five|six|seven|eight|nine))?"
    r"[\s-]+(?:percent|per cent|percentage points?)\b",
    re.IGNORECASE,
)
_NUMBER = re.compile(
    r"(?<![\w.])([-+]?)\$?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s?"
    r"(%|percent\b|trillion\b|billion\b|million\b|bn\b|mn\b|[TBMK]\b)?",
    re.IGNORECASE,
)
_NEGATIVE = re.compile(
    r"\b(?:fell|fall|falls|falling|lost|lose|loses|losing|loss|losses|declin\w*|drop\w*|down|"
    r"decreas\w*|drawdowns?|underperform\w*|slid|slump\w*|plung\w*|below|negative|minus|lower|worse)\b",
    re.IGNORECASE,
)
_POSITIVE = re.compile(
    r"\b(?:rose|rise|rises|rising|gain\w*|up|grew|grow\w*|increas\w*|outperform\w*|rall\w*|climb\w*|above)\b",
    re.IGNORECASE,
)
# Numbers glued to letters/underscores or written without a leading digit
# escape extraction, so they are rejected instead of silently ignored.
_UNVERIFIABLE_NUMBER = re.compile(r"(?<=[A-Za-z_])\d+(?:\.\d+)?\s?%|(?<![\w.])\.\d+|_\d")
_RECOMMENDATION = re.compile(
    r"\b(?:strong\s+(?:buy|sell)|buy(?!-and-hold|\s+and\s+hold|-side)\b|sell(?!-?off|-side)\b|accumulate|"
    r"price\s+targets?|target\s+price|upside\s+(?:of|to|potential)|downside\s+target|overweight|underweight|"
    r"go\s+(?:long|short)|short\s+the\s+stock|we\s+recommend|recommend(?:s|ed|ation|ations)?|"
    r"(?:should|must)\s+(?:buy|sell|hold|own|avoid|accumulate))\b",
    re.IGNORECASE,
)
_ATTRIBUTION = re.compile(
    r"\b(?:according\s+to|reports?|reported|states?|stated|says|said|notes?|noted|writes?|wrote|"
    r"discloses?|disclosed|headlines?|filing|transcript|annual\s+report|10-[KQ]|8-K|20-F|"
    r"mentions?|mentioned|describes?|described|cites?|cited|quotes?|quoted)\b",
    re.IGNORECASE,
)
_INSUFFICIENT = re.compile(
    r"\b(?:insufficient|not\s+enough|no\s+(?:evidence|data|document|passage|information)|"
    r"cannot\s+be\s+(?:determined|assessed|answered)|does\s+not\s+(?:address|support|cover)|"
    r"unavailable|not\s+available)\b",
    re.IGNORECASE,
)
_QUOTED = re.compile(r'“([^”]{3,})”|"([^"]{3,})"')
_BARE_YEAR = re.compile(r"(?<![\w.\-])(19\d{2}|20\d{2})(?![\w%]|\.\d)")
# A metric name directly followed by its value ("volatility was 35%",
# "beta is 1.20", "Sharpe ratio of 1.00"). Only such tight bindings are
# checked against the named metric, so threshold phrasing elsewhere in a
# sentence ("above the 1.20 threshold") is unaffected.
_METRIC_LABELS: dict[str, tuple[str, ...]] = {
    r"total\s+return": ("total return",),
    r"(?:annuali[sz]ed\s+return|cagr)": ("annualized return",),
    r"(?:annuali[sz]ed\s+)?volatility": ("volatility",),
    r"sharpe(?:\s+ratio)?": ("sharpe",),
    r"sortino(?:\s+ratio)?": ("sortino",),
    r"(?:max(?:imum)?\s+)?drawdown": ("drawdown",),
    r"(?:value\s+at\s+risk|var)": ("var",),
    r"(?:cvar|expected\s+shortfall)": ("cvar",),
    r"best\s+(?:day|daily\s+return)": ("best daily",),
    r"worst\s+(?:day|daily\s+return)": ("worst daily",),
    r"beta": ("beta",),
    r"alpha": ("alpha",),
    r"correlation": ("correlation",),
    r"tracking\s+error": ("tracking error",),
}
_BINDING_TAIL = (
    r"(?:\s*\([^)]{0,20}\))?\s*(?::|=|of|is|was|were|stood\s+at|came\s+in\s+at|reached|equal(?:s|led)?(?:\s+to)?|at)?"
    r"\s*(?:about|around|approximately|roughly|nearly)?\s*$"
)
_METRIC_BINDINGS = [
    (re.compile(r"\b" + pattern + _BINDING_TAIL, re.IGNORECASE), labels) for pattern, labels in _METRIC_LABELS.items()
]
_SCALE = {
    "t": 1e12, "trillion": 1e12,
    "b": 1e9, "billion": 1e9, "bn": 1e9,
    "m": 1e6, "million": 1e6, "mn": 1e6,
    "k": 1e3,
}


@dataclass(frozen=True)
class Quantity:
    value: float  # signed
    decimals: int
    percent: bool
    scaled: bool
    raw: str
    start: int = 0  # offsets in the normalized text the quantity was extracted from
    end: int = 0


def _iso(month: str, day: str, year: str) -> str | None:
    number = _MONTHS.get(month[:3].lower())
    if number is None or not 1 <= int(day) <= 31:
        return None
    return f"{int(year):04d}-{number:02d}-{int(day):02d}"


def extract_dates(text: str) -> list[str]:
    """ISO dates plus month-name dates ("March 9, 2009", "9 March 2009")."""
    text = normalize_typography(text)
    dates = _ISO_DATE.findall(text)
    dates += [d for m in _DATE_MDY.finditer(text) if (d := _iso(m.group(1), m.group(2), m.group(3)))]
    dates += [d for m in _DATE_DMY.finditer(text) if (d := _iso(m.group(2), m.group(1), m.group(3)))]
    return dates


def _direction(text: str, start: int, end: int) -> int:
    """+1 / -1 from the nearest direction word before the number (within its
    clause), else just after it; 0 when there is none."""
    before = re.split(r"[;:,()]", text[max(0, start - 40) : start])[-1]
    hits = [(m.end(), -1) for m in _NEGATIVE.finditer(before)]
    hits += [(m.end(), 1) for m in _POSITIVE.finditer(before)]
    if hits:
        return max(hits)[1]
    after = re.split(r"[;:,()]", text[end : end + 20])[0]
    if _NEGATIVE.search(after):
        return -1
    if _POSITIVE.search(after):
        return 1
    return 0


def extract_quantities(text: str) -> list[Quantity]:
    """Every number that carries meaning, with its sign.

    Removed before extraction: ISO and month-name dates (checked separately),
    index names such as "S&P 500", and period descriptors such as "1-year".
    Bare years (1900-2100) are skipped. Ranges ("10-25%") are expanded so both
    ends are checked. The sign comes from an explicit +/- or, failing that,
    from a nearby direction word ("fell", "drawdown" -> negative); an unsigned
    number with no direction word reads as positive."""
    return quantities_in(clean_for_extraction(text))


def clean_for_extraction(text: str) -> str:
    """Normalize typography and blank out numbers that are not quantities
    (dates, index names, period descriptors); expand ranges."""
    cleaned = normalize_typography(text)
    for pattern in (_ISO_DATE, _DATE_MDY, _DATE_DMY, _NAMED_NUMBERS, _PERIOD):
        cleaned = pattern.sub(" ", cleaned)
    return _RANGE.sub(
        lambda m: f"{m.group(1)}{m.group(2) or m.group(4)} to {m.group(3)}{m.group(4)}", cleaned
    )


def quantities_in(cleaned: str) -> list[Quantity]:
    """Quantities in text already passed through :func:`clean_for_extraction`
    (offsets refer to that text)."""
    out: list[Quantity] = []
    for match in _NUMBER.finditer(cleaned):
        sign, integer, fraction, suffix = match.groups()
        digits = integer.replace(",", "")
        decimals = len(fraction) - 1 if fraction else 0
        value = float(digits + (fraction or ""))
        unit = (suffix or "").lower()
        percent = unit in ("%", "percent")
        scale = _SCALE.get(unit, 1.0)
        if not percent and scale == 1.0 and decimals == 0 and "," not in integer and 1900 <= value <= 2100:
            continue  # a bare year
        if sign == "-":
            direction = -1
        elif sign == "+":
            direction = 1
        else:
            direction = _direction(cleaned, match.start(), match.end()) or 1
        out.append(Quantity(
            direction * value * scale, decimals, percent, scale != 1.0, match.group(0).strip(),
            match.start(), match.end(),
        ))
    return out


def _matches(claim_q: Quantity, evidence_q: Quantity) -> bool:
    if claim_q.percent != evidence_q.percent:
        return False
    if claim_q.value * evidence_q.value < 0:  # opposite signs never match
        return False
    a, b = abs(claim_q.value), abs(evidence_q.value)
    if claim_q.scaled or evidence_q.scaled:
        reference = max(a, b)
        return reference == 0 or abs(a - b) / reference <= 0.006
    if claim_q.decimals > evidence_q.decimals:
        return abs(a - b) < 1e-9
    return round(b, claim_q.decimals) == round(a, claim_q.decimals)


def _squash(text: str) -> str:
    text = normalize_typography(text).replace("…", " ").replace("“", '"').replace("”", '"')
    return " ".join(text.casefold().split())


def _split_quotes(text: str) -> tuple[list[str], str]:
    """Return (quoted segments, text with each quotation blanked out)."""
    quotes = [m.group(1) or m.group(2) for m in _QUOTED.finditer(text)]
    unquoted = _QUOTED.sub(lambda m: " " * len(m.group(0)), text)
    return quotes, unquoted


def _bound_labels(cleaned: str, quantity: Quantity) -> tuple[str, ...] | None:
    """Metric labels a number is directly attached to, if any."""
    before = cleaned[max(0, quantity.start - 60) : quantity.start]
    for pattern, labels in _METRIC_BINDINGS:
        if pattern.search(before):
            return labels
    return None


def _label_applies(label: str, keywords: tuple[str, ...], context: str) -> bool:
    """True when a metric label is the one a bound number refers to. A
    qualified label ("Benchmark total return", "Excess annualized return")
    applies only if its qualifier is also mentioned near the number."""
    for keyword in keywords:
        position = label.find(keyword)
        if position < 0:
            continue
        qualifier = label[:position].strip()
        if not qualifier or qualifier.split()[0] in context:
            return True
    return False


def validate_claim(claim: Claim, ledger: EvidenceLedger) -> list[str]:
    reasons: list[str] = []
    text = normalize_typography(claim.text).strip()
    if not text:
        return ["empty claim"]
    if len(text) > MAX_CLAIM_CHARS:
        reasons.append(f"longer than {MAX_CLAIM_CHARS} characters")
    unknown = [eid for eid in claim.evidence_ids if eid not in ledger]
    if unknown:
        reasons.append(f"cites unknown evidence: {', '.join(unknown)}")
    cited = [item for eid in claim.evidence_ids if (item := ledger.get(eid)) is not None]
    trusted = [item for item in cited if not item.untrusted]
    untrusted = [item for item in cited if item.untrusted]
    if claim.kind is ClaimKind.FACT and not cited:
        reasons.append("factual claim without supporting evidence")
    if claim.kind is ClaimKind.INTERPRETATION and not cited and not _INSUFFICIENT.search(text):
        reasons.append("interpretation without supporting evidence")

    quotes, unquoted = _split_quotes(text)
    # Quotations must be verbatim from a cited item; their contents are then
    # attributed source text rather than ARGUS's own assertion.
    cited_bodies = [_squash(f"{item.label} {item.statement}") for item in cited]
    for quote in quotes:
        fragment = _squash(quote)
        if fragment and not any(fragment in body for body in cited_bodies):
            reasons.append("quoted text does not appear verbatim in the cited evidence")
            break
    if _RECOMMENDATION.search(unquoted):
        reasons.append("investment advice (buy/sell, price targets, upside) is not allowed")

    names_source = any(
        name.casefold() in unquoted.casefold()
        for item in untrusted
        for name in (item.label.split(",")[0].strip(), item.source.split("(")[0].strip())
        if len(name) >= 3
    )
    attributed = bool(_ATTRIBUTION.search(unquoted)) or names_source
    if claim.kind is ClaimKind.FACT and cited and not trusted and not quotes and not attributed:
        reasons.append(
            "facts from third-party sources (headlines, documents) must be quoted verbatim "
            "or attributed to their source"
        )

    def support_from(items) -> list[Quantity]:
        body = normalize_typography(" ".join(f"{item.label} {item.statement} {item.as_of or ''}" for item in items))
        return extract_quantities(body)

    trusted_support = support_from(trusted)
    non_method_support = support_from([item for item in trusted if item.kind != "method"])
    third_party_support = support_from(untrusted) if attributed else []
    cleaned = clean_for_extraction(unquoted)
    for quantity in quantities_in(cleaned):
        labels = _bound_labels(cleaned, quantity)
        if labels is not None:
            context = cleaned[max(0, quantity.start - 60) : quantity.start].casefold()
            named = [
                item for item in trusted
                if item.kind == "metric" and _label_applies(item.label.casefold(), labels, context)
            ]
            candidates = support_from(named) if named else non_method_support + third_party_support
            if not any(_matches(quantity, c) for c in candidates):
                reasons.append(
                    f"number '{quantity.raw}' does not match the cited value of the metric it is attributed to"
                )
            continue
        if not any(_matches(quantity, c) for c in trusted_support + third_party_support):
            reasons.append(f"number '{quantity.raw}' is not in the cited evidence (with this sign)")

    support_text = normalize_typography(
        " ".join(f"{item.label} {item.statement} {item.as_of or ''}" for item in cited)
    )
    support_dates = set(extract_dates(support_text))
    for day in extract_dates(unquoted):
        if day not in support_dates:
            reasons.append(f"date {day} is not in the cited evidence")
    support_years = set(re.findall(r"(?:19|20)\d{2}", support_text))
    without_dates = normalize_typography(unquoted)
    for pattern in (_ISO_DATE, _DATE_MDY, _DATE_DMY):
        without_dates = pattern.sub(" ", without_dates)
    for year in _BARE_YEAR.findall(without_dates):
        if year not in support_years:
            reasons.append(f"year {year} is not in the cited evidence")
    if _SPELLED_PERCENT.search(unquoted):
        reasons.append("spelled-out quantities cannot be verified; use digits from the evidence")
    if _UNVERIFIABLE_NUMBER.search(normalize_typography(unquoted)):
        reasons.append("a number is written in a form that cannot be verified")
    return list(dict.fromkeys(reasons))


def validate_sections(
    sections: list[Section],
    ledger: EvidenceLedger,
    summary: ValidationSummary,
    max_claims_per_section: int | None = None,
) -> list[Section]:
    """Return sections containing only accepted claims; record rejections.

    ``max_claims_per_section`` (used for model output) rejects claims beyond
    the cap instead of silently truncating them, and duplicate claims within
    a section are rejected rather than shown twice."""
    accepted_sections: list[Section] = []
    for section in sections:
        kept: list[Claim] = []
        seen: set[str] = set()
        for index, claim in enumerate(section.claims):
            summary.claims_total += 1
            # de-duplicate citations while preserving order
            claim = claim.model_copy(update={"evidence_ids": list(dict.fromkeys(claim.evidence_ids))})
            reasons = validate_claim(claim, ledger)
            key = _squash(claim.text)
            if key in seen:
                reasons.append("duplicate of another claim in this section")
            if max_claims_per_section is not None and index >= max_claims_per_section:
                reasons.append(f"exceeds the limit of {max_claims_per_section} claims per section")
            if reasons:
                summary.claims_rejected += 1
                summary.rejected.append(RejectedClaim(section=section.key, text=claim.text, reasons=reasons))
            else:
                summary.claims_accepted += 1
                seen.add(key)
                kept.append(claim)
        accepted_sections.append(section.model_copy(update={"claims": kept}))
    return accepted_sections
