"""QgsTask wrappers so the three pipeline steps run off the GUI thread.

Each task's ``run()`` does the heavy work (callable directly in tests) and stores
``result``/``error``; ``finished(ok)`` runs on the main thread and calls the
``on_done(task)`` callback the dock supplied (for layer loading + messages).
"""

from qgis.core import QgsTask

from drainworks_plugin.io.import_controller import import_to_base
from drainworks_plugin.pipeline.berging import compute_berging
from drainworks_plugin.pipeline.enrich import enrich


class _StepTask(QgsTask):
    """Base: run a callable, capture result/error, fire on_done on the main thread."""

    def __init__(self, description, on_done=None):
        super().__init__(description, QgsTask.CanCancel)
        self.on_done = on_done
        self.result = None
        self.error = None

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
    """Step 1: parse + write_base."""

    def __init__(self, input_path, measurement_path, gpkg_path, on_done=None):
        super().__init__("Drainworks: importeren", on_done)
        self._args = (input_path, measurement_path, gpkg_path)

    def _work(self):
        """Parse the input and write the base layers to the GeoPackage."""
        return import_to_base(*self._args)


class EnrichTask(_StepTask):
    """Step 2: validate + integrate + segments."""

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
        """Validate, integrate and build segments for the base data."""
        return enrich(self.gpkg_path, **self._kwargs)


class BergingTask(_StepTask):
    """Step 3: flood-fill + segment berging."""

    def __init__(self, gpkg_path, resolution="accurate", on_done=None):
        super().__init__("Drainworks: verloren berging", on_done)
        self.gpkg_path = gpkg_path
        self.resolution = resolution

    def _work(self):
        """Run the flood-fill and write per-segment lost-storage results."""
        return compute_berging(self.gpkg_path, resolution=self.resolution)
