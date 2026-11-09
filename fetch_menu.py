"""Fetch today's Rose-Hulman Union Café menu once and save it as JSON.

Pulls the Bamco.menu_items and Bamco.dayparts objects that Bon Appétit
embeds in the page, and writes:
  menus/YYYY-MM-DD.json  (dated archive)
  menus/latest.json      (always today's menu)
One HTTP request per run.
"""
import datetime
import json
import pathlib
import re
import urllib.request
from zoneinfo import ZoneInfo

CAFE_URL = "https://rose-hulman.cafebonappetit.com/cafe/cafe/{date}/"
OUT_DIR = pathlib.Path("menus")


def extract_object(html: str, start: int) -> dict:
    """Parse the JS object literal that begins at or after `start`."""
    brace = html.index("{", start)
    obj, _ = json.JSONDecoder().raw_decode(html, brace)
    return obj


def parse(html: str) -> dict:
    m = re.search(r"Bamco\.menu_items\s*=\s*", html)
    if not m:
        raise RuntimeError("Bamco.menu_items not found; page layout may have changed")
    menu_items = extract_object(html, m.end())

    dayparts = {}
    for dm in re.finditer(r"Bamco\.dayparts\[['\"]?(\w+)['\"]?\]\s*=\s*", html):
        try:
            dayparts[dm.group(1)] = extract_object(html, dm.end())
        except (ValueError, json.JSONDecodeError):
            pass  # skip anything that isn't plain JSON
    return {"menu_items": menu_items, "dayparts": dayparts}


def simplify(data: dict) -> dict:
    """Group items by meal and station, keeping only the useful fields."""
    items = data["menu_items"]
    meals = {}
    for dp in data["dayparts"].values():
        meal = dp.get("label", "Unknown")
        stations = {}
        for st in dp.get("stations", []):
            entries = []
            for item_id in st.get("items", []):
                it = items.get(str(item_id))
                if not it:
                    continue
                entries.append({
                    "id": it.get("id"),
                    "name": it.get("label"),
                    "description": it.get("description"),
                    "diet": [v.get("label") if isinstance(v, dict) else v
                             for v in (it.get("cor_icon") or {}).values()],
                    "nutrition": it.get("nutrition_details"),
                })
            stations[st.get("label", "")] = entries
        meals[meal] = {"time": f"{dp.get('starttime')}-{dp.get('endtime')}",
                       "stations": stations}
    return meals


def main():
    date = datetime.datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    req = urllib.request.Request(
        CAFE_URL.format(date=date),
        headers={"User-Agent": "Mozilla/5.0 (personal once-daily menu fetch)"},
    )
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")

    data = parse(html)
    out = {"date": date, "meals": simplify(data), "raw": data}

    OUT_DIR.mkdir(exist_ok=True)
    text = json.dumps(out, indent=2, ensure_ascii=False)
    (OUT_DIR / f"{date}.json").write_text(text, encoding="utf-8")
    (OUT_DIR / "latest.json").write_text(text, encoding="utf-8")
    print(f"Saved {len(data['menu_items'])} items, {len(data['dayparts'])} meals for {date}")


if __name__ == "__main__":
    main()
