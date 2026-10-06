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
    if wd == 1:
        return "TUE"
    return "WED"            # der Saisonauftakt 2026 lag auf einem Mittwoch
 
 
LABEL = {"TNF": "Thursday Night", "FRI": "Freitagsspiel", "SAT": "Samstagsspiel",
         "SUN_EARLY": "Sonntag früh", "SUN_LATE": "Sonntag spät",
         "SNF": "Sunday Night", "MNF": "Monday Night", "TUE": "Dienstagsspiel",
         "WED": "Mittwochsspiel"}
 
 
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
    return {"fassung": FASSUNG, "season": SAISON, "week": week, "abgerufen": jetzt(),
            "spiele": spiele, "teams": teams, "bye": byes, "proteam": proteam}
 
 
# Wird erhoeht, wenn sich der Aufbau der Spielplan-Dateien aendert. Abgeschlossene
# Wochen mit kleinerer Fassung werden dann einmalig neu geholt (Fassung 2: Block
# `proteam` mit den ESPN-Team-IDs, Mittwochsspiele als eigener Slot).
FASSUNG = 2
 
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
 
 
def _fassung(pfad):
    """Fassungsnummer einer abgelegten Spielplan-Datei (0, wenn sie fehlt oder alt ist)."""
    try:
        with open(pfad, encoding="utf-8") as f:
            return int((json.load(f) or {}).get("fassung") or 0)
    except (OSError, ValueError, TypeError):
        return 0
 
 
def kader_schnappschuss(week):
    """Den Kaderstand dieser Woche einmalig wegsichern.
 
    Warum: `rosters.json` wird bei jedem Lauf überschrieben, enthält aber die einzige
    Angabe darüber, wer gerade auf IR oder im Taxi-Squad steht. Für die bestmögliche
    Aufstellung einer vergangenen Woche braucht man genau diesen Stand — ohne ihn lässt
    sich eine alte Woche nicht mehr korrekt nachrechnen. Geschrieben wird nur, was noch
    nicht existiert, damit ein späterer Lauf den Stand nicht nachträglich verfälscht.
    """
    out = []
    for liga in ("globis", "fcm"):
        quelle = os.path.join(DATA, liga, "rosters.json")
        ziel = os.path.join(DATA, liga, "rosters_w%02d.json" % week)
        if not os.path.exists(quelle) or os.path.exists(ziel):
            continue
        try:
            with open(quelle, "rb") as f:
                roh = f.read()
            os.makedirs(os.path.dirname(ziel), exist_ok=True)
            with open(ziel + ".tmp", "wb") as f:
                f.write(roh)
            os.replace(ziel + ".tmp", ziel)
            out.append("%s/rosters_w%02d" % (liga, week))
        except OSError as e:
            fehler.append("Kader-Schnappschuss %s: %s" % (liga, e))
    return out
 
 
def main():
    w = aktuelle_woche()
    # Alle bisherigen Wochen plus die kommende. Abgeschlossene Wochen werden nur
    # einmal geschrieben (ihre Kickoff-Zeiten aendern sich nicht mehr) — das haelt
    # den Commit klein und spart ESPN-Abrufe. Die laufende und die kommende Woche
    # werden bei jedem Lauf frisch geholt.
    geschrieben = []
    for n in range(1, min(18, w + 1) + 1):
        pfad = os.path.join(DATA, "nfl/schedule_w%02d.json" % n)
        if n < w - 1 and os.path.exists(pfad) and _fassung(pfad) >= FASSUNG:
            continue
        sp = spielplan(n)
        if sp:
            schreibe("nfl/schedule_w%02d.json" % n, sp)
            geschrieben.append("schedule_w%02d (%d Spiele)" % (n, len(sp["spiele"])))
    geschrieben += kader_schnappschuss(w)
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
