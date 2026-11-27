#!/usr/bin/env python3
"""Update the Agent Medicare Hub SEP tracker from a HealthSpring DST-SEP notice.

This script writes local files only. It does not deploy to production and
does not merge anything. Use --preview (via preview_deploy.py) for a
Netlify draft URL after reviewing the diff.

Examples:
  python3 sep-tracker/update_from_healthspring.py \\
      --replace-json sep-tracker/data/source_2026-10-21.json \\
      --email sep-tracker/data/healthspring-2026-11-27.txt \\
      --as-of 2026-11-27 --keep-hub-unique --write
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
JSON_PATH = ROOT / "data" / "seps.json"
YEARROUND_PATH = ROOT / "data" / "yearround.json"
HTML_PATH = REPO / "pages" / "sep-tracker-app.html"
SHELL_PAGES = [
    REPO / "pages" / "sep-tracker.html",
    REPO / "pages" / "es" / "sep-tracker.html",
]

EXPIRING_DAYS = 30
STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "PR": "Puerto Rico", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "GU": "Guam",
    "AS": "American Samoa", "MP": "Northern Mariana Islands", "VI": "U.S. Virgin Islands",
}

GENERIC_TOKENS = {
    "severe", "storms", "storm", "flooding", "flood", "weather", "conditions",
    "event", "the", "and", "of", "a", "in", "on", "for", "from", "with", "county",
    "counties", "fire", "fires", "wildfire", "wildfires", "state", "local",
    "declaration", "fema", "previously", "potential", "tropical", "cyclone",
    "nine", "fka", "aka", "thru", "through",
}


def iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def parse_iso(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def parse_mdy(s: str) -> date:
    s = s.strip()
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date: {s!r}")


def parse_any_date(s: str) -> date | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return parse_mdy(s)
    except ValueError:
        pass
    s2 = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", s)
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(s2, fmt).date()
        except ValueError:
            continue
    return None


def fmt_long(d: date) -> str:
    return d.strftime("%b %-d, %Y")


def fmt_window(start: date | None, end: date | None, *, ongoing: bool = False) -> str:
    if start and ongoing:
        return f"{fmt_long(start)} \u2013 ongoing"
    if start and end:
        return f"{fmt_long(start)} \u2013 {fmt_long(end)}"
    if start:
        return fmt_long(start)
    return ""


def live_status(term: date | None, today: date) -> tuple[str, int | None, int | None]:
    if term is None:
        return "active", None, None
    days = (term - today).days
    if days < 0:
        return "ended", None, -days
    if days <= EXPIRING_DAYS:
        return "expiring", days, None
    return "active", days, None


def refresh_item(item: dict, today: date) -> None:
    if item.get("status") == "yearround":
        item["days_until_expiry"] = None
        item["days_since_expiry"] = None
        return
    term = parse_iso(item.get("sep_termination"))
    status, until, since = live_status(term, today)
    item["status"] = status
    item["days_until_expiry"] = until
    item["days_since_expiry"] = since


def disaster_meta(kind: str, name: str) -> tuple[str, list[str]]:
    n = name.lower()
    if kind == "fire" or "fire" in n or "wildfire" in n or "burn ban" in n:
        return "Fires/Wildfires", ["Fires/Wildfires"]
    if "typhoon" in n or "hurricane" in n:
        return "Hurricane/Typhoon", ["Hurricane/Typhoon"]
    if "tropical storm" in n:
        return "Tropical Storm", ["Tropical Storm"]
    if "tornado" in n:
        return "Tornado", ["Tornado"]
    if "flood" in n:
        return "Floods", ["Floods"]
    if "drought" in n:
        return "Drought", ["Drought"]
    if "winter" in n:
        return "Storms - Snowstorm/Blizzard/Mix", ["Storms"]
    return "Storms - Rain", ["Storms"]


def parse_counties(raw: str, statewide: bool = False) -> tuple[list[str], str]:
    if statewide or re.search(r"^\s*(all counties|statewide|all)\s*$", raw or "", re.I):
        return ["STATEWIDE"], "All Counties"
    text = (raw or "").strip()
    text = re.sub(r"\s+for SEP purposes:?\s*", " ", text, flags=re.I)
    text = re.sub(
        r"\s+(Counties|County|Boroughs|Borough|Parishes|Parish)\.?$",
        "",
        text,
        flags=re.I,
    )
    text = text.replace(" and ", ", ")
    parts = [re.sub(r"\s+", " ", p).strip(" .") for p in text.split(",")]
    parts = [p for p in parts if p]
    pretty = ", ".join(parts)
    if len(parts) == 1:
        pretty += " County"
    elif len(parts) > 1:
        pretty = ", ".join(parts[:-1]) + ", and " + parts[-1]
    return parts, pretty


def is_statewide(counties) -> bool:
    if counties in ("ALL", "All Counties", "STATEWIDE", "all"):
        return True
    if isinstance(counties, list):
        if not counties:
            return False
        if len(counties) == 1 and str(counties[0]).strip().lower() in {
            "statewide", "all counties", "all", "all county",
        }:
            return True
    return False


def normalize_name(s: str) -> str:
    s = (s or "").lower()
    s = s.replace("\u2014", "-").replace("\u2013", "-")
    s = re.sub(r"\bmigration\b", "immigration", s)
    s = re.sub(r"\d{1,2}/\d{1,2}/\d{2,4}", " ", s)
    s = re.sub(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _state_words() -> set[str]:
    words = set()
    for code, name in STATE_NAMES.items():
        words.add(code.lower())
        words.update(name.lower().split())
    return words


STATE_WORDS = _state_words()


def name_tokens(s: str, state: str | None = None) -> list[str]:
    drop = set(GENERIC_TOKENS) | STATE_WORDS
    if state:
        drop.add(state.lower())
    return [w for w in normalize_name(s).split() if w not in drop and len(w) > 1]


def generic_name_key(s: str, state: str | None = None) -> str:
    """Normalized name keeping disaster-type words, dropping state and dates."""
    drop = set(STATE_WORDS)
    if state:
        drop.add(state.lower())
    return " ".join(w for w in normalize_name(s).split() if w not in drop and len(w) > 1)


def dates_compatible(start_a: date | None, start_b: date | None, window_days: int = 45) -> bool:
    if start_a is None or start_b is None:
        return True
    return abs((start_a - start_b).days) <= window_days


def same_declaration(
    name_a: str,
    state_a: str,
    name_b: str,
    state_b: str,
    start_a: date | None = None,
    start_b: date | None = None,
) -> bool:
    if state_a != state_b:
        return False
    a, b = name_tokens(name_a, state_a), name_tokens(name_b, state_b)
    if a and b:
        sa, sb = " ".join(a), " ".join(b)
        distinctive = False
        if sa == sb:
            distinctive = True
        else:
            shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
            if len(shorter) >= 2 and set(shorter) <= set(longer):
                distinctive = True
            elif len(shorter) == 1 and len(shorter[0]) >= 5 and shorter[0] in set(longer):
                distinctive = True
            else:
                inter = set(a) & set(b)
                union = set(a) | set(b)
                if len(inter) >= 2 and len(inter) / len(union) >= 0.6:
                    distinctive = True
        if distinctive:
            return dates_compatible(start_a, start_b)
    # Generic titles like "Flooding" or "Severe Storms" have no distinctive tokens.
    # Require an exact key match, or a 2+ token subset. A single generic word such
    # as "flooding" must not match "Hill Country Heavy Rainfall and Flooding".
    ka, kb = generic_name_key(name_a, state_a), generic_name_key(name_b, state_b)
    if ka and kb:
        if ka == kb and dates_compatible(start_a, start_b):
            return True
        ta, tb = ka.split(), kb.split()
        shorter, longer = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
        if len(shorter) >= 2 and set(shorter) <= set(longer) and dates_compatible(start_a, start_b):
            return True
    return False


def next_numeric_id(items: list[dict]) -> int:
    nums = [int(x["id"].split("-")[1]) for x in items if re.fullmatch(r"sep-\d+", x.get("id") or "")]
    return (max(nums) + 1) if nums else 1


def declarations_list(item: dict) -> list[str]:
    raw = item.get("declaration_number")
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    return [p.strip() for p in re.split(r"[,;]", str(raw)) if p.strip()]


def data_counties(item: dict):
    counties = item.get("counties")
    if is_statewide(counties) or is_statewide(item.get("counties_raw")):
        return "ALL"
    if isinstance(counties, list):
        cleaned = [re.sub(r"^and\s+", "", c).strip(" .") for c in counties if str(c).strip()]
        return cleaned
    if isinstance(counties, str) and counties.strip():
        return counties.strip()
    return item.get("counties_raw") or ""


def item_to_data(item: dict, sort_rank: int) -> dict:
    inc_s = parse_iso(item.get("incident_effective"))
    inc_e = parse_iso(item.get("incident_termination"))
    sep_s = parse_iso(item.get("sep_effective"))
    sep_e = parse_iso(item.get("sep_termination"))
    ongoing = bool(item.get("incident_ongoing")) or (
        inc_s is not None and inc_e is None and item.get("status") != "ended"
    )
    return {
        "id": item["id"],
        "state": item.get("state") or "",
        "type": item.get("disaster_type_raw") or (item.get("disaster_types") or [""])[0],
        "name": item.get("declaration_name") or item.get("name") or "",
        "incidentWindow": item.get("incidentWindow") or fmt_window(inc_s, inc_e, ongoing=ongoing),
        "sepWindow": item.get("sepWindow") or fmt_window(sep_s, sep_e),
        "sepEnd": item.get("sepEnd") if "sepEnd" in item else (iso(sep_e) or ""),
        "status": item.get("status") or "active",
        "sortRank": sort_rank,
        "counties": data_counties(item) if "counties" in item or "counties_raw" in item else item.get("counties", ""),
        "declarations": item.get("declarations") if isinstance(item.get("declarations"), list) else declarations_list(item),
    }


def parse_window_dates(window: str) -> tuple[date | None, date | None, bool]:
    if not window:
        return None, None, False
    ongoing = "ongoing" in window.lower()
    parts = re.split(r"\s+[\u2013\-]\s+", window, maxsplit=1)
    start = parse_any_date(parts[0]) if parts else None
    end = None
    if len(parts) == 2 and not ongoing:
        end = parse_any_date(parts[1])
    return start, end, ongoing


def data_to_item(d: dict, today: date) -> dict:
    inc_s, inc_e, inc_ong = parse_window_dates(d.get("incidentWindow") or "")
    sep_s, sep_e, _ = parse_window_dates(d.get("sepWindow") or "")
    if d.get("sepEnd"):
        sep_e = parse_iso(d.get("sepEnd")) or sep_e
    counties = d.get("counties")
    statewide = is_statewide(counties)
    if isinstance(counties, str) and not statewide:
        counties_list, counties_raw = parse_counties(counties, False)
    elif isinstance(counties, list):
        counties_list, counties_raw = counties, ", ".join(counties)
    else:
        counties_list, counties_raw = ["STATEWIDE"], "All Counties"
    name = d.get("name") or ""
    dtype = d.get("type") or disaster_meta("", name)[0]
    item = {
        "id": d["id"],
        "raw_status": "SEP - In Progress/No Change",
        "status": d.get("status") or "active",
        "entity": "FEMA" if "fema" in name.lower() else "State/Local Declaration",
        "state": d.get("state") or "",
        "state_raw": d.get("state") or "",
        "lookback": "30 days" if "fema" in name.lower() else "60 days",
        "declaration_name": name,
        "declaration_number": ", ".join(d.get("declarations") or []) or None,
        "disaster_type_raw": dtype,
        "disaster_types": [dtype] if dtype else [],
        "declaration_type": "Fire Management (FM)" if "fema" in name.lower() and "fire" in name.lower() else "Emergency (EM)",
        "counties": counties_list,
        "counties_raw": counties_raw,
        "declaration_date": iso(inc_s) or iso(today),
        "incident_effective": iso(inc_s),
        "incident_termination": None if inc_ong else iso(inc_e),
        "sep_effective": iso(sep_s),
        "sep_termination": iso(sep_e),
        "days_until_expiry": None,
        "days_since_expiry": None,
        "incident_ongoing": inc_ong,
        "retained_from_hub": True,
    }
    refresh_item(item, today)
    return item


def counts(items: list[dict]) -> dict:
    return {
        "total": len(items),
        "active": sum(1 for x in items if x["status"] == "active"),
        "expiring": sum(1 for x in items if x["status"] == "expiring"),
        "ended": sum(1 for x in items if x["status"] == "ended"),
        "yearround": sum(1 for x in items if x["status"] == "yearround"),
        "fl_active": sum(1 for x in items if x.get("state") == "FL" and x["status"] in ("active", "expiring")),
    }


def parse_healthspring_email(text: str) -> list[dict]:
    """Parse HealthSpring weekly DST-SEP blocks into structured updates."""
    # Drop tracking URLs so they cannot confuse the county lists.
    text = re.sub(r"https?://\S+", " ", text)
    text = text.replace("\r\n", "\n")
    # Current section state (two-letter code if we can map the heading)
    name_to_code = {v.lower(): k for k, v in STATE_NAMES.items()}
    updates: list[dict] = []
    current_state = None
    blocks = re.split(r"\n(?=Declaration information)", text, flags=re.I)
    # Also allow a heading that sets the state before a block.
    preamble = blocks[0] if blocks else ""
    heading_state = None

    def detect_state(chunk: str) -> str | None:
        # A standalone state name line, or "DST-SEPs in Florida and Texas"
        for line in chunk.splitlines():
            line_s = line.strip().rstrip(":")
            if line_s.lower() in name_to_code:
                return name_to_code[line_s.lower()]
        return None

    # Walk the text assigning state from headings that appear before each block.
    # Rebuild with a simple line scan for robustness.
    current_state = None
    pending: dict | None = None

    def flush():
        nonlocal pending
        if pending and pending.get("title") and pending.get("state"):
            updates.append(pending)
        pending = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        st = name_to_code.get(line.rstrip(":").lower())
        if st:
            flush()
            current_state = st
            continue
        mflag = re.search(r"Declaration information[^\n]*\((Renewed|Amended|New)\)", line, re.I)
        if not mflag:
            mflag = re.search(r"^Declaration information", line, re.I)
            flag = "Updated" if mflag else None
        else:
            flag = mflag.group(1).title()
        if mflag:
            flush()
            pending = {"state": current_state, "flag": flag or "Updated", "counties_raw": None}
            continue
        if pending is None:
            continue
        m = re.search(r"(?:State declaration|declaration)\s*:\s*(.+)$", line, re.I)
        if m and "SEP incident" not in line and "effective" not in line.lower():
            pending["title"] = m.group(1).strip()
            continue
        m = re.search(r"SEP incident dates?:\s*(\d{1,2}/\d{1,2}/\d{2,4})\s*[-–—]\s*(\d{1,2}/\d{1,2}/\d{2,4})", line, re.I)
        if m:
            pending["incident_start"] = parse_mdy(m.group(1))
            pending["incident_end"] = parse_mdy(m.group(2))
            continue
        m = re.search(r"(?:This SEP declaration is effective|effective)\s*:\s*(\d{1,2}/\d{1,2}/\d{2,4})\s*[-–—]\s*(\d{1,2}/\d{1,2}/\d{2,4})", line, re.I)
        if m:
            pending["sep_start"] = parse_mdy(m.group(1))
            pending["sep_end"] = parse_mdy(m.group(2))
            continue
        m = re.search(r"Impacted counties for SEP purposes:\s*(.+)$", line, re.I)
        if m:
            pending["counties_raw"] = m.group(1).strip()
            continue
        # Continuation of a county list
        if pending.get("counties_raw") and not re.search(r"declaration|incident|effective|IMPORTANT|SEP ", line, re.I):
            pending["counties_raw"] = pending["counties_raw"] + " " + line
    flush()
    return updates


def find_update_target(items: list[dict], upd: dict) -> dict | None:
    state = upd.get("state")
    title = upd.get("title") or ""
    title_tokens = name_tokens(title, state)
    start = upd.get("incident_start") or upd.get("sep_start")
    scored = []
    for x in items:
        if x.get("state") != state:
            continue
        if not same_declaration(
            title,
            state,
            x.get("declaration_name") or "",
            state,
            start,
            parse_iso(x.get("incident_effective")) or parse_iso(x.get("sep_effective")),
        ):
            continue
        xt = name_tokens(x.get("declaration_name") or "", state)
        overlap = len(set(title_tokens) & set(xt))
        # Strong preference for titles that actually share distinctive tokens
        name = (x.get("declaration_name") or "").lower()
        ended_split = 1 if re.search(r"\([12]\)|ended as of", name) else 0
        scored.append((0 if overlap else 1, ended_split, -overlap, x))
    if not scored:
        return None
    scored.sort(key=lambda r: (r[0], r[1], r[2]))
    best = scored[0]
    # If the update has distinctive tokens, reject a 0-overlap generic hit
    if title_tokens and best[0] == 1:
        return None
    return best[3]


def apply_email_updates(items: list[dict], updates: list[dict], today: date) -> tuple[list[dict], list[dict], list[dict]]:
    added: list[dict] = []
    changed: list[dict] = []
    next_id = next_numeric_id(items)
    for upd in updates:
        if not upd.get("state") or not upd.get("title"):
            continue
        if not upd.get("sep_start") or not upd.get("sep_end"):
            continue
        target = find_update_target(items, upd)
        counties_raw = upd.get("counties_raw")
        has_counties = bool(counties_raw) and "not listed" not in (counties_raw or "").lower()
        if target:
            before = {
                "incident_effective": target.get("incident_effective"),
                "incident_termination": target.get("incident_termination"),
                "sep_effective": target.get("sep_effective"),
                "sep_termination": target.get("sep_termination"),
                "counties": list(target.get("counties") or []),
            }
            target["raw_status"] = f"SEP - {upd.get('flag') or 'Renewed'}"
            if upd.get("incident_start"):
                target["incident_effective"] = iso(upd["incident_start"])
            if upd.get("incident_end"):
                target["incident_termination"] = iso(upd["incident_end"])
                target["incident_ongoing"] = False
            target["sep_effective"] = iso(upd["sep_start"])
            target["sep_termination"] = iso(upd["sep_end"])
            if has_counties:
                counties, label = parse_counties(counties_raw, False)
                target["counties"] = counties
                target["counties_raw"] = label
            refresh_item(target, today)
            after = {
                "incident_effective": target.get("incident_effective"),
                "incident_termination": target.get("incident_termination"),
                "sep_effective": target.get("sep_effective"),
                "sep_termination": target.get("sep_termination"),
                "counties": list(target.get("counties") or []),
            }
            if before != after:
                changed.append(target)
        else:
            state = upd["state"]
            title = upd["title"]
            dtype_raw, dtypes = disaster_meta("", title)
            counties, label = parse_counties(counties_raw or "All Counties", not has_counties)
            item = {
                "id": f"sep-{next_id:04d}",
                "raw_status": f"SEP - {upd.get('flag') or 'New'}",
                "status": "active",
                "entity": "State/Local Declaration",
                "state": state,
                "state_raw": f"{state} (60 days)",
                "lookback": "60 days",
                "declaration_name": f"{STATE_NAMES.get(state, state)} - {title} {upd['incident_start'].month}/{upd['incident_start'].day}/{upd['incident_start'].year}",
                "declaration_number": None,
                "disaster_type_raw": dtype_raw,
                "disaster_types": dtypes,
                "declaration_type": "Emergency (EM)",
                "counties": counties,
                "counties_raw": label,
                "declaration_date": iso(upd["sep_start"]),
                "incident_effective": iso(upd["incident_start"]),
                "incident_termination": iso(upd.get("incident_end")),
                "sep_effective": iso(upd["sep_start"]),
                "sep_termination": iso(upd["sep_end"]),
                "days_until_expiry": None,
                "days_since_expiry": None,
            }
            refresh_item(item, today)
            items.append(item)
            added.append(item)
            next_id += 1
    return items, added, changed


def merge_hub_unique(items: list[dict], hub_data: list[dict], today: date) -> tuple[list[dict], list[dict], list[dict]]:
    kept: list[dict] = []
    dropped: list[dict] = []
    existing = list(items)
    used_ids = {x.get("id") for x in existing}
    next_id = next_numeric_id(existing)
    for d in hub_data:
        if d.get("status") == "yearround":
            continue
        hub_start, _, _ = parse_window_dates(d.get("incidentWindow") or "")
        if hub_start is None:
            hub_start, _, _ = parse_window_dates(d.get("sepWindow") or "")
        match = next(
            (
                x for x in existing
                if same_declaration(
                    d.get("name") or "",
                    d.get("state") or "",
                    x.get("declaration_name") or "",
                    x.get("state") or "",
                    hub_start,
                    parse_iso(x.get("incident_effective")) or parse_iso(x.get("sep_effective")),
                )
            ),
            None,
        )
        if match:
            dropped.append({"hub_id": d.get("id"), "hub_name": d.get("name"), "kept_id": match["id"], "kept_name": match.get("declaration_name")})
            continue
        item = data_to_item(d, today)
        if item["id"] in used_ids:
            item["id"] = f"sep-{next_id:04d}"
            item["retained_from_hub_original_id"] = d.get("id")
            next_id += 1
        items.append(item)
        existing.append(item)
        used_ids.add(item["id"])
        kept.append(item)
    return items, kept, dropped


def assign_sort_and_data(items: list[dict], yearround: list[dict], today: date) -> list[dict]:
    for item in items:
        refresh_item(item, today)
    data_items = [item_to_data(x, 0) for x in items]
    for yr in yearround:
        row = dict(yr)
        row["status"] = "yearround"
        row["sepEnd"] = row.get("sepEnd") or ""
        data_items.append(row)
    rank = {"expiring": 0, "active": 1, "yearround": 2, "ended": 3}
    data_items.sort(key=lambda d: (rank.get(d.get("status"), 9), d.get("sepEnd") or "9999-12-31", d.get("state") or "", d.get("name") or ""))
    for i, d in enumerate(data_items, start=1):
        d["sortRank"] = i
    return data_items


def write_seps_json(items: list[dict], today: date, source: str, generated_note: str) -> dict:
    payload = {
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "today": iso(today),
        "source_file": source,
        "last_imported": iso(today),
        "last_updated": iso(today),
        "source": generated_note,
        "counts": counts(items),
        "items": items,
    }
    JSON_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def embed_into_pages(data_items: list[dict], today: date) -> None:
    total = len(data_items)
    chip = f'{today.strftime("%m.%d.%Y")} &middot; {total} SEPs'
    cache = today.strftime("%Y%m%d")
    html = HTML_PATH.read_text()
    payload = "var DATA=" + json.dumps(data_items, separators=(",", ":")) + ";"
    new_html, n = re.subn(
        r"var DATA=\[.*?\];",
        lambda _m: payload,
        html,
        count=1,
        flags=re.S,
    )
    if n != 1:
        raise SystemExit("Could not find var DATA=[...] in pages/sep-tracker-app.html")
    new_html, n = re.subn(
        r'(<span class="chip soft" id="hero-imported">).*?(</span>)',
        rf"\g<1>{chip}\2",
        new_html,
        count=1,
        flags=re.S,
    )
    if n != 1:
        raise SystemExit("Could not find #hero-imported chip in pages/sep-tracker-app.html")
    HTML_PATH.write_text(new_html)

    for path in SHELL_PAGES:
        if not path.exists():
            continue
        text = path.read_text()
        text = re.sub(
            r"https://agentmedicarehub.com/sep-tracker-app.html\?v=\d+",
            f"/sep-tracker-app.html?v={cache}",
            text,
        )
        text, n = re.subn(
            r"sep-tracker-app.html\?v=\d+",
            f"sep-tracker-app.html?v={cache}",
            text,
        )
        if n < 1:
            print(f"warning: no cache-bust param in {path}", file=sys.stderr)
        path.write_text(text)


def load_source_items(path: Path) -> list[dict]:
    raw = json.loads(path.read_text())
    if isinstance(raw, dict) and "items" in raw:
        return list(raw["items"])
    if isinstance(raw, list):
        return list(raw)
    raise SystemExit(f"Unrecognized JSON in {path}")


def brief(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "state": item.get("state"),
        "status": item.get("status"),
        "name": item.get("declaration_name") or item.get("name"),
        "incident": f"{item.get('incident_effective')} -> {item.get('incident_termination')}",
        "sep": f"{item.get('sep_effective')} -> {item.get('sep_termination')}",
        "counties": item.get("counties"),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Update the hub SEP tracker (local files only; no production deploy).")
    p.add_argument("--as-of", dest="as_of", default=None, help="Status date YYYY-MM-DD (default: today).")
    p.add_argument("--email", type=Path, help="HealthSpring DST-SEP email / notice text file.")
    p.add_argument("--replace-json", type=Path, help="Replace seps.json items from this snapshot (e.g. the 10.21 standalone export).")
    p.add_argument("--keep-hub-unique", action="store_true", help="Keep unique disaster rows from the current public page that are not in the snapshot.")
    p.add_argument("--write", action="store_true", help="Write seps.json and embed into the hub HTML. Default is dry-run.")
    p.add_argument("--report", type=Path, help="Optional JSON report path.")
    args = p.parse_args(argv)

    today = parse_iso(args.as_of) if args.as_of else date.today()
    if today is None:
        raise SystemExit("Invalid --as-of date")

    if args.replace_json:
        items = load_source_items(args.replace_json)
        source_file = args.replace_json.name
    elif JSON_PATH.exists():
        items = load_source_items(JSON_PATH)
        source_file = JSON_PATH.name
    else:
        items = []
        source_file = "(empty)"

    # Work on copies so dry-run cannot surprise the caller
    items = json.loads(json.dumps(items))

    hub_data = []
    if HTML_PATH.exists():
        html = HTML_PATH.read_text()
        m = re.search(r"var DATA=(\[.*?\]);", html, re.S)
        if m:
            hub_data = json.loads(m.group(1))

    kept_unique: list[dict] = []
    dropped_dupes: list[dict] = []
    if args.keep_hub_unique and hub_data:
        items, kept_unique, dropped_dupes = merge_hub_unique(items, hub_data, today)

    added: list[dict] = []
    changed: list[dict] = []
    parsed_updates: list[dict] = []
    if args.email:
        parsed_updates = parse_healthspring_email(args.email.read_text())
        items, added, changed = apply_email_updates(items, parsed_updates, today)

    for item in items:
        refresh_item(item, today)

    yearround = []
    if YEARROUND_PATH.exists():
        yearround = json.loads(YEARROUND_PATH.read_text())
    elif hub_data:
        yearround = [d for d in hub_data if d.get("status") == "yearround"]

    data_items = assign_sort_and_data(items, yearround, today)
    summary = counts([{**x, "status": x["status"]} for x in items])
    # Page counts include year-round rows
    page_counts = {
        "total": len(data_items),
        "active": sum(1 for d in data_items if d["status"] == "active"),
        "expiring": sum(1 for d in data_items if d["status"] == "expiring"),
        "ended": sum(1 for d in data_items if d["status"] == "ended"),
        "yearround": sum(1 for d in data_items if d["status"] == "yearround"),
        "fl_active": sum(1 for d in data_items if d.get("state") == "FL" and d["status"] in ("active", "expiring", "yearround")),
        "added": len(added),
        "changed": len(changed),
        "kept_hub_unique": len(kept_unique),
        "dropped_hub_duplicates": len(dropped_dupes),
    }

    source_note = "HealthSpring DST-SEP notice"
    if args.email:
        source_note += f" {args.email.name}"
    if args.replace_json:
        source_note += f"; base snapshot {args.replace_json.name}"

    print("parsed email updates:", len(parsed_updates))
    for u in parsed_updates:
        print("  ", u.get("state"), u.get("flag"), u.get("title"),
              iso(u.get("incident_start")), "->", iso(u.get("incident_end")),
              "sep", iso(u.get("sep_start")), "->", iso(u.get("sep_end")),
              "counties", "yes" if u.get("counties_raw") else "unchanged")
    print("page counts:", page_counts)
    print("added:")
    for x in added:
        print("  ", brief(x))
    print("changed:")
    for x in changed:
        print("  ", brief(x))

    fl_tx = [d for d in data_items if d.get("state") in ("FL", "TX") and d.get("status") != "yearround"]
    report = {
        "as_of": iso(today),
        "page_counts": page_counts,
        "disaster_counts": summary,
        "added": [brief(x) for x in added],
        "changed": [brief(x) for x in changed],
        "kept_hub_unique": [
            {"id": x.get("id"), "state": x.get("state"), "status": x.get("status"), "name": x.get("declaration_name")}
            for x in kept_unique
        ],
        "dropped_hub_duplicates": dropped_dupes,
        "florida_texas": fl_tx,
        "source": source_note,
    }
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        print("wrote report", args.report)

    if args.write:
        write_seps_json(items, today, source_file if not args.replace_json else args.replace_json.name, source_note)
        embed_into_pages(data_items, today)
        print("wrote", JSON_PATH.relative_to(REPO), "and embedded DATA into", HTML_PATH.relative_to(REPO))
        print("updated cache-bust on", ", ".join(str(p.relative_to(REPO)) for p in SHELL_PAGES if p.exists()))
    else:
        print("dry-run only (pass --write to save files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
