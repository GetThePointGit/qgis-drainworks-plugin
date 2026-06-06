from drainworks_plugin.pipeline.state import PipelineState


def test_fresh_import_marks_enrich_required():
    s = PipelineState()
    s.mark_imported()
    assert s.enrich_stale is True
    assert s.berging_stale is True


def test_enrich_then_berging_clears_staleness():
    s = PipelineState()
    s.mark_imported()
    s.mark_enriched()
    assert s.enrich_stale is False
    assert s.berging_stale is True
    s.mark_berging_computed()
    assert s.berging_stale is False


def test_editing_base_marks_enrich_and_berging_stale():
    s = PipelineState()
    s.mark_imported(); s.mark_enriched(); s.mark_berging_computed()
    s.mark_base_edited()
    assert s.enrich_stale is True
    assert s.berging_stale is True


def test_changing_sinks_marks_only_berging_stale():
    s = PipelineState()
    s.mark_imported(); s.mark_enriched(); s.mark_berging_computed()
    s.mark_sinks_changed()
    assert s.enrich_stale is False
    assert s.berging_stale is True


def test_enrich_label_and_berging_label():
    s = PipelineState()
    s.mark_imported()
    assert s.enrich_label() == "Verrijk basisdata"
    s.mark_enriched(); s.mark_berging_computed()
    s.mark_base_edited()
    assert s.enrich_label() == "Verrijk opnieuw"
    assert s.berging_label() == "Herbereken"


def test_restore_sets_flags():
    s = PipelineState()
    s.restore(enrich_ran=True, enrich_fresh=True, berging_ran=True, berging_fresh=True)
    assert s.enrich_ran and not s.enrich_stale
    assert s.berging_ran and not s.berging_stale

    s.restore(enrich_ran=True, enrich_fresh=False, berging_ran=True, berging_fresh=False)
    assert s.enrich_stale and s.berging_stale      # ran but no longer fresh

    s.restore(enrich_ran=False, enrich_fresh=False, berging_ran=False, berging_fresh=False)
    assert s.enrich_stale and s.berging_stale      # not run -> needs running
    assert s.enrich_label() == "Verrijk basisdata"  # not run -> plain label
