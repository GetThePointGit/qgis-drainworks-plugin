"""Dialog to switch the map styling of the pipe and manhole layers."""

from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from drainworks_plugin.styling import views as v


def _combo(options, current):
    """Build a combo from ``(label, mode)`` options, selecting ``current``."""
    box = QComboBox()
    for label, mode in options:
        box.addItem(label, mode)
    idx = box.findData(current)
    if idx >= 0:
        box.setCurrentIndex(idx)
    return box


class StyleDialog(QDialog):
    """Pick colour / width / label for pipes and manholes."""

    PIPE_COLOR = [("Standaard", v.PIPE_COLOR_DEFAULT),
                  ("Hoogteligging (BOB)", v.PIPE_COLOR_BOB),
                  ("Verhang", v.PIPE_COLOR_SLOPE)]
    PIPE_WIDTH = [("Standaard", v.PIPE_WIDTH_DEFAULT),
                  ("Diameter", v.PIPE_WIDTH_DIAMETER)]
    PIPE_LABEL = [("Niet", v.PIPE_LABEL_NONE), ("Code", v.PIPE_LABEL_CODE),
                  ("BOB (begin / eind)", v.PIPE_LABEL_BOB), ("Diameter", v.PIPE_LABEL_DIAMETER)]
    MANHOLE_COLOR = [("Standaard", v.MANHOLE_COLOR_DEFAULT),
                     ("Bodemhoogte", v.MANHOLE_COLOR_BOTTOM),
                     ("Maaiveld", v.MANHOLE_COLOR_GROUND)]
    MANHOLE_LABEL = [("Niet", v.MANHOLE_LABEL_NONE), ("Code", v.MANHOLE_LABEL_CODE),
                     ("Bodemhoogte", v.MANHOLE_LABEL_BOTTOM), ("Maaiveld", v.MANHOLE_LABEL_GROUND)]
    SEGMENT_COLOR = [("Vullingsgraad", v.SEGMENT_COLOR_FLOODED),
                     ("Waterhoogte", v.SEGMENT_COLOR_WATER),
                     ("Max. waterdiepte", v.SEGMENT_COLOR_DEPTH)]

    def __init__(self, current, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Drainworks — opmaak")
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("<b>Leidingen</b>"))
        pipe_form = QFormLayout()
        self.pipe_color = _combo(self.PIPE_COLOR, current.get("pipe_color"))
        self.pipe_width = _combo(self.PIPE_WIDTH, current.get("pipe_width"))
        self.pipe_label = _combo(self.PIPE_LABEL, current.get("pipe_label"))
        pipe_form.addRow("Kleur:", self.pipe_color)
        pipe_form.addRow("Breedte:", self.pipe_width)
        pipe_form.addRow("Label:", self.pipe_label)
        layout.addLayout(pipe_form)

        layout.addWidget(QLabel("<b>Putten</b>"))
        mh_form = QFormLayout()
        self.mh_color = _combo(self.MANHOLE_COLOR, current.get("manhole_color"))
        self.mh_label = _combo(self.MANHOLE_LABEL, current.get("manhole_label"))
        mh_form.addRow("Kleur:", self.mh_color)
        mh_form.addRow("Label:", self.mh_label)
        layout.addLayout(mh_form)

        layout.addWidget(QLabel("<b>Segmenten</b>"))
        seg_form = QFormLayout()
        self.segment_color = _combo(self.SEGMENT_COLOR, current.get("segment_color"))
        seg_form.addRow("Kleur op:", self.segment_color)
        layout.addLayout(seg_form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        """Return the chosen styling modes as a dict keyed by layer/aspect."""
        return {
            "pipe_color": self.pipe_color.currentData(),
            "pipe_width": self.pipe_width.currentData(),
            "pipe_label": self.pipe_label.currentData(),
            "manhole_color": self.mh_color.currentData(),
            "manhole_label": self.mh_label.currentData(),
            "segment_color": self.segment_color.currentData(),
        }
