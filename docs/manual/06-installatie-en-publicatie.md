# 6 — Installatie & publicatie

## A. Installeren via een plugin-ZIP

### Installeren in QGIS

1. **Plugins → Manage and Install Plugins… → Install from ZIP**.
2. Kies `drainworks-<versie>.zip` en klik **Install Plugin**.
3. Activeer **Drainworks** in de lijst (als dat niet automatisch gebeurt).
4. Het Drainworks-logo verschijnt in de werkbalk.


### Vereisten op de doelcomputer

- QGIS **3.40 LTR** of nieuwer (zie `qgisMinimumVersion`). Getest op 3.44.
- Python-pakketten die met QGIS meekomen (`osgeo`, `PyQt5`, `pandas`, `lxml`). `pyqtgraph`
  wordt door de plugin meegeleverd; installeer niets in de QGIS-bundel.
