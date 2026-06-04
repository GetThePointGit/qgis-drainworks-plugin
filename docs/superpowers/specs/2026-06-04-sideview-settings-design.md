# Side-view settings + panel polish — design (C7)

**Goal:** Per-line colour/width in the langsprofiel settings, white legend background by
default, more legend positions (four corners + below the graph), fully Dutch dialog, and
a shorter panel by moving the step ⚙ next to the action button.

**Status:** decisions agreed (2026-06-04); feeds `writing-plans`.

**Builds on:** C1–C6. Touches `sideview/settings.py`, `ui/sideview_settings_dialog.py`,
`sideview/sideview_widget.py`, `ui/dock.py`.

---

## 1. Per-line colour + width

`SideViewSettings` replaces the single `line_color`/`line_width` with a **`lines`** map
`{key: {"color": str, "width": int}}` for these six lines, with the current looks as
defaults:

| key | line | default colour | default width |
|-----|------|----------------|---------------|
| `bob` | BOB gemeten (measured invert) | `#333333` | 2 |
| `crown` | Bovenkant buis | `#888888` | 1 |
| `ideal` | BOB leiding (recht) | `#cc8400` | 1 |
| `maaiveld` | Maaiveld | `#a0522d` | 1 |
| `put` | Put-lijn | `#398a39` | 2 |
| `water` | Waterpeil | `#2c7fb8` | 1 |

`show_profile` reads each line's colour/width from the settings. The light full-height
put guide uses the `put` colour (at width 1); the dashed `ideal`/`maaiveld`/`water` lines
keep their dashed style but take the configured colour/width. `from_dict` fills any
missing line/key from the defaults (forward/backward compatible).

## 2. White legend background by default

`SideViewSettings.legend_white_bg` defaults to **True**.

## 3. Legend positions

Positions become: **linksboven, rechtsboven, linksonder, rechtsonder** (four corners,
anchored inside the plot) and **onder (horizontaal)** — a horizontal legend along the
bottom (the legend's column count is raised so the entries sit side by side, anchored
bottom-centre). Stored values: `top-left, top-right, bottom-left, bottom-right, below`.
`legend.setColumnCount` is used for the horizontal layout, guarded with `hasattr` (fall
back to bottom-left if the vendored pyqtgraph lacks it). Default stays `top-left`.

## 4. Fully Dutch dialog

- The dialog buttons show Dutch text: **Annuleren** (Cancel) and **Standaardwaarden**
  (Restore Defaults); OK stays "OK". Set via explicit button text (QDialogButtonBox
  shows OS-English otherwise).
- The legend-position combo shows Dutch labels (Linksboven / Rechtsboven / Linksonder /
  Rechtsonder / Onder) mapped to the stored values above.

## 5. Panel polish — gear next to the action button

In both step cards, the ⚙ settings button moves onto the **same row as the wide action
button** (`[ Verrijk basisdata ][⚙]` and `[ Bereken verloren berging ][⚙]`), removing the
separate gear row above the button so the panel is less tall. The action button keeps
stretching; the gear is a small fixed button beside it.

---

## 6. Out of scope

- No change to what the lines represent or the berging logic.
- No persistence-format migration tooling (old stored settings just fall back to
  defaults via `from_dict`).

## 7. Defaults

- White legend background: on. Legend position default: linksboven. Line defaults: per
  the table in §1.
