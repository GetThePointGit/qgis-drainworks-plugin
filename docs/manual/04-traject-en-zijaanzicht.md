# 4 — Traject kiezen & zijaanzicht

Met een traject bekijk je een pad door het netwerk in de **langsdoorsnede** (het zijaanzicht
rechts in het paneel).

> 📷 **Screenshot:** *een gekozen traject (grijze band met A/B/C-punten) op de kaart en het
> bijbehorende langsprofiel rechts.* `screenshots/04-traject-en-profiel.png`

## Traject samenstellen

Klik op **Traject** in de hoofdknoppenbalk om de trajectmodus aan te zetten. Boven het
langsprofiel verschijnt een knoppenbalk (zie onder). Klik nu putten op de kaart aan:

- **Lege start** — de eerste klik plaatst punt A.
- **Een put op het bestaande traject** — voegt daar een gelabeld **tussenpunt** toe.
- **Een al gekozen punt** — selecteert dat punt (de blauwe ring springt erheen).
- **Een put buiten het traject**, afhankelijk van het geselecteerde punt:
  - geselecteerd = **laatste** punt → de put wordt **achteraan** toegevoegd;
  - geselecteerd = **eerste** punt → **vooraan** toegevoegd;
  - geselecteerd = **tussenpunt** → dat punt **verplaatst** naar de nieuwe put.

Is een put **niet bereikbaar** vanaf het buurpunt, dan verschijnt een melding en gebeurt er
niets.

> 📷 **Screenshot:** *de trajectmodus actief, met de blauwe ring op het actieve punt en de
> grijze trajectband.* `screenshots/04-actief-punt.png`

## Knoppenbalk boven het profiel

- **Stroomafw.** — verleng het traject stroomafwaarts vanaf het laatste punt.
- **Verwijdermodus** — klik daarna één put aan om die uit het traject te halen (gaat
  daarna vanzelf weer uit).
- **Wis** — wis het hele traject.
- **↶ Ongedaan / ↷ Opnieuw** — stap terug/vooruit door de wijzigingen.
- **Klaar** — sluit de trajectkeuze af (zet de modus uit).

> 📷 **Screenshot:** *de trajectknoppenbalk boven het langsprofiel.*
> `screenshots/04-trajectbalk.png`

## Punten verwijderen & snel afronden

- **Verwijdermodus** + klik op een punt, of
- **Rechtermuisklik op een trajectpunt** = dat ene punt eruit. (Op macOS wordt Ctrl+klik
  een rechtermuisklik; gebruik daarom de Command-toets — of de Ctrl-toets met links.)
- **Rechtermuisklik náást een trajectpunt** (in de lege ruimte, terwijl er al een traject
  is) = **Klaar**: dit sluit de trajectmodus af, net als de knop.

Het **hele** traject wissen doe je met **Wis**.

## Het langsprofiel

Het zijaanzicht toont, langs de afstand van het traject:

- de **gemeten BOB** (bodemlijn) en de **bovenkant buis**;
- de **rechte BOB-leidinglijn** (bob1→bob2) als referentie;
- de **putten** als verticale lijnen (bodem→maaiveld) met de putcode;
- de **maaiveldlijn** die de putten verbindt;
- het **waterpeil + de berging-vulling** (na een berekening).

Het deel dat je *live aan het bewerken* bent, wordt licht (alleen de BOB-leidinglijn)
getekend; het al gekozen deel toont de metingen en het waterpeil.

### Het waterpeil (verloren berging)

- **Nauwkeurig** berekend (zie stap 3): het water wordt per meetpunt getekend als **vlakke
  plassen**. Waar de bodem boven het waterpeil uitkomt, eindigt de plas met een **oever**
  (de vulling loopt daar naar nul) i.p.v. schuin door te lopen.
- **Snel** berekend: één waterpeil per segment, getekend in het **midden van elk segment**
  en lineair geïnterpoleerd naar het volgende — een gladdere, schuine lijn.
- Dekt een meting maar een deel van de leiding, dan loopt de plas **horizontaal door tot
  het leidingeinde** (geknipt tegen de bodem), zodat het water niet middenin de leiding
  stopt.
- **Aan/uit zetten:** klik op het legenda-item **"Water (verloren berging)"** in de
  grafiek (uit → label "(uit)"; nogmaals klikken zet het weer aan). Je kunt het ook
  standaard uitzetten via de zijaanzicht-instellingen (zie onder).

Beweeg je de muis over het traject op de kaart, dan verschijnt een **cursor** in de grafiek
op die positie (en andersom). Dit werkt ook als de trajectmodus uitstaat, zolang er een
traject is.

> 📷 **Screenshot:** *het langsprofiel met de bob-/bovenkant-/maaiveld-lijnen, putcodes en
> een waterpeil-vulling; de cursor op een positie.* `screenshots/04-langsprofiel.png`

## Zijaanzicht-instellingen

Klik op **Zijaanzicht** in de hoofdknoppenbalk (tandwielicoon) voor:

- **Legenda-positie** (linksboven / rechtsboven / linksonder / rechtsonder / onder) en een
  **witte legenda-achtergrond** (standaard aan);
- **per-lijn kleur en dikte** (BOB gemeten, bovenkant buis, BOB-leiding, maaiveld, put-lijn,
  waterpeil);
- **toon putcodes**;
- **toon water (verloren berging)** — de standaard zichtbaarheid van het watervlak (los van
  de snelle aan/uit-toggle op het legenda-item in de grafiek).

De instellingen zijn persistent (Annuleren / Standaardwaarden).

> 📷 **Screenshot:** *het dialoog "Langsprofiel-instellingen" met de per-lijn-rijen.*
> `screenshots/04-zijaanzicht-instellingen.png`
