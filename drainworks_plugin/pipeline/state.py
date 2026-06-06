"""Pipeline staleness state machine (pure — no QGIS).

Tracks whether step 2 (enrich) and step 3 (berging) are up to date, so the dock
can label its buttons. ``enrich_ran``/``berging_ran`` record whether each step has
ever produced output; the *_stale flags say whether that output is current.
"""


class PipelineState:
    """Track enrich/berging staleness across edits."""

    def __init__(self):
        self.imported = False
        self.enrich_ran = False
        self.berging_ran = False
        self.enrich_stale = False
        self.berging_stale = False

    def mark_imported(self):
        """Fresh base data: enrich + berging both required."""
        self.imported = True
        self.enrich_ran = False
        self.berging_ran = False
        self.enrich_stale = True
        self.berging_stale = True

    def mark_enriched(self):
        """Step 2 produced profile/segments; berging now needs (re)computing."""
        self.enrich_ran = True
        self.enrich_stale = False
        self.berging_stale = True

    def mark_berging_computed(self):
        """Step 3 filled the segment berging fields."""
        self.berging_ran = True
        self.berging_stale = False

    def mark_base_edited(self):
        """Pipes/manholes were edited: both downstream steps are stale.

        Wired to the pipes/manholes layer ``afterCommitChanges`` signal in the dock.
        """
        self.enrich_stale = True
        self.berging_stale = True

    def mark_sinks_changed(self):
        """Sinks changed: only the berging is affected."""
        self.berging_stale = True

    def restore(self, enrich_ran, enrich_fresh, berging_ran, berging_fresh):
        """Set the flags from persisted state on load.

        A step that has not run, or whose stored output no longer matches the data,
        is stale (needs running).
        """
        self.imported = True
        self.enrich_ran = enrich_ran
        self.berging_ran = berging_ran
        self.enrich_stale = (not enrich_ran) or (not enrich_fresh)
        self.berging_stale = (not berging_ran) or (not berging_fresh)

    def enrich_label(self):
        """Button text for step 2 (stale + previously run -> 'opnieuw')."""
        return "Verrijk opnieuw" if (self.enrich_stale and self.enrich_ran) else "Verrijk basisdata"

    def berging_label(self):
        """Button text for step 3 (stale + previously run -> 'Herbereken')."""
        return "Herbereken" if (self.berging_stale and self.berging_ran) else "Bereken verloren berging"
