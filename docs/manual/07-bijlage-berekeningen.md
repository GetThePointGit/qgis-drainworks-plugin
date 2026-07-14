```{=latex}
\appendix
```

# Bijlage — rekenmethoden

Deze bijlage beschrijft de twee kernberekeningen van Drainworks in detail: de
**correctie BOB** (onderdeel van het verrijken, hoofdstuk 3) en de **verloren
berging** (hoofdstuk 4). De beschrijving volgt exact wat de plug-in rekent; de
methodes zijn overgenomen uit het eerdere lizard-progress-gereedschap.

## Correctie BOB (de-trending van hellingmetingen)

### Waarom een correctie?

Het hoogteprofiel van een gemeten leiding komt uit de **hellingmetingen** (RIBX
`BXA`-waarnemingen): per afstand langs de leiding een gemeten helling of hoogte.
Hellingmetingen worden **geïntegreerd** — elke waarde bouwt voort op de vorige —
waardoor kleine meetfouten zich optellen tot *drift*: het profiel eindigt
stelselmatig te diep of te ondiep ten opzichte van de bekende eind-BOB. In een
langsprofiel over meerdere leidingen geeft dat een kenmerkende **zaagtand**: elk
leidingprofiel begint goed en loopt scheef weg.

De bekende BOB's van de leidinguiteinden (uit de basisdata, inclusief eventuele
handmatige correcties in QGIS) zijn betrouwbaarder dan het geïntegreerde verloop.
De correctie legt het gemeten profiel daarom terug op die BOB's, terwijl de
**vorm** van het profiel — de doorhang en lokale verzakkingen, precies wat je wilt
zien — behouden blijft.

### Stap 1 — integratie van de metingen

Per leiding worden de metingen eerst op afstand gesorteerd en opgeschoond
(dubbele afstanden vervallen; punten meer dan 20 % voorbij de schuine
leidinglengte worden als ruisstaart weggelaten; de gemeten afstand wordt
geschaald naar de kaartlengte van de leiding). Daarna wordt per meetpunt een BOB
bepaald, afhankelijk van het meettype (RIBX-karakteristiek B van de
`BXA`-waarneming):

| Type | Betekenis | BOB per punt |
|---|---|---|
| `J` | helling in graden | vorige BOB $+\;\Delta d \cdot \tan(\alpha)$ (geïntegreerd vanaf de begin-BOB) |
| `K` | helling in procenten | vorige BOB $+\;\Delta d \cdot p/100$ (geïntegreerd vanaf de begin-BOB) |
| `A` | afwijking in mm | ideale lijn begin-BOB → eind-BOB $+$ afwijking |
| `AA` | afwijking in m | ideale lijn begin-BOB → eind-BOB $+$ afwijking |
| `B` | absolute hoogte in m NAP | de gemeten waarde zelf |

Is de leiding **omgekeerd geïnspecteerd** (vanaf de eindput), dan wordt vanaf de
eind-BOB geïntegreerd en worden de afstanden daarna gespiegeld, zodat het profiel
altijd van beginput naar eindput loopt.

Drift speelt vooral bij de geïntegreerde types `J` en `K`; de types `A`/`AA`
hangen al aan de ideale lijn en `B` is absoluut.

### Stap 2 — de-trending op de BOB's

Met **Corrigeer BOB** aan (standaard) wordt het geïntegreerde profiel per leiding
rechtgetrokken. Noem $L$ de leidinglengte, $b_1$ en $b_2$ de bekende begin- en
eind-BOB, en $d$ de afstand van een meetpunt langs de leiding. Twee hulplijnen:

- de **ideale lijn** door de bekende BOB's:
  $\;\mathrm{ideaal}(d) = b_1 + (b_2 - b_1)\cdot d/L$
- de **schijnbare lijn** door het *eerste* en *laatste gemeten* punt van het
  profiel (lineair geïnterpoleerd tussen die twee punten).

Elk meetpunt wordt verticaal verschoven met het verschil tussen beide lijnen op
zijn eigen afstand:

$$\mathrm{correctie}(d) = \mathrm{ideaal}(d) - \mathrm{schijnbaar}(d)$$

De verschuiving wordt op de BOB **én** de OBB (binnen-bovenkant buis) toegepast,
zodat de buisdiameter per punt onveranderd blijft. Het effect is een *rotatie*
van het profiel: het eerste en laatste meetpunt komen exact op de ideale lijn te
liggen, en alle afwijkingen ten opzichte van de rechte lijn (doorhang, kommen,
opduikingen) blijven exact behouden.

De correctie doet níéts wanneer er minder dan 3 meetpunten zijn, de
leidinglengte ontbreekt, of alle metingen op dezelfde afstand liggen. Staat de
instelling **uit**, dan blijft de drift in het profiel zichtbaar (de zaagtand in
het zijaanzicht) en rekent ook de verloren berging met de ongecorrigeerde
hoogtes.

## Verloren berging

### Het idee

Verloren berging is het watervolume dat na afloop van een regenbui **niet** naar
de uitstroompunten (*sinks*) kan afstromen: water dat blijft staan in verzakte
leidingdelen (kommen) en achter tegenhellingen. De berekening beantwoordt per
punt van het netwerk de vraag: *tot welk peil blijft hier water staan als al het
water dat weg kán, weg is?*

### Het netwerk als graaf

Het stelsel wordt omgezet in een keten van knopen met elk een bodemhoogte:

- **putten** — bodemhoogte = de *laagste* BOB van alle aangesloten leidingen
  (water kan door een put stromen op het niveau van de laagste aansluiting);
- **leidinguiteinden** — de begin- en eind-BOB van elke leiding;
- **meetpunten** — de profielpunten uit het verrijken (resolutie *Nauwkeurig*)
  óf alleen de segmentgrenzen (resolutie *Snel*).

Binnen een leiding zijn de knopen op volgorde van afstand verbonden; putten
verbinden de leidingen tot één netwerk. Leidingen zonder begin- of eind-BOB doen
niet mee.

### Flood-fill vanaf de sinks

Elke gekozen sink is een **overstortpunt op zijn eigen bodemhoogte**: water boven
dat niveau stroomt weg, water eronder kan niet meer weg. Vanaf de laagste sink
"vult" het algoritme het netwerk:

1. Alle aaneengesloten knopen die *lager* liggen dan het sinkniveau krijgen een
   waterpeil gelijk aan dat niveau (de plas direct rond de sink).
2. Vanaf de rand van zo'n plas klimt het algoritme omhoog zolang de bodem stijgt;
   die klimmende stukken zijn leeggelopen (waterpeil = eigen bodem, diepte 0).
3. Waar de bodem na een klim weer gaat dalen ligt een **lokale kruin**
   (tegenhelling of top van een verzakking). Die kruin werkt als overlaat: aan de
   andere kant blijft water staan tot exact de kruinhoogte. De kruin wordt als
   nieuw "sinkniveau" in de wachtrij gezet en het vullen herhaalt zich daar.

Zo krijgt elke kom in het netwerk het peil van zijn *laagste ontsnappingspunt*
richting een sink. Bij **meerdere sinks** loost elke sink op zijn eigen
bodemhoogte; delen van het netwerk draineren naar de sink die voor hen het
gunstigst ligt.

Het waterpeil per meetpunt wordt begrensd op de buis: nooit lager dan de BOB en
nooit hoger dan de OBB. Een kom die dieper "vol" zou staan dan de buis hoog is,
telt dus maximaal als volledig gevulde buis.

### Vullingsgraad per meetpunt

Uit waterpeil en buisafmeting volgt per meetpunt de **vullingsgraad**: het deel
van de doorsnede dat onder water staat. Met waterdiepte $h$ (waterpeil − BOB) en
diameter $D$:

- **rond profiel** — de oppervlakte van het cirkelsegment gedeeld door de
  cirkeloppervlakte. Voor $h \le D/2$:
  $$A_{\mathrm{segment}} = \tfrac{r^2}{2}\,(\theta - \sin\theta),\qquad
    \theta = 2\arccos\!\Big(\tfrac{r-h}{r}\Big),\qquad r = D/2$$
  (voor $h > D/2$ het complement daarvan);
- **rechthoekig profiel** — lineair: $h/D$, met $D$ de hoogte van de koker.

### Aggregatie naar segmenten

De meetpunten worden per **segment** (de rekeneenheid uit het verrijken)
samengevat. Tussen elk paar opeenvolgende meetpunten wordt lineair
geïnterpoleerd (trapeziumregel); per segment levert dat:

| Veld | Berekening |
|---|---|
| `flooded_pct` | lengte-gewogen gemiddelde vullingsgraad |
| `flooded_pct_max` | hoogste vullingsgraad van de meetpunten |
| `lost_volume` (m³) | $\int A(d)\,\mathrm{d}d$: natte doorsnede $\times$ lengte, trapeziumregel; $A = \mathrm{vullingsgraad} \times \pi (D/2)^2$ |
| `flooded_length` (m) | totale lengte van de tussenstukken waar water staat |
| `water_level` (m NAP) | lengte-gewogen gemiddeld waterpeil (alleen natte stukken) |
| `water_depth_max` (m) | grootste waterdiepte (waterpeil − BOB) van de meetpunten |

Het **totaal verloren berging** in de stapkaart is de som van `lost_volume` over
alle segmenten.

> **Beperking.** Het verloren volume rekent met een *cirkelvormige* doorsnede
> ($\pi (D/2)^2$). Voor rechthoekige profielen is de vullingsgraad wél exact,
> maar wijkt het volume af zodra de breedte verschilt van de hoogte.

### Nauwkeurig versus snel

- **Nauwkeurig** (standaard): de flood-fill draait op alle profielpunten. Kommen
  *binnen* een segment tellen mee, en het waterpeil wordt per meetpunt in de laag
  `profile` bewaard — het zijaanzicht toont de plassen dan op meetpuntniveau.
- **Snel**: de flood-fill draait alleen op de segmentgrenzen (begin-/eind-BOB per
  segment). Sneller op grote netwerken, maar verzakkingen die geheel binnen een
  segment vallen blijven buiten beeld en het zijaanzicht toont één peil per
  segment.

Bij beide resoluties bepalen de segmentlengtes uit het verrijken (instellingen
**Segment** en **BOB-segment**, hoofdstuk 3) het detailniveau van het resultaat.
