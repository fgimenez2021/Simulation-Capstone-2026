from __future__ import annotations

from pathlib import Path

import pandas as pd
from matplotlib.figure import Figure

from sim.plots import _plot_stage_delta_waterfalls, _setup_theme


def test_time_waterfall_uses_dynamic_limits_for_large_negative_deltas(local_tmp_path, monkeypatch):
    rows = []
    stage_specs = [
        ("ONBOARDING", 1, 48.0, 8.0, 0.0, 0.0),
        ("CLEARING_SETTLEMENT", 2, 72.0, 6.0, 1.0, 0.2),
        ("TRANSFERABILITY", 3, 96.0, 4.0, 0.5, 0.1),
    ]

    for scenario in ["BASELINE", "STRESS"]:
        stress_shift = 24.0 if scenario == "STRESS" else 0.0
        for asset in ["TBILL_MMF", "PRIVATE_CREDIT"]:
            for route in ["TRADFI", "TOKENIZED"]:
                for stage_id, stage_index, tradfi_hours, tokenized_hours, tradfi_cost, tokenized_cost in stage_specs:
                    rows.append(
                        {
                            "scenario_id": scenario,
                            "asset_id": asset,
                            "route_id": route,
                            "stage_id": stage_id,
                            "stage_index": stage_index,
                            "time_hours": tradfi_hours + stress_shift if route == "TRADFI" else tokenized_hours,
                            "explicit_cost": tradfi_cost if route == "TRADFI" else tokenized_cost,
                            "implicit_cost": 0.0,
                        }
                    )

    df = pd.DataFrame(rows)
    _setup_theme()

    original_savefig = Figure.savefig

    def checked_savefig(self: Figure, *args, **kwargs):
        if self._suptitle and "Time Delta" in self._suptitle.get_text():
            mins = [ax.get_ylim()[0] for ax in self.axes if ax.axison]
            maxs = [ax.get_ylim()[1] for ax in self.axes if ax.axison]
            assert mins, "Expected at least one axis on the time waterfall figure"
            assert min(mins) < -7.0
            assert max(maxs) > 0.0
        return original_savefig(self, *args, **kwargs)

    monkeypatch.setattr(Figure, "savefig", checked_savefig)

    paths = _plot_stage_delta_waterfalls(df, Path(local_tmp_path))

    assert Path(paths["fig_kpi_stage_delta_waterfall_time"]).exists()
    assert Path(paths["fig_kpi_stage_delta_waterfall_cost"]).exists()
