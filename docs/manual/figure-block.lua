-- Houd elk figuur samen met zijn caption op één pagina, met witruimte eromheen.
--
-- Onze figuren staan in de Markdown als een alleenstaande afbeelding gevolgd
-- door een cursieve caption:
--
--     ![](screenshots/foo.png){width=5.8cm}
--
--     *Beschrijving.*
--
-- Dit filter (alleen voor de PDF/LaTeX-build) wikkelt zo'n paar in de
-- `samepagefig`-omgeving uit preamble.tex, die het als één ondeelbaar blok
-- zet en er verticale ruimte omheen legt. In andere uitvoerformaten (GitHub,
-- HTML) doet het filter niets bijzonders; de Markdown blijft gewoon leesbaar.

local function is_single(b, tag)
  return (b.t == 'Para' or b.t == 'Plain')
    and #b.content == 1
    and b.content[1].t == tag
end

function Blocks(blocks)
  local out = pandoc.List()
  local i = 1
  while i <= #blocks do
    local b = blocks[i]
    local nxt = blocks[i + 1]
    if is_single(b, 'Image') and nxt and is_single(nxt, 'Emph') then
      out:insert(pandoc.RawBlock('latex', '\\begin{samepagefig}'))
      out:insert(b)
      out:insert(nxt)
      out:insert(pandoc.RawBlock('latex', '\\end{samepagefig}'))
      i = i + 2
    else
      out:insert(b)
      i = i + 1
    end
  end
  return out
end
