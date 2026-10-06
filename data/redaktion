# Redaktionsregeln für alle drei Ligen

Stand 06.10.2026. Diese Datei liegt im Relay unter `data/redaktion.md` und wird von allen
sechs geplanten Aufgaben vor dem Schreiben gelesen. Sie ist die ausführliche Fassung der
Kurzregeln, die in den Prompts selbst stehen — ändert sich etwas, genügt ein Commit hier
statt sechs Prompt-Übertragungen.

---

## 1. Aufstellungsfehler kommen slotgenau aus dem Motor

Der Rekord-Motor gibt unter **AUFSTELLUNGEN DER WOCHE** je Manager fertige Tauschzeilen aus:

```
  Yannik     133.02 von  170.02   78.24 %  Bank  37.00
      FLEX  #8: Dalton Kincaid (TE) 1.20  statt  Kyle Monangai (RB) 28.50   +27.30
      WR    #4: Jakobi Meyers (WR) 4.80  statt  Alvin Kamara (RB) 20.30   +15.50
      RB    #3: James Cook (RB) 15.30  statt  Wan'Dale Robinson (WR) 9.50    -5.80
```

Gelesen wird das so: Auf Startplatz 8 (ein FLEX-Platz) stand Kincaid, dort hätte Monangai
stehen müssen, Unterschied 27.30 Punkte. Die Zeilen sind **nach Hebel sortiert** — die
oberste ist der teuerste Fehler und gehört in den Beweisstück-Kasten. Die Summe aller
Gewinne ergibt **exakt** die Bankpunkte; stimmt das nicht, wird nicht publiziert.

**Niemals selbst Starter und Bankspieler gegeneinanderstellen.** Genau daran scheiterte die
Globis-Ausgabe zu Woche 4: Dort stand als Fehler „James Cook statt Kyle Monangai". Die
Summe war richtig, die Geschichte falsch — Cook stand auf einem RB-Platz und war völlig in
Ordnung. Der teure Fehler war Yanniks **dritter Tight End auf einem FLEX-Platz**: Kincaid,
1.20 Punkte. Wer bloss den Startplatz wechselt (derselbe Spieler, anderer Slot), hat keinen
Fehler gemacht und taucht in den Tauschzeilen nicht auf.

Eine negative Zeile ganz unten ist kein Widerspruch, sondern der Rest, der sich aus der
Umstellung ergibt. Erzählt wird die oberste Zeile; die Summe ist die Bankpunktzahl.

> Technischer Hintergrund: Der Motor rechnet die bestmögliche Aufstellung seit 06.10.2026
> exakt über alle Slot-Kombinationen (DP über Bitmasken) statt gierig Slot für Slot. Die
> Summen ändern sich dadurch nicht — 1'200 Zufallskader je Liga ergaben null Abweichungen —,
> aber der Motor kennt jetzt die Zuordnung Spieler → Startplatz und kann sie ausgeben.

## 2. Kaderzugehörigkeit zum Zeitpunkt der Entscheidung

Eine bessere Aufstellung zählt nur, wenn sie damals möglich war. Wer am Sonntag per Trade
oder Waiver kam, konnte den Kicker aus dem Donnerstagsspiel nicht mehr ersetzen — der
Startplatz war längst gesperrt.

Vor dem Motorlauf `lock.json` bauen:

```json
{"<roster_id>": {"<player_id>": {"acq": 1790489413859, "kick": 1790512800000}}}
```

- **`acq`** — `status_updated` der letzten abgeschlossenen Transaktion, mit der dieser
  Spieler in **diesen** Kader kam. Quelle: `<liga>/transactions/wNN.json` für alle Wochen 1
  bis N, chronologisch durchgehen; ein späterer Drop löscht den Eintrag wieder. Wer von
  Anfang an im Kader war, bekommt keinen Eintrag.
- **`kick`** — Kickoff seines NFL-Spiels dieser Woche in Millisekunden. Team aus
  `players_slim.json`, Zeit aus `nfl/schedule_wNN.json` → `teams[<Teamkürzel>]`.

Dann `--lock lock.json` an den Motorlauf hängen. Der Motor sperrt damit genau die
Paarungen, die praktisch unmöglich waren: Ein Spieler darf einen Startplatz nur besetzen,
wenn er vor dem Kickoff seines eigenen Spiels **und** vor dem Kickoff dessen, der dort
tatsächlich stand, im Kader war. Fehlt eine Zeitangabe, wird nichts verboten.

Wo eine Sperre greift, ist das eine eigene Geschichte wert: „Perfekt wäre X gewesen — nur
war X zu dem Zeitpunkt noch gar nicht im Kader."

Für die AurelFootballLeague lässt sich das vorerst nicht anwenden: Das ESPN-Relay führt
keine Transaktions-Historie. Dort gilt nur die Faustregel, einen offensichtlich zu spät
gekommenen Zugang nicht als verpasste Aufstellung zu roasten.

## 3. Power Ranking — gewichtete Einschätzung

Keine starre Rangfolge der Kriterien, kein Sortieren nach einer einzigen Zahl. Fünf
Faktoren fliessen zusammen, ungefähr so gewichtet:

| Faktor | Gewicht | Wofür er steht |
|---|---|---|
| All-Play-Bilanz | 30 % | Wie oft hätte das Team gegen die ganze Liga gewonnen — die ehrlichste Rangliste, sie entlarvt Glücksritter und Pechvögel |
| Erzielte Punkte (PF) | 25 % | Die Feuerkraft des Kaders, unabhängig vom Spielplan |
| Bilanz / Record | 20 % | Das Fundament — aber eben nur das Fundament |
| Kadertiefe und Trend | 15 % | Verletzungen, Bye-Wochen, Formkurve der letzten zwei Wochen; der einzige Faktor, der nach vorn schaut |
| Punkte gegen (PA) | 10 % | Wer ständig gegen hohe Werte antreten musste, steht schlechter da, als sein Kader hergibt |

Die **% of Perfect Lineup ist kein Kriterium mehr**, sondern Kommentar. Die Gewichte sind
Richtwerte, keine Formel zum Nachrechnen: Das Ranking bleibt eine begründete Einschätzung,
muss aber aus diesen fünf Grössen folgen. Bei jedem Team steht die Zahl dabei, die den
Ausschlag gab, und die Bewegung gegenüber der Vorwoche mit ↑/↓ und einem halben Satz.

## 4. Rekorde: Halterwechsel zählt wie ein Rekord

Im Abschnitt „🏆 Neue Rekorde" stehen **zwei gleichwertige Dinge**:

1. ein gebrochener Rekord (`bedeutung` = „Rekord gebrochen" in `<liga>_neue_rekorde.json`),
2. ein **Wechsel des Halters** bei einem laufenden Bilanzwert (`bedeutung` = „laufender
   Bilanzwert", `halter` anders als in `vorher`).

„X löst Y als Rekordhalter ab" ist genauso eine Schlagzeile wie eine neue Bestmarke. Beides
mit altem und neuem Halter und Wert. Draussen bleiben nur reine Wertveränderungen bei
gleichem Halter (etwa „Most Wins: Fry — 41, vorher 40"). Saisonrekorde bleiben aussen vor,
solange die Saison läuft.
