# 3 — Verloren berging berekenen

De derde stap berekent de **verloren berging** per segment, op basis van de gekozen
*sinks* (uitstroompunten). Je vindt hem in de tweede stapkaart, **2. Verloren berging**.

> 📷 **Screenshot:** *de stapkaart "2. Verloren berging" met de sink-keuze, de tabel en de
> knop.* `screenshots/03-kaart-berging.png`

## Sinks (uitstroompunten) kiezen

Een sink is een put waar water het netwerk verlaat. Kies ze op één van twee manieren:

- **Uit de keuzelijst** — selecteer een putcode en klik op **+**.
- **Op de kaart** — klik **Kaart** en klik daarna een put op de kaart aan.

De gekozen sinks staan in een **tabel** met per regel de putcode, de **bodemhoogte (m)** en
een ✕ om de sink te verwijderen.

> 📷 **Screenshot:** *de sinks-tabel met een paar gekozen sinks (code · bodem · ✕).*
> `screenshots/03-sinks-tabel.png`

De sinks worden bij het berekenen in de GeoPackage bewaard (veld `is_sink` op de putten) en
bij heropenen weer ingelezen.

## Instellingen (tandwiel)

Klik op het **tandwiel** naast de knop:

- **Resolutie**:
  - *Nauwkeurig* — flood-fill op de gedetailleerde meetpunten; toont in de grafiek een
    waterpeil **per meetpunt**.
  - *Snel* — flood-fill op de segment-uiteinden; waterpeil **per segment**.

## Uitvoeren

Klik op **Bereken verloren berging**. (Eerst verrijken; staat de basisdata op "verouderd",
dan vraagt de plug-in je eerst opnieuw te verrijken.) De stap draait op de achtergrond, met
bovenin een voortgangsbalk met benoemde stappen (*Waterstanden berekenen… → wegschrijven…*).

Per segment worden gevuld: **waterpeil**, **vullingspercentage** (gemiddeld en max),
**verloren volume (m³)**, **overstroomde lengte** en **max. waterdiepte**.

Het berekende waterpeil zie je in het **zijaanzicht** van een traject (zie *04 — Traject &
zijaanzicht*): bij **Nauwkeurig** als vlakke plassen per meetpunt, bij **Snel** als één
peil per segment.

## Resultaat

Onder de knop verschijnt:

- **Actueel-indicatie** — ✓ *actueel* / ⚠ *verouderd — herbereken*.
- **Totaal verloren berging** — het netwerk-totaal in m³.

De segmenten op de kaart kleuren naar vullingsgraad (zie *05 — Opmaak* om op waterhoogte of
max. waterdiepte te kleuren).

> 📷 **Screenshot:** *de kaart met gekleurde segmenten over de leidingen na een berekening,
> en het totaal in de stapkaart.* `screenshots/03-resultaat.png`
