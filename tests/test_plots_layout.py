from __future__ import annotations

from pathlib import Path

import pandas as pd
from matplotlib.figure import Figure

from sim.plots import _plot_event_composition, _setup_theme


def test_event_composition_layout_keeps_title_legend_and_axes_separated(local_tmp_path, monkeypatch):
    rows = []
    combos = [
        ("BASELINE", "TBILL_MMF", "TRADFI"),
        ("BASELINE", "TBILL_MMF", "TOKENIZED"),
        ("BASELINE", "PRIVATE_CREDIT", "TRADFI"),
        ("BASELINE", "PRIVATE_CREDIT", "TOKENIZED"),
        ("STRESS", "TBILL_MMF", "TRADFI"),
        ("STRESS", "TBILL_MMF", "TOKENIZED"),
        ("STRESS", "PRIVATE_CREDIT", "TRADFI"),
        ("STRESS", "PRIVATE_CREDIT", "TOKENIZED"),
    ]
    gate_cycle = [
        "GATE:redemption_ok",
        "GATE:transfer_restricted_checked",
        "GATE:redemption_hold_by_rules",
        "GATE_DENIED:allowlist_failed",
        "GATE:redemption_rejected_by_rules",
    ]
    risk_cycle = [
        "KYC_MANUAL_REVIEW",
        "REDEMPTION_HOLD",
        "ATTESTATION_DELAY",
        "ACATS_COMPLICATION",
        "SETTLEMENT_FAIL",
        "GOVERNANCE_PAUSE",
    ]

    for idx, (scenario, asset, route) in enumerate(combos):
        rows.append(
            {
                "scenario_id": scenario,
                "asset_id": asset,
                "route_id": route,
                "risk_events": ";".join(risk_cycle[idx % len(risk_cycle) :] + risk_cycle[: idx % len(risk_cycle)]),
                "gate_events": ";".join(gate_cycle[idx % len(gate_cycle) :] + gate_cycle[: idx % len(gate_cycle)]),
            }
        )

    df = pd.DataFrame(rows)
    _setup_theme()

    original_savefig = Figure.savefig

    def checked_savefig(self: Figure, *args, **kwargs):
        self.canvas.draw()
        renderer = self.canvas.get_renderer()

        assert self._suptitle is not None
        assert self.legends, "Expected a shared legend on the event composition figure"

        title_box = self._suptitle.get_window_extent(renderer=renderer)
        legend_box = self.legends[0].get_window_extent(renderer=renderer)
        axes_boxes = [ax.get_tightbbox(renderer=renderer) for ax in self.axes if ax.axison]
        top_of_axes = max(box.y1 for box in axes_boxes)

        assert title_box.y0 >= legend_box.y1 + 2
        assert legend_box.y0 >= top_of_axes + 2

        return original_savefig(self, *args, **kwargs)

    monkeypatch.setattr(Figure, "savefig", checked_savefig)

    path = _plot_event_composition(df, Path(local_tmp_path))

    assert path.name == "fig_kpi_event_composition_by_type.png"
    assert path.exists()
