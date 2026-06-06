# 6 — Installatie & publicatie

## A. Installeren via een plugin-ZIP

### De ZIP bouwen

Een QGIS-plugin-ZIP bevat één map op het hoogste niveau (`drainworks_plugin/`) met daarin
`metadata.txt` en `__init__.py`. Twee aandachtspunten:

1. **`rgs_ribx` moet meegeleverd worden.** In ontwikkeling staat
   `drainworks_plugin/external/rgs_ribx` als *symlink* naar `../../rgs-ribx/src/rgs_ribx`.
   In de ZIP moet dat een **echte kopie** zijn (een symlink werkt niet op de computer van de
   gebruiker).
2. **Uitsluiten:** `__pycache__/`, `tests/`, `docs/`, `.git`, `*.pyc`, de voorbeelddata.

Gebruik het meegeleverde script:

```bash
./scripts/build_plugin_zip.sh
# -> dist/drainworks-<versie>.zip
```

Het script kopieert `drainworks_plugin/` naar een tijdelijke map, vervangt de `rgs_ribx`-
symlink door een echte kopie uit `../rgs-ribx/src/rgs_ribx`, gooit `__pycache__` weg en
zipt het geheel. De vendored `pyqtgraph` onder `external/` blijft meegeleverd. De werkmap
zelf blijft ongewijzigd (de dev-symlink blijft staan).

> Wil je in plaats daarvan een echte kopie van `rgs_ribx` **in de repo** committen (bijv. om
> zonder de sibling-checkout te kunnen bouwen), gebruik dan
> `./scripts/vendor_rgs_ribx.sh --copy` en `git add -f drainworks_plugin/external/rgs_ribx`.

> **Tip:** controleer dat `external/rgs_ribx/` in de ZIP echte bestanden bevat (geen
> symlink) en dat `metadata.txt` op het hoogste niveau van de plugin-map staat.

### Installeren in QGIS

1. **Plugins → Manage and Install Plugins… → Install from ZIP**.
2. Kies `dist/drainworks-<versie>.zip` en klik **Install Plugin**.
3. Activeer **Drainworks** in de lijst (als dat niet automatisch gebeurt).
4. Het Drainworks-logo verschijnt in de werkbalk.

> 📷 **Screenshot:** *het "Install from ZIP"-tabblad met de gekozen ZIP.*
> `screenshots/06-install-zip.png`

### Vereisten op de doelcomputer

- QGIS **3.22** of nieuwer (zie `qgisMinimumVersion`).
- Python-pakketten die met QGIS meekomen (`osgeo`, `PyQt5`, `pandas`, `lxml`). `pyqtgraph`
  wordt door de plugin meegeleverd; installeer niets in de QGIS-bundel.

## B. Publiceren in de QGIS-plugin-repository

De officiële repository is **https://plugins.qgis.org**.

### Eenmalig

1. Maak een **OSGEO-account** aan (https://www.osgeo.org/community/getting-started-osgeo/)
   — daarmee log je in op plugins.qgis.org.
2. Controleer `drainworks_plugin/metadata.txt`: `name`, `version`, `qgisMinimumVersion`,
   `description`, `about`, `author`, `email`, `repository`, `tracker`, `tags`, `icon`,
   `experimental`. Verhoog `version` bij elke nieuwe upload (bijv. `1.0.0` → `1.0.1`).

### Uploaden

1. Log in op **https://plugins.qgis.org** en kies **Share a plugin / Upload**.
2. Upload de ZIP uit stap A. De site valideert `metadata.txt` en de mapstructuur.
3. Bij de **eerste** upload moet een beheerder de plug-in goedkeuren; daarna kun je zelf
   nieuwe versies uploaden.
4. Staat `experimental=True`, dan is de plug-in alleen zichtbaar voor gebruikers die in QGIS
   "Show also experimental plugins" hebben aangezet. Voor een publieke release zet je
   `experimental=False` (zoals nu).

> 📷 **Screenshot:** *het uploadformulier op plugins.qgis.org.* `screenshots/06-upload.png`

### Nieuwe versies

- Verhoog `version` in `metadata.txt`, vul `changelog=` aan, bouw een nieuwe ZIP en upload
  die. Gebruikers krijgen de update via **Plugins → Upgradeable**.

### Aandachtspunten voor goedkeuring

- De plug-in mag bij het laden geen netwerkverkeer of zware imports doen.
- Geen `print()`-debugoutput; meldingen via de QGIS-message bar (zoals Drainworks doet).
- Een geldige `LICENSE` en een duidelijke `about`/`description`.
- De meegeleverde `external/pyqtgraph` en `external/rgs_ribx` zijn third-party/eigen code en
  zijn toegestaan zolang de licenties verenigbaar zijn.

## C. Alternatief: een eigen plugin-repository

Voor intern gebruik kun je de ZIP ook serveren via een eigen `plugins.xml` + de ZIP-bestanden
op een webserver, en die URL in QGIS toevoegen onder **Plugins → Settings → Plugin
Repositories**. Dit vraagt geen goedkeuring maar wel zelf hosten.
