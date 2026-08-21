#!/usr/bin/env python3
"""Merge the 2026-08-21 HealthSpring DST-SEP email into seps.json and embed it."""
from __future__ import annotations

import json
import re
import shutil
from datetime import date, datetime
from pathlib import Path

TODAY = date(2026, 8, 21)
ROOT = Path(__file__).resolve().parent
JSON_PATH = ROOT / "data" / "seps.json"
HTML_PATH = ROOT / "index.html"
PAGES_APP = ROOT.parent / "pages" / "sep-tracker-app.html"

EXPIRING_DAYS = 30


def iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def parse_mdy(s: str) -> date:
    return datetime.strptime(s.strip(), "%m/%d/%Y").date()


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


def parse_counties(raw: str, statewide: bool) -> tuple[list[str], str]:
    if statewide:
        return ["STATEWIDE"], "All Counties"
    text = raw.strip()
    keep_borough = bool(re.search(r"Boroughs?\s*$", text, flags=re.I))
    text = re.sub(r"\s+(Counties|County|Boroughs|Borough|Parishes|Parish)\.?$", "", text, flags=re.I)
    text = text.replace(" and ", ", ")
    parts = [re.sub(r"\s+", " ", p).strip(" .") for p in text.split(",")]
    parts = [p for p in parts if p]
    # HealthSpring listed "Cole County" under Illinois; IL county is Coles.
    parts = ["Coles" if p == "Cole" else p for p in parts]
    if keep_borough:
        parts = [p if p.lower().endswith("borough") else f"{p} Borough" for p in parts]
        return parts, ", ".join(parts)
    pretty = ", ".join(parts)
    if len(parts) == 1:
        pretty += " County"
    elif len(parts) > 1:
        pretty = ", ".join(parts[:-1]) + ", and " + parts[-1]
    return parts, pretty


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
    term = date.fromisoformat(item["sep_termination"]) if item.get("sep_termination") else None
    status, until, since = live_status(term, today)
    item["status"] = status
    item["days_until_expiry"] = until
    item["days_since_expiry"] = since


def make_item(
    *,
    next_id: int,
    state: str,
    state_name: str,
    title: str,
    flag: str,
    entity_kind: str,
    incident_start: str,
    incident_end: str,
    sep_start: str,
    sep_end: str,
    counties_raw: str,
    statewide: bool = False,
) -> dict:
    inc_s, inc_e = parse_mdy(incident_start), parse_mdy(incident_end)
    sep_s, sep_e = parse_mdy(sep_start), parse_mdy(sep_end)
    dtype_raw, dtypes = disaster_meta(entity_kind if entity_kind == "fire" else title, title)
    counties, counties_label = parse_counties(counties_raw, statewide)
    if entity_kind in ("fema", "fema_fmag"):
        entity = "FEMA"
        decl_type = "Fire Management (FM)" if entity_kind == "fema_fmag" else "Emergency (EM)"
        lookback = "30 days"
        raw_status = "SEP - New" if flag == "New" else "SEP - Extended/Updated"
    else:
        entity = "State/Local Declaration"
        decl_type = "Emergency (EM)"
        lookback = "60 days"
        raw_status = "SEP - New" if flag == "New" else "SEP - Extended/Updated"
    status, until, since = live_status(sep_e, TODAY)
    return {
        "id": f"sep-{next_id:04d}",
        "raw_status": raw_status,
        "status": status,
        "entity": entity,
        "state": state,
        "state_raw": f"{state} ({lookback})",
        "lookback": lookback,
        "declaration_name": f"{state_name} - {title} {inc_s.month}/{inc_s.day}/{inc_s.year}",
        "declaration_number": None,
        "disaster_type_raw": dtype_raw,
        "disaster_types": dtypes,
        "declaration_type": decl_type,
        "counties": counties,
        "counties_raw": counties_label,
        "declaration_date": iso(TODAY),
        "incident_effective": iso(inc_s),
        "incident_termination": iso(inc_e),
        "sep_effective": iso(sep_s),
        "sep_termination": iso(sep_e),
        "days_until_expiry": until,
        "days_since_expiry": since,
    }


# HealthSpring weekly DST-SEP email, received 2026-08-21.
# flag: New | Renewed
UPDATES = [
    ("AK", "Alaska", "Flooding", "New", "state", "07/21/2026", "10/01/2026", "07/21/2026", "11/30/2026", "Matanuska-Susitna Borough", False),
    ("AK", "Alaska", "Catastrophic Flooding", "New", "state", "08/12/2026", "10/09/2026", "08/12/2026", "11/30/2026", "Juneau Borough", False),
    ("CO", "Colorado", "310 Fire", "New", "state", "08/06/2026", "10/04/2026", "08/06/2026", "11/30/2026", "Garfield County", False),
    ("CO", "Colorado", "Post Fire", "New", "state", "08/12/2026", "10/10/2026", "08/12/2026", "11/30/2026", "Las Animas County", False),
    ("CO", "Colorado", "The Sheep Pen Fire", "New", "state", "08/11/2026", "10/10/2026", "08/11/2026", "11/30/2026", "Las Animas County", False),
    ("CO", "Colorado", "The High Fence Fire", "New", "state", "08/12/2026", "10/10/2026", "08/12/2026", "11/30/2026", "Las Animas County", False),
    ("CO", "Colorado", "The Gotera Fire", "New", "state", "08/12/2026", "10/10/2026", "08/12/2026", "11/30/2026", "Las Animas County", False),
    ("GU", "Guam", "Typhoon Bavi", "New", "fema", "07/02/2026", "09/08/2026", "07/02/2026", "10/31/2026", "All Counties", True),
    ("HI", "Hawaii", "Tropical Storm LALA", "New", "state", "08/13/2026", "09/25/2026", "08/13/2026", "10/31/2026", "All Counties", True),
    ("IL", "Illinois", "Tornadoes, Damaging Winds, and Torrential Rain", "New", "state", "03/10/2026", "08/27/2026", "03/10/2026", "09/30/2026", "Kankakee County", False),
    ("IL", "Illinois", "Severe Storms", "New", "state", "04/14/2026", "08/27/2026", "04/14/2026", "09/30/2026", "Stephenson County", False),
    ("IL", "Illinois", "Line of Severe Storms", "New", "state", "04/17/2026", "08/27/2026", "04/17/2026", "09/30/2026", "Winnebago County", False),
    ("IL", "Illinois", "Severe Storms and Tornadoes", "New", "state", "04/17/2026", "08/27/2026", "04/17/2026", "09/30/2026", "McLean County", False),
    ("IL", "Illinois", "Thunderstorms", "New", "state", "06/10/2026", "08/27/2026", "06/10/2026", "09/30/2026", "Cook County", False),
    ("IL", "Illinois", "Tornadoes", "New", "state", "06/11/2026", "08/27/2026", "06/11/2026", "09/30/2026", "LaSalle and Woodford Counties", False),
    ("IL", "Illinois", "Severe Storms and Tornadoes", "New", "state", "06/17/2026", "08/27/2026", "06/17/2026", "09/30/2026", "Cole County", False),
    ("IL", "Illinois", "Impacts of Severe Weather", "New", "state", "06/17/2026", "08/27/2026", "06/17/2026", "09/30/2026", "Effingham County", False),
    ("IL", "Illinois", "Tornado", "New", "state", "06/17/2026", "08/27/2026", "06/17/2026", "09/30/2026", "Warren County", False),
    ("IL", "Illinois", "Severe Storms and Tornadoes", "New", "state", "06/21/2026", "08/27/2026", "06/21/2026", "09/30/2026", "Jefferson County", False),
    ("IN", "Indiana", "Flooding, Severe Weather", "New", "state", "08/11/2026", "10/10/2026", "08/11/2026", "11/30/2026", "All Counties", True),
    ("LA", "Louisiana", "Tropical Storm Arthur", "Renewed", "state", "06/17/2026", "10/04/2026", "06/17/2026", "11/30/2026", "Avoyelles, East Feliciana, Lafourche, Pointe Coupee, St. Charles, St. Landry, St. Tammany, Terrebonne, and Winn", False),
    ("NV", "Nevada", "Fred Mountain Fire", "New", "fema_fmag", "08/09/2026", "08/10/2027", "08/09/2026", "10/31/2027", "Washoe County", False),
    ("NV", "Nevada", "Stallion Fire", "New", "fema_fmag", "08/10/2026", "08/10/2027", "08/10/2026", "10/31/2027", "Washoe County", False),
    ("NV", "Nevada", "Bug Fire", "New", "fema_fmag", "08/08/2026", "08/07/2027", "08/08/2026", "10/31/2027", "Washoe County", False),
    ("NM", "New Mexico", "Frijoles Fire", "New", "state", "08/04/2026", "10/08/2026", "08/04/2026", "11/30/2026", "Rio Arriba and Santa Fe Counties", False),
    ("ND", "North Dakota", "Drought Conditions", "New", "state", "08/04/2026", "12/30/2026", "08/04/2026", "02/28/2027", "All Counties", True),
    ("OH", "Ohio", "Severe Flooding", "New", "state", "08/10/2026", "12/07/2026", "08/10/2026", "01/31/2027", "Perry and Muskingum Counties", False),
    ("OK", "Oklahoma", "Train Trestle Fire", "New", "fema_fmag", "08/13/2026", "08/12/2027", "08/13/2026", "10/31/2027", "Canadian and Oklahoma Counties", False),
    ("OR", "Oregon", "Grasshopper Fire", "New", "state", "07/29/2026", "09/25/2026", "07/29/2026", "10/31/2026", "Wasco County", False),
    ("OR", "Oregon", "Wrights Spring Fire", "New", "state", "08/07/2026", "10/04/2026", "08/07/2026", "11/30/2026", "Klamath County", False),
    ("OR", "Oregon", "Wrights Spring Fire", "New", "fema_fmag", "08/07/2026", "08/08/2027", "08/07/2026", "10/31/2027", "Klamath County", False),
    ("OR", "Oregon", "Hagen Fire", "New", "fema_fmag", "07/21/2026", "08/08/2027", "07/21/2026", "10/31/2027", "Umatilla and Union Counties", False),
    ("OR", "Oregon", "Fielder Mountain Fire", "New", "fema_fmag", "08/13/2026", "08/12/2027", "08/13/2026", "10/31/2027", "Jackson and Josephine Counties", False),
    ("UT", "Utah", "Rocky Canyon Fire", "New", "fema_fmag", "08/07/2026", "08/08/2027", "08/07/2026", "10/31/2027", "Morgan and Summit Counties", False),
    ("WA", "Washington", "Burn Ban, Drought Conditions and Wildfires", "New", "state", "08/01/2026", "10/08/2026", "08/01/2026", "11/30/2026", "All Counties", True),
]


def counts(items: list[dict]) -> dict:
    active = sum(1 for x in items if x["status"] == "active")
    expiring = sum(1 for x in items if x["status"] == "expiring")
    ended = sum(1 for x in items if x["status"] == "ended")
    fl_active = sum(1 for x in items if x.get("state") == "FL" and x["status"] in ("active", "expiring"))
    return {
        "total": len(items),
        "active": active,
        "expiring": expiring,
        "ended": ended,
        "fl_active": fl_active,
    }


def main() -> None:
    data = json.loads(JSON_PATH.read_text())
    items = data["items"]

    # Renew Florida winter weather / drought / wildfire statewide through 12/31/2026.
    fl = next(
        x
        for x in items
        if x.get("state") == "FL"
        and "winter weather" in (x.get("declaration_name") or "").lower()
        and "wildfire" in (x.get("declaration_name") or "").lower()
    )
    fl["raw_status"] = "SEP - Extended/Updated"
    fl["declaration_name"] = (
        "Florida - Emergency Management-Impacts of Winter Weather, Droughts, and Wildfire Risks 1/31/2026 thru 11/3/2026"
    )
    fl["disaster_type_raw"] = "Storms - Snowstorm/Blizzard/Mix; Drought; Fires/Wildfires"
    fl["disaster_types"] = ["Storms", "Drought", "Fires/Wildfires"]
    fl["counties"] = ["STATEWIDE"]
    fl["counties_raw"] = "All Counties"
    fl["incident_effective"] = "2026-01-31"
    fl["incident_termination"] = "2026-11-03"
    fl["sep_effective"] = "2026-01-31"
    fl["sep_termination"] = "2026-12-31"

    existing_keys = {
        (x.get("state"), x.get("incident_effective"), (x.get("declaration_name") or "").lower())
        for x in items
    }

    nums = [int(x["id"].split("-")[1]) for x in items if re.fullmatch(r"sep-\d+", x["id"] or "")]
    next_id = max(nums) + 1

    added = 0
    for row in UPDATES:
        state, state_name, title, flag, entity_kind, i0, i1, s0, s1, counties, statewide = row
        item = make_item(
            next_id=next_id,
            state=state,
            state_name=state_name,
            title=title,
            flag=flag,
            entity_kind=entity_kind,
            incident_start=i0,
            incident_end=i1,
            sep_start=s0,
            sep_end=s1,
            counties_raw=counties,
            statewide=statewide,
        )
        key = (item["state"], item["incident_effective"], item["declaration_name"].lower())
        # Skip exact dupes if re-run
        if any(
            x.get("state") == item["state"]
            and x.get("sep_effective") == item["sep_effective"]
            and x.get("sep_termination") == item["sep_termination"]
            and x.get("counties") == item["counties"]
            and title.lower() in (x.get("declaration_name") or "").lower()
            and x.get("entity") == item["entity"]
            for x in items
        ):
            continue
        items.append(item)
        next_id += 1
        added += 1
        existing_keys.add(key)

    for item in items:
        refresh_item(item, TODAY)

    items.sort(
        key=lambda x: (
            {"expiring": 0, "active": 1, "ended": 2}.get(x["status"], 9),
            x.get("sep_termination") or "9999-12-31",
            x.get("state") or "",
        )
    )

    data["generated_at"] = datetime(2026, 8, 21, 18, 50, 0).isoformat()
    data["today"] = iso(TODAY)
    data["last_imported"] = iso(TODAY)
    data["last_updated"] = iso(TODAY)
    data["source"] = "HealthSpring DST-SEP weekly email 2026-08-21"
    data["source_file"] = "HealthSpring DST-SEP email 2026-08-21"
    data["counts"] = counts(items)
    data["items"] = items

    JSON_PATH.write_text(json.dumps(data, indent=2) + "\n")

    html = HTML_PATH.read_text()
    html = re.sub(
        r'<script type="application/json" id="sep-data">.*?</script>',
        lambda _m: '<script type="application/json" id="sep-data">'
        + json.dumps(data, separators=(",", ":"))
        + "</script>",
        html,
        count=1,
        flags=re.S,
    )
    html = html.replace(
        '<span id="hdr-last-imported">2026-05-29</span> · <span id="hdr-total">3 SEPs</span>',
        f'<span id="hdr-last-imported">{iso(TODAY)}</span> · <span id="hdr-total">{data["counts"]["total"]} SEPs</span>',
    )
    HTML_PATH.write_text(html)
    shutil.copyfile(HTML_PATH, PAGES_APP)

    fl_now = [x for x in items if x.get("state") == "FL"]
    print("added", added)
    print("counts", data["counts"])
    print("Florida:")
    for x in fl_now:
        print(f"  {x['status']:9} {x['sep_effective']} -> {x['sep_termination']}  {x['declaration_name'][:90]}")


if __name__ == "__main__":
    main()
