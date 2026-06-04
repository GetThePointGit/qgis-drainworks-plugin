# 2 — Basisdata verrijken

De tweede stap maakt van de basisdata **verrijkte basisdata**: validatie, hoogtes en
segmenten. Je vindt hem in de eerste stapkaart, **1. Basisdata verrijken**.

> 📷 **Screenshot:** *de stapkaart "1. Basisdata verrijken" met de knop, het tandwiel, de
> actueel-indicatie en de samenvatting.* `screenshots/02-kaart-verrijken.png`

## Instellingen (tandwiel)

Klik op het **tandwiel** naast de knop voor de instellingen van deze stap:

- **Corrigeer BOB** — corrigeert de gemeten hoogtes op de bekende BOB's van begin/eind van
  de leiding (verwijdert drift in de hellingmetingen). Standaard aan.
- **Segment** — minimale lengte van een gemeten segment (standaard 1 m).
- **BOB-segment** — lengte van de segmenten voor leidingen zónder meting (standaard 5 m).

De instellingen worden bewaard (ook per GeoPackage) en zijn later weer op te vragen via het
tandwiel.

> 📷 **Screenshot:** *het dialoog "Instellingen — basisdata verrijken".*
> `screenshots/02-instellingen.png`

## Uitvoeren

Klik op **Verrijk basisdata**. De stap draait op de achtergrond (voortgangsbalk bovenin) en
doet:

1. **Validatie** — controleert volledigheid (code, BOB, diameter, knooppunten aanwezig) en
   waardes binnen bereik (diameter 50–3000 mm, meetlengte ±20 % van de geometrielengte,
   hellingshoek). Resultaten komen op de velden `valid`/`issues` van de leidingen/putten.
2. **Hoogtes** — zet de hellingmetingen om naar een hoogteprofiel (laag `profile`).
3. **Segmenten** — voegt gemeten punten samen tot segmenten (laag `segments`); voor
   leidingen zonder meting worden BOB-segmenten gemaakt.

Eerder berekende verloren berging wordt hierbij gewist (moet opnieuw).

## Resultaat

Onder de knop verschijnt:

- **Actueel-indicatie** — ✓ *actueel* of ⚠ *verouderd — verrijk opnieuw*.
- **Samenvatting** — bijv. *1697 segmenten · 3 fouten · 5 waarschuwingen*.
  - **Fouten** = ontbrekende/onbekende data (code, BOB, diameter, knooppunt).
  - **Waarschuwingen** = waardes buiten bereik (diameter, meetlengte, hellingshoek).

> 📷 **Screenshot:** *de stapkaart na verrijken met "✓ actueel" en de samenvatting.*
> `screenshots/02-resultaat.png`

## Opnieuw verrijken

Pas je in QGIS een BOB of leiding aan (en sla de bewerking op), dan springt de knop op
**Verrijk opnieuw** (⚠ verouderd). Klik nogmaals om de segmenten/profielen te herbouwen.
