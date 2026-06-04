# 5 — Opmaak van de kaart

Met **Opmaak** in de hoofdknoppenbalk (kwasticoon) pas je de kaartweergave van leidingen,
putten en segmenten aan. De keuzes gebruiken *graduated* renderers, zodat de legenda in het
lagenpaneel meeverandert.

> 📷 **Screenshot:** *het dialoog "Drainworks — opmaak" met de secties Leidingen, Putten en
> Segmenten.* `screenshots/05-opmaak-dialoog.png`

## Leidingen

- **Kleur**: Standaard (donkergrijs) · Hoogteligging (BOB) · Verhang.
- **Breedte**: Standaard · Diameter.
- **Label**: Niet · Code · BOB (begin/eind) · Diameter.

## Putten

- **Kleur**: Standaard · Bodemhoogte · Maaiveld.
- **Label**: Niet · Code · Bodemhoogte · Maaiveld.

## Segmenten

De segmenten liggen **boven** de leidingen. Kleur ze op:

- **Vullingsgraad** (`flooded_pct`) — de standaard 0–25 / 25–50 / 50–75 / 75–100 %-klassen.
- **Waterhoogte** (`water_level`).
- **Max. waterdiepte** (`water_depth_max`).

> 📷 **Screenshot:** *de kaart met segmenten gekleurd op max. waterdiepte, met de bijbehorende
> legenda in het lagenpaneel.* `screenshots/05-segmenten-waterdiepte.png`

## Legenda in het lagenpaneel

Omdat alle opmaak via graduated renderers loopt, tonen de lagen in het QGIS-lagenpaneel de
klassen-legenda die bij je keuze hoort.

> 📷 **Screenshot:** *het QGIS-lagenpaneel met de klassen-legenda onder de Segmenten-laag.*
> `screenshots/05-legenda.png`
