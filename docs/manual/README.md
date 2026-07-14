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

## Naar PDF converteren

Met [pandoc](https://pandoc.org/) + `tectonic` (zelfstandige LaTeX-engine, `brew install
tectonic`), vanuit deze map:

```bash
pandoc metadata.yaml \
       00-overzicht.md 01-importeren.md 02-verrijken.md 03-verloren-berging.md \
       04-traject-en-zijaanzicht.md 05-opmaak.md 06-installatie-en-publicatie.md \
       --pdf-engine=tectonic --resource-path=. --include-in-header=preamble.tex \
       -o drainworks-handleiding.pdf
```

`metadata.yaml` levert de **titelpagina** (titel, ondertitel, auteur, versie), de
inhoudsopgave, genummerde secties en de marges — pas titel/auteur/versie daar aan.

`preamble.tex` (via `--include-in-header`) zet het **lettertype** (Fira Sans + Fira Mono)
en vervangt symbolen die de bodyfont mist (✓ ⚠ ✕ ↶ ↷). Dit staat bewust in een apart raw
bestand en niet in `metadata.yaml`: pandoc verwerkt `header-includes` als Markdown en
escapet dan de `[..]`-font-opties. De fonts worden met `Renderer=OpenType` geladen omdat
tectonic's HarfBuzz-renderer op deze OTF's crasht.

Wil je een omslagafbeelding, plaats dan `screenshots/00-omslag.png` en haal de
`\titlegraphic`-regel in `preamble.tex` uit commentaar. Met `xelatex` i.p.v. `tectonic`
kan `Renderer=OpenType` meestal weg (systeemfonts vereisen dan wel dat Fira Sans/Mono
geïnstalleerd is).

Alternatief (HTML → print naar PDF in de browser):

```bash
pandoc metadata.yaml *.md --toc --standalone -o handleiding.html
```
