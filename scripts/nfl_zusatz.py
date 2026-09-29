#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zusatzdaten für das Sleeper-Relay: NFL-Spielplan und Verletzungsliste.
 
Warum diese Datei:
  * SPIELPLAN — die wöchentlichen Berichte sollen konstant über die Spielzeitpunkte
    reden (TNF, Sonntag früh/spät, SNF, MNF). Dafür braucht jeder Lauf pro NFL-Team
    den Slot und die Kickoff-Zeit. Die Cloud-Umgebung der App erreicht ESPN nicht,
    die GitHub Action schon. Ergebnis: data/nfl/schedule_wNN.json.
  * VERLETZUNGEN — bisher musste jeder Lauf per Websuche raten, ob ein Ausfall eine
    Verletzung war. Sleeper liefert den Status selbst mit. Ergebnis: data/injuries.json
    (nur Spieler mit gesetztem injury_status, also klein).
 
Läuft mit der Standardbibliothek, im selben Stil wie sleeper_relay.py, und bricht den
Workflow nie ab: Was nicht kommt, wird in data/nfl/status.json vermerkt.
"""
import datetime as dt
import json
import os
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo
 
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
ET = ZoneInfo("America/New_York")
CH = ZoneInfo("Europe/Zurich")
SAISON = int(os.environ.get("NFL_SAISON", "2026"))
UA = {"User-Agent": "sleeper-relay/1.0 (+github actions)"}
fehler = []
 
 
def hole(url, versuche=3):
    for i in range(versuche):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=45) as r:
                return r.read()
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            if i == versuche - 1:
                fehler.append("%s -> %s" % (url, e))
                return None
            import time
            time.sleep(2 + 3 * i)
 
 
def hole_json(url):
    b = hole(url)
    if b is None:
        return None
    try:
        return json.loads(b.decode("utf-8"))
    except ValueError as e:
        fehler.append("%s -> kein JSON (%s)" % (url, e))
        return None
 
 
def schreibe(pfad, obj):
    p = os.path.join(DATA, pfad)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    os.replace(tmp, p)
    return p
 
 
def slot_von(kick_et):
    """Slot-Kürzel aus der Kickoff-Zeit in US-Ostzeit."""
    wd, h = kick_et.weekday(), kick_et.hour          # Mo=0 … So=6
    if wd == 3:
        return "TNF"
    if wd == 4:
        return "FRI"
    if wd == 5:
        return "SAT"
    if wd == 6:
        if h < 15:
            return "SUN_EARLY"
        if h < 19:
            return "SUN_LATE"
        return "SNF"
    if wd == 0:
        return "MNF"
    return "TUE"
 
 
LABEL = {"TNF": "Thursday Night", "FRI": "Freitagsspiel", "SAT": "Samstagsspiel",
         "SUN_EARLY": "Sonntag früh", "SUN_LATE": "Sonntag spät",
         "SNF": "Sunday Night", "MNF": "Monday Night", "TUE": "Dienstagsspiel"}
 
 
def spielplan(week):
    url = ("https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
           "?week=%d&seasontype=2&year=%d" % (week, SAISON))
    d = hole_json(url)
    if not d:
        return None
    spiele, teams, proteam = [], {}, {}
    for ev in d.get("events") or []:
        iso = (ev.get("date") or "").replace("Z", "+00:00")
        try:
            utc = dt.datetime.fromisoformat(iso)
        except ValueError:
            continue
        e, c = utc.astimezone(ET), utc.astimezone(CH)
        s = slot_von(e)
        comp = (ev.get("competitions") or [{}])[0]
        krz, krz_ids = [], []
        for t in comp.get("competitors") or []:
            tm = t.get("team") or {}
            ab = (tm.get("abbreviation") or "").upper()
            krz.append((ab, t.get("homeAway")))
            krz_ids.append((ab, str(tm.get("id") or "")))
        heim = next((a for a, ha in krz if ha == "home"), None)
        gast = next((a for a, ha in krz if ha == "away"), None)
        eintrag = {
            "id": str(ev.get("id") or ""),
            "kickoff_utc": utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "kickoff_et": e.strftime("%Y-%m-%d %H:%M"),
            "kickoff_ch": c.strftime("%Y-%m-%d %H:%M"),
            "wochentag_ch": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"][c.weekday()],
            "slot": s, "slot_text": LABEL[s], "heim": heim, "gast": gast,
            "status": ((comp.get("status") or {}).get("type") or {}).get("state"),
        }
        spiele.append(eintrag)
        for ab, espn_id in krz_ids:
            if ab:
                teams[ab] = {"slot": s, "slot_text": LABEL[s], "kickoff_ch": eintrag["kickoff_ch"],
                             "wochentag_ch": eintrag["wochentag_ch"], "gegner": gast if ab == heim else heim,
                             "heim": ab == heim, "espn_id": espn_id}
                if espn_id:
                    proteam[str(espn_id)] = ab
    spiele.sort(key=lambda x: x["kickoff_utc"])
    byes = sorted({t for t in ALLE_TEAMS} - set(teams)) if ALLE_TEAMS else []
    return {"season": SAISON, "week": week, "abgerufen": jetzt(),
            "spiele": spiele, "teams": teams, "bye": byes, "proteam": proteam}
 
 
ALLE_TEAMS = {"ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN", "DET", "GB",
              "HOU", "IND", "JAX", "KC", "LAC", "LAR", "LV", "MIA", "MIN", "NE", "NO", "NYG",
              "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WSH"}
 
 
def jetzt():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
 
 
def aktuelle_woche():
    d = hole_json("https://api.sleeper.app/v1/state/nfl") or {}
    try:
        return max(1, int(d.get("week") or 1))
    except (TypeError, ValueError):
        return 1
 
 
def verletzungen():
    """Nur Spieler mit gesetztem injury_status — aus der grossen Spielerdatei."""
    d = hole_json("https://api.sleeper.app/v1/players/nfl")
    if not d:
        return None
    out = {}
    for pid, p in d.items():
        st = (p.get("injury_status") or "").strip()
        if not st:
            continue
        out[str(pid)] = {
            "name": p.get("full_name") or p.get("last_name") or str(pid),
            "pos": p.get("position"), "team": p.get("team"),
            "status": st, "body_part": p.get("injury_body_part") or None,
            "notiz": (p.get("injury_notes") or None),
            "news_updated": p.get("news_updated"),
        }
    return {"stand": jetzt(), "anzahl": len(out), "spieler": out}
 
 
def main():
    w = aktuelle_woche()
    wochen, geschrieben = [max(1, w - 1), w, min(18, w + 1)], []
    for n in sorted(set(wochen)):
        sp = spielplan(n)
        if sp:
            schreibe("nfl/schedule_w%02d.json" % n, sp)
            geschrieben.append("schedule_w%02d (%d Spiele)" % (n, len(sp["spiele"])))
    v = verletzungen()
    if v:
        schreibe("injuries.json", v)
        geschrieben.append("injuries (%d Spieler)" % v["anzahl"])
    schreibe("nfl/status.json", {"abgerufen": jetzt(), "week": w,
                                 "geschrieben": geschrieben, "fehler": fehler})
    print("nfl_zusatz: Woche %s | %s" % (w, ", ".join(geschrieben) or "nichts"))
    if fehler:
        print("Fehler (Workflow laeuft trotzdem weiter):")
        for f in fehler:
            print("  -", f)
 
 
if __name__ == "__main__":
    main()
 
