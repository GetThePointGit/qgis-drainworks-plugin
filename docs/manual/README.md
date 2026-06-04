# Drainworks — gebruikershandleiding

Deze map bevat de gebruikershandleiding als losse Markdown-documenten. Ze zijn in
leesvolgorde genummerd en bedoeld om naar één PDF te converteren.

## Inhoud

1. [00 — Overzicht & concepten](00-overzicht.md)
2. [01 — Importeren](01-importeren.md)
3. [02 — Basisdata verrijken](02-verrijken.md)
4. [03 — Verloren berging berekenen](03-verloren-berging.md)
5. [04 — Traject kiezen & zijaanzicht](04-traject-en-zijaanzicht.md)
6. [05 — Opmaak van de kaart](05-opmaak.md)
7. [06 — Installatie & publicatie](06-installatie-en-publicatie.md)

## Screenshots

Op plekken waar een schermafbeelding hoort, staat een blok zoals:

> 📷 **Screenshot:** *korte beschrijving van wat te tonen.*
> `screenshots/NN-naam.png`

Maak die screenshots in QGIS en plaats ze als `docs/manual/screenshots/NN-naam.png`. De
PDF-export pakt ze dan automatisch op (vervang het 📷-blok desgewenst door
`![beschrijving](screenshots/NN-naam.png)` als je ze inline wilt). Aanbevolen: PNG, breedte
~1400 px, lichte QGIS-thema.

## Naar PDF converteren

Met [pandoc](https://pandoc.org/) (+ een LaTeX-engine zoals `tectonic` of `xelatex`),
vanuit deze map:

```bash
pandoc 00-overzicht.md 01-importeren.md 02-verrijken.md 03-verloren-berging.md \
       04-traject-en-zijaanzicht.md 05-opmaak.md 06-installatie-en-publicatie.md \
       --toc --number-sections --resource-path=. \
       -V geometry:margin=2.5cm -V lang=nl \
       -o drainworks-handleiding.pdf
```

Alternatief (HTML → print naar PDF in de browser):

```bash
pandoc *.md --toc --standalone --metadata title="Drainworks handleiding" -o handleiding.html
```

> 📷 **Screenshot:** *(optioneel) titelpagina/omslag.* `screenshots/00-omslag.png`
