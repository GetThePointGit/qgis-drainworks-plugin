# 1 — Importeren

De eerste stap leest riooldata in en schrijft een **GeoPackage met basisdata** weg.

## Ondersteunde formaten

- **RIBX** (`.ribx` / `.xml`) — NEN 13508-2 inspectiedata.
- **SUFRIB** (klassiek) — een `.rib`-netwerkbestand met optioneel een meetbestand
  (`.hel` / `.rmb`).
- **GeoPackage** (`.gpkg`) — een eerder door Drainworks gemaakte (of compatibele) GeoPackage;
  deze wordt direct geopend.

## Stappen

1. Klik op **Importeren** in de hoofdknoppenbalk.
2. Kies het **bestand** (RIBX / `.rib` / GeoPackage).
3. Alleen bij SUFRIB: kies eventueel het **meetbestand** (`.hel` / `.rmb`).
4. Kies de **doel-GeoPackage** (wordt aangemaakt/overschreven). Bij het kiezen van een
   invoerbestand wordt automatisch een naam voorgesteld.
5. Klik **Importeren**.

> 📷 **Screenshot:** *het importdialoog "Drainworks — rioolgegevens importeren" met de drie
> velden ingevuld.* `screenshots/01-importdialoog.png`

Het inlezen draait op de achtergrond; bovenin verschijnt een melding met een lopende
voortgangsbalk. Als het klaar is, worden de lagen **Putten**, **Leidingen** en (na verrijken)
**Segmenten** in een laaggroep met de naam van de GeoPackage op de kaart geladen, en zoomt de
kaart naar het netwerk.

> 📷 **Screenshot:** *de voortgangsbalk bovenin tijdens het importeren.*
> `screenshots/01-voortgang.png`

## Resultaat

- **Putten** (puntlaag): code, maaiveld, bodemhoogte, is_sink.
- **Leidingen** (lijnlaag): code, knopen, diameter, BOB-begin/eind, lengte, materiaal.
- **Metingen** (`measurements_raw`): de ruwe hellingshoekmetingen (nog niet omgezet naar
  hoogtes).

De bestandsinformatie in het paneel toont nu het aantal putten, leidingen en metingen.

> 📷 **Screenshot:** *het paneel met de bestandsinformatieregel ("Bestand: … · Putten N ·
> Leidingen N · Metingen N").* `screenshots/01-bestandinfo.png`

> **Let op:** correctie van BOB-metingen, segmentlengtes e.d. zijn géén importinstellingen;
> die horen bij stap 2 (zie het tandwiel bij "Verrijk basisdata").
