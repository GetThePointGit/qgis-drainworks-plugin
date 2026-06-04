
## Verwerking in stappen

Verwerking in stappen, zodat bijvoorbeeld bob's of ontbrekende leidingen kunnen worden aangepast en dan opnieuw de 
(tussen) stappen kunnen worden berekend
De stappen zijn:

1. van ribx/ sufrib naar geopackage met basisdata.
   In de geopackage staan de basis data (geometry, BOB's diameters) en (hellingshoek) metingen.
2. van basisdata naar de 'verrijkte basis data'. 
   In deze stap wordt:
   - compleetheid van de data gecontroleerd (codes, hoogtes, diameters, links aanwezig)
   - hoogtes bepaald op basis van de metingen
   - waar metingen zijn worden leiding segmenten gemaakt. hierbij worden elementen ook samengevoegd (om niet te veel korte stukken te hebben)
     Gegevens van deze segmenten (leiding, van/ tot afstand, hoogte begin/ eind, hoogste punt bob in segment, gemiddelde hellingshoek, diameter, gebaseerd op aantal metingen, ...))
     De berekende verorenbergingsdata worden verwijderd in deze stap (moeten opnieuw worden bepaald)
     Voor leidingen zonder meting wordt de BOB gebruikt. Ook hier worden segmenten gemaakt van een bepaalde afstand voor de visualisatie.
   - worden gegegevens gevalideerd op basis van verwachte data ranges (diameter, hellingshoek, afstanden (metingen vs leidinggegevens - te kort/ te lang))
   Instellingen voor deze stap is: Corrigeer op basis van BOB (default true)
3. naar verlorenbergingsdata
   Uiteindelijk wordt samen met de opgegeven sinks de verlorgen berging bepaald. Dit gebeurd op de segmenten (hopelijk door de aggregatie ook vrij snel?!)
   en als die mist wordt de BOB's van de leiding gebruikt. Aan de segmenten worden waterpeil, vullingspercentage, m3 verloren berging

Nog uitwerken hoe deze flow moet. in principe kan 1 en 2 tegelijk gebeuren. Daarnaast zou het fijn zijn om 2 los te kunenn draaien (aanpassen -> stap 2 -> direct resultaat bekijken)   

## Kiezen van traject

- kan het label (A, B, etc) binnen de cirkel.
- Kan het traject onder de andere lagen worden gelegd met een brede, niet al te opvallende band 
- Kan je zien vanaf weke punt wordt gewerkt (nu is niet te zien vanaf welk punt)
- kan 'live' het traject worden aangepast in de kaart (grafiek zou ook mooi zijn, maar is misschien te zwaar)
- Als 'traject' aanstaat, dat graag aparte knoppen laten zien, zoals 'stroomafwaarts' en wis traject (en misschien undo/ redo?)
- ik wil de tabel met het traject graag weghalen. Alleen moet er een manier zijn om punten te verwijderen. zelf dacht ik iig aan de 'ctrl', maar misschien ook een aparte knop?


## Sideview

Werkt goed zo. Paar optimalisaties:
- haal label 'langsprofiel' boven de grafiek weg 
- kan er een instellingen knop voor de grafiek komen met: 
  - de locatie van de legenda (links boven, rechtsboven) (default linksboven)
  - aanzetten witte achtergrond voor legenda
  - kleur en breedte van de lijnen.
  - aanzetten tonen putcodes (default an)
  - reset naar default instellingen
  - instellingen graag persistant
- kan de put als lijn van onderkant naar bovenkant (maaiveld) van een put worden getoond? (deze liever niet meenemen bij het zoomen, kan dat?)

## Sinks
- Punten graag in een tabel met de mogelijkheid om punten te verwijderen (zoals de huidige traject tabel). Wis knop kan dan weg.
- knop naast pulldown graag met een + icoon ipv filter.

## Opmaak

- Graag een andere icoon (kwast?)
- de legenda in de layers verander niet bij iets kiezen (zoals kleuren), kan dit wel?
- 

Leidingssegmenten toevoegen met:
- % verloren berging
- waterpeil
- ... (nog ideeen?)
