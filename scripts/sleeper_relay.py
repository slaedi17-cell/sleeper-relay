#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sleeper-Relay fuer die beiden Sleeper-Ligen (NFL Globis, FCM's Hail Mary).
 
Warum es das gibt
-----------------
Die Wochenberichte holen ihre Daten bisher per WebFetch direkt von api.sleeper.app.
Dieser Weg fasst lange JSON-Antworten zusammen und verliert dabei Eintraege (am
24.09.2026 meldete derselbe Endpunkt in drei Versuchen 90, 71 und 51 Transaktionen),
und ausserhalb der geplanten Laeufe ist er ganz gesperrt. Dieses Skript holt die
Rohdaten mit einem normalen HTTP-Client, legt sie als Dateien im Repo ab und macht
sie damit ueber raw.githubusercontent.com exakt, vollstaendig und jederzeit lesbar.
 
Ablage (je Liga unter data/<liga>/)
-------------------------------------------
  league.json            /v1/league/<id>            (Einstellungen, u. a. waiver_day_of_week)
  rosters.json           /v1/league/<id>/rosters    (roh, mit settings.waiver_budget_used)
  users.json             /v1/league/<id>/users
  matchups/wNN.json      /v1/league/<id>/matchups/NN
  transactions/wNN.json  /v1/league/<id>/transactions/NN
  snapshot.json          kompakter Kaderstand je Roster - Grundlage des Diffs
  moves.json             Bewegungs-Logbuch aus den Snapshot-Diffs (waechst an)
  proj/wNN.json          Wochen-Projections, EINGEFROREN (wird nie ueberschrieben)
  proj_live/wNN.json     Projections der laufenden Woche (jeder Lauf frisch)
  status.json            was dieser Lauf geholt hat und was fehlschlug
Gemeinsam:
  data/state.json         /v1/state/nfl
  data/players_slim.json  id -> [Name, Position, Team], hoechstens woechentlich
  data/players_slim_stand.txt  Datum des letzten Spielerlisten-Abrufs
  data/last_fetch.txt
 
Das Logbuch moves.json
----------------------
Sleeper hat am 24.09.2026 drei durchgegangene Waiver-Claims ueber
/transactions/<woche> nicht herausgegeben. Darum vergleicht jeder Lauf den neuen
Kaderstand mit dem letzten und schreibt die Differenz fort: wer hat wen geholt,
wen abgegeben, wie viel FAAB ist dabei geflossen. Das ist unabhaengig davon, was
der Transaktions-Endpunkt liefert. Blindstelle: was zwischen zwei Laeufen geholt
UND wieder abgegeben wird, sieht das Logbuch nicht - dafuer sind die
transactions-Dateien da. Beide Quellen liegen im Repo, die Auswertung entscheidet.
 
Nur Standardbibliothek, keine Installation noetig.
"""
 
import concurrent.futures as cf
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.request
 
API = "https://api.sleeper.app"
ROOT = "data"
 
LIGEN = {
    "globis": {"name": "NFL Globis", "league_id": "1314575373521915904"},
    "fcm": {"name": "FCM's Hail Mary", "league_id": "1399391327598161920"},
}
 
PLAYERS_MAX_ALTER_TAGE = 6      # /v1/players/nfl ist 5 MB - hoechstens woechentlich holen
PROJ_THREADS = 8                # parallele Projection-Abrufe
TIMEOUT = 30
 
 
# ── HTTP ────────────────────────────────────────────────────────────────
 
def hole(url, versuche=3):
    """Rohdaten holen. Gibt bytes zurueck oder wirft die letzte Ausnahme."""
    letzte = None
    for i in range(versuche):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "sleeper-relay"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.read()
        except Exception as e:                       # noqa: BLE001 - alles protokollieren
            letzte = e
            time.sleep(1.5 * (i + 1))
    raise letzte
 
 
def hole_json(url):
    return json.loads(hole(url).decode("utf-8"))
 
 
# ── Dateien ─────────────────────────────────────────────────────────────
 
def schreibe(pfad, obj, roh=False):
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    with open(pfad, "w", encoding="utf-8") as f:
        if roh:
            f.write(obj)
        else:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            f.write("\n")
 
 
def lies(pfad, standard=None):
    try:
        with open(pfad, encoding="utf-8") as f:
            return json.load(f)
    except Exception:                                # noqa: BLE001
        return standard
 
 
def jetzt():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
 
 
# ── Kaderstand und Bewegungs-Logbuch ────────────────────────────────────
 
def snapshot_bauen(rosters, saison, woche, stand):
    out = {}
    for r in rosters:
        s = r.get("settings") or {}
        out[str(r.get("roster_id"))] = {
            "faab_used": s.get("waiver_budget_used") or 0,
            "total_moves": s.get("total_moves") or 0,
            "wins": s.get("wins") or 0, "losses": s.get("losses") or 0,
            "ties": s.get("ties") or 0,
            "fpts": round((s.get("fpts") or 0) + (s.get("fpts_decimal") or 0) / 100.0, 2),
            "players": sorted(r.get("players") or []),
            "starters": r.get("starters") or [],
            "taxi": sorted(r.get("taxi") or []),
            "reserve": sorted(r.get("reserve") or []),
        }
    return {"fetched_at": stand, "season": saison, "week": woche, "rosters": out}
 
 
def trades_markieren(eintraege):
    """Zwei Rosters, die im selben Zeitfenster gegenseitig Spieler tauschen: Trade."""
    for i, a in enumerate(eintraege):
        for b in eintraege[i + 1:]:
            if a.get("typ") == "trade" or b.get("typ") == "trade":
                continue
            if (set(a["adds"]) & set(b["drops"])) and (set(b["adds"]) & set(a["drops"])):
                a["typ"] = b["typ"] = "trade"
                a["mit"] = b["roster_id"]
                b["mit"] = a["roster_id"]
 
 
def diff_schreiben(alt, neu):
    """Aus zwei Kaderstaenden die Bewegungen dazwischen ableiten."""
    if not alt or not alt.get("rosters"):
        return []
    eintraege = []
    for rid, n in sorted(neu["rosters"].items(), key=lambda kv: int(kv[0])):
        a = (alt["rosters"] or {}).get(rid)
        if not a:
            continue
        adds = sorted(set(n["players"]) - set(a["players"]))
        drops = sorted(set(a["players"]) - set(n["players"]))
        faab = (n["faab_used"] or 0) - (a["faab_used"] or 0)
        if not adds and not drops and not faab:
            continue
        eintraege.append({
            "seit": alt.get("fetched_at"), "gesehen": neu["fetched_at"],
            "season": neu["season"], "week": neu["week"], "roster_id": int(rid),
            "adds": adds, "drops": drops, "faab_delta": faab,
            "typ": "waiver" if faab > 0 else ("free_agent" if adds else "drop"),
        })
    trades_markieren(eintraege)
    return eintraege
 
 
# ── Projections ─────────────────────────────────────────────────────────
 
def projection(pid, saison, woche):
    url = ("%s/projections/nfl/player/%s?season_type=regular&season=%d&grouping=week"
           % (API, pid, saison))
    d = hole_json(url) or {}
    eintrag = d.get(str(woche))
    if not eintrag:                       # null = von Sleeper vor dem Spiel ausgeschlossen
        return 0.0
    return float((eintrag.get("stats") or {}).get("pts_half_ppr") or 0.0)
 
 
def projections_holen(starters, saison, woche, fehler):
    ids = sorted({p for p in starters if p and p != "0"})
    out = {}
    with cf.ThreadPoolExecutor(max_workers=PROJ_THREADS) as ex:
        auftraege = {ex.submit(projection, p, saison, woche): p for p in ids}
        for f in cf.as_completed(auftraege):
            pid = auftraege[f]
            try:
                out[pid] = f.result()
            except Exception as e:                   # noqa: BLE001
                fehler.append("projection %s: %s" % (pid, e))
    return out
 
 
# ── Spielerliste ────────────────────────────────────────────────────────
 
def players_slim(fehler):
    """Spielerliste hoechstens woechentlich holen (/v1/players/nfl ist 5 MB).
 
    Das Alter steht in einer eigenen Datei, NICHT im Dateidatum: ein frischer
    Checkout setzt alle Dateidaten auf jetzt, die Liste wuerde sonst nie erneuert."""
    pfad = os.path.join(ROOT, "players_slim.json")
    stand_pfad = os.path.join(ROOT, "players_slim_stand.txt")
    if os.path.exists(pfad) and os.path.exists(stand_pfad):
        try:
            with open(stand_pfad, encoding="utf-8") as f:
                frueher = dt.datetime.strptime(f.read().strip()[:10], "%Y-%m-%d").date()
            if (dt.date.today() - frueher).days < PLAYERS_MAX_ALTER_TAGE:
                return "uebersprungen (Stand %s)" % frueher
        except Exception:                            # noqa: BLE001 - dann eben neu holen
            pass
    try:
        roh = hole_json("%s/v1/players/nfl" % API)
    except Exception as e:                           # noqa: BLE001
        fehler.append("players/nfl: %s" % e)
        return "fehlgeschlagen"
    slim = {}
    for pid, v in roh.items():
        if not isinstance(v, dict):
            continue
        name = v.get("full_name") or v.get("last_name") or pid
        slim[pid] = [name, v.get("position"), v.get("team")]
    schreibe(pfad, slim)
    schreibe(stand_pfad, dt.date.today().isoformat() + "\n", roh=True)
    return "%d Spieler" % len(slim)
 
 
# ── eine Liga ───────────────────────────────────────────────────────────
 
def liga_holen(key, cfg, saison, woche, stand):
    basis = os.path.join(ROOT, key)
    lid = cfg["league_id"]
    fehler = []
 
    def sichern(name, url):
        """Holen und ablegen; bei Fehler bleibt die alte Datei stehen."""
        try:
            roh = hole(url).decode("utf-8")
            json.loads(roh)                          # nur gueltiges JSON ablegen
            schreibe(os.path.join(basis, name), roh, roh=True)
            return True
        except Exception as e:                       # noqa: BLE001
            fehler.append("%s: %s" % (name, e))
            return False
 
    sichern("league.json", "%s/v1/league/%s" % (API, lid))
    sichern("users.json", "%s/v1/league/%s/users" % (API, lid))
    ok_rosters = sichern("rosters.json", "%s/v1/league/%s/rosters" % (API, lid))
 
    for w in range(1, max(1, woche) + 1):
        sichern(os.path.join("matchups", "w%02d.json" % w),
                "%s/v1/league/%s/matchups/%d" % (API, lid, w))
    for w in range(1, max(1, woche) + 2):            # eine Woche weiter: Waiver-Laeufe
        sichern(os.path.join("transactions", "w%02d.json" % w),
                "%s/v1/league/%s/transactions/%d" % (API, lid, w))
 
    # Kaderstand fortschreiben und die Bewegungen daraus ableiten
    neue_bewegungen = []
    if ok_rosters:
        rosters = lies(os.path.join(basis, "rosters.json"), [])
        alt = lies(os.path.join(basis, "snapshot.json"))
        neu = snapshot_bauen(rosters, saison, woche, stand)
        neue_bewegungen = diff_schreiben(alt, neu)
        if neue_bewegungen:
            log = lies(os.path.join(basis, "moves.json"), [])
            log.extend(neue_bewegungen)
            schreibe(os.path.join(basis, "moves.json"), log)
        schreibe(os.path.join(basis, "snapshot.json"), neu)
 
    # Projections: die abgeschlossene Woche einfrieren, die laufende frisch halten
    def starters_der_woche(w):
        ms = lies(os.path.join(basis, "matchups", "w%02d.json" % w), []) or []
        return [p for t in ms if t.get("matchup_id") is not None
                for p in (t.get("starters") or [])]
 
    eingefroren = []
    for w in range(1, max(1, woche)):                # alle Wochen VOR der laufenden
        ziel = os.path.join(basis, "proj", "w%02d.json" % w)
        if os.path.exists(ziel):
            continue
        st = starters_der_woche(w)
        if not st:
            continue
        schreibe(ziel, projections_holen(st, saison, w, fehler))
        eingefroren.append(w)
 
    st = starters_der_woche(woche)
    if st:
        schreibe(os.path.join(basis, "proj_live", "w%02d.json" % woche),
                 projections_holen(st, saison, woche, fehler))
 
    status = {"liga": cfg["name"], "league_id": lid, "fetched_at": stand,
              "season": saison, "week": woche,
              "neue_bewegungen": len(neue_bewegungen),
              "projections_eingefroren": eingefroren,
              "fehler": fehler}
    schreibe(os.path.join(basis, "status.json"), status)
    return status
 
 
# ── Hauptlauf ───────────────────────────────────────────────────────────
 
def main():
    stand = jetzt()
    fehler = []
    try:
        state = hole_json("%s/v1/state/nfl" % API)
    except Exception as e:                           # noqa: BLE001
        raise SystemExit("state/nfl nicht erreichbar: %s" % e)
    schreibe(os.path.join(ROOT, "state.json"), state)
 
    saison = int(state.get("season") or dt.date.today().year)
    woche = int(state.get("week") or 1)
    if (state.get("season_type") or "regular") == "pre":
        woche = 1
 
    print("Saison %d, Woche %d, Stand %s" % (saison, woche, stand))
    print("Spielerliste: %s" % players_slim(fehler))
 
    gesamt = {"fetched_at": stand, "season": saison, "week": woche,
              "season_type": state.get("season_type"), "ligen": {}}
    for key, cfg in LIGEN.items():
        s = liga_holen(key, cfg, saison, woche, stand)
        gesamt["ligen"][key] = s
        print("%-8s Bewegungen %d, eingefroren %s, Fehler %d"
              % (key, s["neue_bewegungen"], s["projections_eingefroren"], len(s["fehler"])))
        for f in s["fehler"]:
            print("   Fehler: %s" % f)
    gesamt["fehler_gemeinsam"] = fehler
    schreibe(os.path.join(ROOT, "status.json"), gesamt)
    schreibe(os.path.join(ROOT, "last_fetch.txt"), "Abgerufen: %s\n" % stand, roh=True)
    print("fertig")
 
 
if __name__ == "__main__":
    main()
 
