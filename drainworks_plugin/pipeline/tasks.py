"""QgsTask wrappers so the three pipeline steps run off the GUI thread.

Each task's ``run()`` does the heavy work (callable directly in tests) and stores
``result``/``error``; ``finished(ok)`` runs on the main thread and calls the
``on_done(task)`` callback the dock supplied (for layer loading + messages).
"""

from qgis.core import QgsTask
from qgis.PyQt.QtCore import pyqtSignal

from drainworks_plugin.pipeline.berging import berging_compute
from drainworks_plugin.pipeline.enrich import enrich_compute


class _StepTask(QgsTask):
    """Base: run a callable, capture result/error, fire on_done on the main thread.

    Emits :attr:`progress` ``(percent, label)`` as the step proceeds (and feeds the
    same value to ``QgsTask.setProgress``); the signal is emitted from the worker
    thread and delivered to main-thread slots via Qt's queued connection.
    """

    progress = pyqtSignal(float, str)

    def __init__(self, description, on_done=None):
        super().__init__(description, QgsTask.CanCancel)
        self.on_done = on_done
        self.result = None
        self.error = None

    def _report(self, frac, label=""):
        """Progress callback for the pipeline functions: fan out to the bar + task."""
        pct = max(0.0, min(100.0, float(frac) * 100.0))
        self.setProgress(pct)
        self.progress.emit(pct, label or "")

    def _work(self):
        """Do the step's heavy work and return its result (override in subclasses)."""
        raise NotImplementedError

    def run(self):  # noqa: D401 (QGIS-required name) — executes off-thread
        """Run ``_work`` off the GUI thread, capturing result or error.

        Returns
        -------
        bool
            ``True`` on success, ``False`` if ``_work`` raised (stored in ``error``).
        """
        try:
            self.result = self._work()
            return True
        except Exception as exc:  # captured; surfaced in finished()
            self.error = exc
            return False

    def finished(self, ok):  # noqa: D401 — main thread
        """Fire the ``on_done(task)`` callback on the main thread once ``run`` returns."""
        if self.on_done is not None:
            self.on_done(self)


class ImportTask(_StepTask):
    """Step 1: parse the input off-thread (RIBX/SUFRIB -> BuildResult).

    Only the parse runs here; ``result`` is the parsed ``BuildResult``. The GeoPackage
    write must happen on the main thread (writing/finalising a large GeoPackage in a
    worker thread crashes QGIS on Windows), so the controller does that in the
    ``on_done`` callback. ``gpkg_path`` is the destination for that write.
    """

    def __init__(self, input_path, measurement_path, gpkg_path, on_done=None):
        super().__init__("Drainworks: importeren", on_done)
        self._args = (input_path, measurement_path)
        self.gpkg_path = gpkg_path

    def _work(self):
        """Parse RIBX/SUFRIB into a BuildResult (no GeoPackage write here)."""
        from drainworks_plugin.io.import_controller import parse_input
        return parse_input(*self._args, on_progress=self._report)


class EnrichTask(_StepTask):
    """Step 2: validate + integrate + segments.

    Only the **compute** half runs here (off-thread); ``result`` is the write-plan
    from :func:`enrich_compute`. The GeoPackage write happens later on the main
    thread (writing/finalising a large GeoPackage in a worker thread crashes QGIS
    on Windows), so the dock calls :func:`enrich_write` in its ``on_done`` callback.
    """

    def __init__(self, gpkg_path, correct_bob=True, min_segment=None,
                 bob_segment=None, on_done=None):
        super().__init__("Drainworks: verrijken", on_done)
        self.gpkg_path = gpkg_path
        self._kwargs = {"correct_bob": correct_bob}
        if min_segment is not None:
            self._kwargs["min_segment"] = min_segment
        if bob_segment is not None:
            self._kwargs["bob_segment"] = bob_segment

    def _work(self):
        """Validate, integrate and build segments (no GeoPackage write here)."""
        return enrich_compute(self.gpkg_path, on_progress=self._report, **self._kwargs)


class BergingTask(_StepTask):
    """Step 3: flood-fill + segment berging.

    Only the **compute** half runs here (off-thread); ``result`` is the write-plan
    from :func:`berging_compute`. The GeoPackage write happens on the main thread
    via :func:`berging_write` in the dock's ``on_done`` callback (Windows safety).
    """

    def __init__(self, gpkg_path, resolution="accurate", on_done=None):
        super().__init__("Drainworks: verloren berging", on_done)
        self.gpkg_path = gpkg_path
        self.resolution = resolution

    def _work(self):
        """Flood-fill the network and aggregate per-segment (no GeoPackage write here)."""
        return berging_compute(self.gpkg_path, resolution=self.resolution,
                               on_progress=self._report)
