Sleeper-Relay (NFL Globis · FCM's Hail Mary)
Legt die Rohdaten der beiden Sleeper-Ligen als Dateien im Repo ab, damit die Wochenberichte sie vollständig und exakt lesen können.
Warum
Die Berichte holten die Daten bisher per WebFetch direkt von api.sleeper.app. Dieser Weg fasst lange JSON-Antworten zusammen und verliert dabei Einträge — am 24.09.2026 meldete derselbe Endpunkt in drei Versuchen 90, 71 und 51 Transaktionen, und eine ganze Waiver-Runde fehlte in der Ausgabe. Über dieses Relay kommen die Daten als Datei: kein Zusammenfasser, keine Kürzung, und auch ausserhalb der geplanten Läufe lesbar.
Was wo liegt
Je Liga unter data/<globis|fcm>/:

Datei
Inhalt
league.json
/v1/league/<id> — Einstellungen, u. a. waiver_day_of_week
rosters.json
/v1/league/<id>/rosters — roh, mit settings.waiver_budget_used
users.json
/v1/league/<id>/users
matchups/wNN.json
/v1/league/<id>/matchups/NN
transactions/wNN.json
/v1/league/<id>/transactions/NN
snapshot.json
kompakter Kaderstand je Roster — Grundlage des Diffs
moves.json
Bewegungs-Logbuch aus den Snapshot-Diffs, wächst an
proj/wNN.json
Wochen-Projections, eingefroren (wird nie überschrieben)
proj_live/wNN.json
Projections der laufenden Woche, jeder Lauf frisch
status.json
was der Lauf geholt hat, was fehlschlug


Gemeinsam: data/state.json, data/players_slim.json (ID → [Name, Position, Team]), data/last_fetch.txt.
Das Logbuch moves.json
Sleeper hat am 24.09.2026 drei durchgegangene Waiver-Claims über /transactions/<woche> nicht herausgegeben. Darum vergleicht jeder Lauf den neuen Kaderstand mit dem letzten und schreibt die Differenz fort — wer hat wen geholt, wen abgegeben, wie viel FAAB floss dabei:

{"seit":"2026-09-23T16:40:09Z","gesehen":"2026-09-24T04:40:12Z","season":2026,

 "week":3,"roster_id":1,"adds":["1339"],"drops":["6931"],"faab_delta":150,"typ":"waiver"}

typ ist waiver (FAAB geflossen), free_agent, drop oder trade (zwei Rosters tauschen im selben Fenster gegenseitig Spieler).

Blindstelle: Was zwischen zwei Läufen geholt und wieder abgegeben wird, sieht das Logbuch nicht — dafür liegen die transactions-Dateien daneben. Beide Quellen sind da, die Auswertung entscheidet.
Projections
proj/wNN.json wird für eine Woche genau einmal geschrieben, sobald sie abgeschlossen ist, und danach nie mehr angefasst — Sleeper schreibt Projections nach den Spielen um, und die Over-/Underachiever-Rekorde brauchen einen festen Wert. proj_live/wNN.json ist das Gegenstück für die Vorschau und wird jeden Lauf überschrieben.

Achtung: Der erste Lauf friert auch die bereits gespielten Wochen ein. Diese Werte sind von heute, nicht von damals. Wochen, die in der App schon erfasst sind, werden deshalb nicht neu eingelesen — dort gilt weiter, was gespeichert ist.
Zeitplan
40 4 * * * und 40 16 * * * (UTC), dazu manuell über den Reiter Actions. Die beiden Läufe klammern die Waiver-Ausführung am Mittwochmorgen ein, und der Morgenlauf liegt vor den Dienstags- und Donnerstagsläufen der App.
Einmalige Einstellung
Damit der Lauf committen darf: Settings → Actions → General → Workflow permissions → „Read and write permissions".

Das Repo muss öffentlich bleiben — raw.githubusercontent.com liefert private Dateien nicht ohne Token.

