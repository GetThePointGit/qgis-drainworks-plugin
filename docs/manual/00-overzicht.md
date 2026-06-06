# Drainworks — overzicht & concepten

Drainworks is een QGIS-plug-in om Nederlandse riool-inspectiegegevens te importeren, te
verrijken, de **verloren berging** te berekenen en een traject door het netwerk te bekijken
in een **langsdoorsnede** (zijaanzicht).

> 📷 **Screenshot:** *QGIS met het Drainworks-paneel onderaan, een geïmporteerd netwerk op
> de kaart en een langsprofiel rechts.* `screenshots/00-overzicht.png`

## Het paneel

Klik op het Drainworks-logo in de werkbalk om het paneel onderaan te openen/sluiten. Het
paneel heeft links de bediening en rechts het langsprofiel.

De **hoofdknoppenbalk** bevat:

- **Importeren** — gegevens inlezen (RIBX / SUFRIB / GeoPackage).
- **Traject** — een traject door het netwerk samenstellen (aan/uit).
- **Opmaak** — de kaartopmaak van leidingen, putten en segmenten aanpassen.
- **Zijaanzicht** — instellingen voor het langsprofiel.

Daaronder staat **bestandsinformatie** (naam van de GeoPackage; aantal putten, leidingen en
metingen) en twee **stapkaarten**.

## De drie verwerkingsstappen

Drainworks werkt in drie stappen. De tussenresultaten worden in de GeoPackage bewaard, zodat
elke stap los opnieuw gedraaid kan worden.

1. **Importeren** — ruwe basisdata (geometrie, BOB's, diameters) en de (hellingshoek-)
   metingen worden ingelezen en weggeschreven.
2. **Basisdata verrijken** — de data wordt gecontroleerd, hoogtes worden berekend uit de
   metingen, en er worden leidingsegmenten gemaakt.
3. **Verloren berging berekenen** — samen met de gekozen *sinks* (uitstroompunten) wordt de
   verloren berging per segment bepaald.

Elke stap draait op de achtergrond (de kaart blijft bruikbaar) en toont een voortgangsbalk
bovenin het scherm.

> 📷 **Screenshot:** *de twee inklapbare stapkaders "1. Basisdata verrijken" en
> "2. Verloren berging" met hun knoppen en actueel-indicatie.* `screenshots/00-stapkaders.png`

## Actueel of verouderd

Bij elke stapkaart staat of het resultaat **actueel** is (✓) of **verouderd** (⚠). Drainworks
slaat in de GeoPackage een vingerafdruk van de basisdata op; wijzig je een BOB of leiding,
dan merkt de plug-in dat het verrijken/berekenen opnieuw moet — óók als je het bestand later
opnieuw opent.

## Begrippenlijst

| Begrip | Betekenis |
|---|---|
| BOB | Binnen-onderkant buis (de bodemhoogte van de leiding) |
| Maaiveld | Hoogte van het maaiveld bij een put |
| Sink | Uitstroompunt waar water het netwerk verlaat |
| Verloren berging | Watervolume dat in lage stukken blijft staan (kan niet wegstromen) |
| Segment | Geaggregeerd stuk leiding waarop de berging wordt bepaald |
| Vullingsgraad | Het deel van de buisdoorsnede dat onder water staat |
