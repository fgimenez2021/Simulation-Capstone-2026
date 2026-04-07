from __future__ import annotations

from pathlib import Path

import pandas as pd
from matplotlib.figure import Figure

from sim.plots import (
    _plot_event_composition,
    _plot_stage_bottleneck_mix,
    _plot_stage_time_distribution_top4,
    _setup_theme,
)


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


def test_stage_bottleneck_layout_keeps_annotations_clear_of_title_and_legend(local_tmp_path, monkeypatch):
    rows = []
    combos = [
        ("BASELINE", "TBILL_MMF", "TRADFI", "KYC_REVIEW", 37.2),
        ("BASELINE", "TBILL_MMF", "TOKENIZED", "KYC_REVIEW", 56.8),
        ("BASELINE", "PRIVATE_CREDIT", "TRADFI", "EXIT_INITIATION", 84.5),
        ("BASELINE", "PRIVATE_CREDIT", "TOKENIZED", "EXIT_INITIATION", 89.3),
        ("STRESS", "TBILL_MMF", "TRADFI", "KYC_REVIEW", 41.1),
        ("STRESS", "TBILL_MMF", "TOKENIZED", "KYC_REVIEW", 54.2),
        ("STRESS", "PRIVATE_CREDIT", "TRADFI", "EXIT_INITIATION", 72.1),
        ("STRESS", "PRIVATE_CREDIT", "TOKENIZED", "EXIT_INITIATION", 78.8),
    ]
    for scenario, asset, route, stage_id, share in combos:
        rows.append(
            {
                "scenario_id": scenario,
                "asset_id": asset,
                "route_id": route,
                "stage_id": stage_id,
                "stage_time_share_pct": share,
            }
        )

    df = pd.DataFrame(rows)
    _setup_theme()

    original_savefig = Figure.savefig

    def checked_savefig(self: Figure, *args, **kwargs):
        self.canvas.draw()
        renderer = self.canvas.get_renderer()

        ax = self.axes[0]
        title_box = ax.title.get_window_extent(renderer=renderer)
        legend = ax.get_legend()
        assert legend is not None
        legend_box = legend.get_window_extent(renderer=renderer)

        label_boxes = [
            txt.get_window_extent(renderer=renderer)
            for txt in ax.texts
            if txt.get_text().strip()
        ]
        assert label_boxes, "Expected stage labels above the bottleneck bars"

        for box in label_boxes:
            assert not box.overlaps(title_box)
            assert not box.overlaps(legend_box)

        return original_savefig(self, *args, **kwargs)

    monkeypatch.setattr(Figure, "savefig", checked_savefig)

    path = _plot_stage_bottleneck_mix(df, Path(local_tmp_path))

    assert path.name == "fig_kpi_stage_bottleneck_mix.png"
    assert path.exists()


def test_stage_distribution_layout_keeps_title_legend_and_axes_separated(local_tmp_path, monkeypatch):
    rows = []
    stages = ["EXIT_INITIATION", "KYC_REVIEW", "REDEMPTION_PROCESSING", "TRANSFERABILITY"]
    routes = ["TRADFI", "TOKENIZED"]
    scenarios = ["BASELINE", "STRESS"]

    for stage_idx, stage in enumerate(stages):
        for route_idx, route in enumerate(routes):
            for scenario_idx, scenario in enumerate(scenarios):
                base_level = 40.0 + stage_idx * 35.0 + route_idx * 10.0 + scenario_idx * 80.0
                for run_id in range(24):
                    rows.append(
                        {
                            "stage_id": stage,
                            "time_hours": base_level + run_id * 2.0,
                            "route_id": route,
                            "scenario_id": scenario,
                            "asset_id": "TBILL_MMF" if run_id % 2 == 0 else "PRIVATE_CREDIT",
                        }
                    )

    df = pd.DataFrame(rows)
    _setup_theme()

    original_savefig = Figure.savefig

    def checked_savefig(self: Figure, *args, **kwargs):
        self.canvas.draw()
        renderer = self.canvas.get_renderer()

        assert self._suptitle is not None
        assert self.legends, "Expected a shared legend on the stage distribution figure"

        title_box = self._suptitle.get_window_extent(renderer=renderer)
        legend_box = self.legends[0].get_window_extent(renderer=renderer)
        axes_boxes = [ax.get_tightbbox(renderer=renderer) for ax in self.axes if ax.axison]
        top_of_axes = max(box.y1 for box in axes_boxes)

        assert title_box.y0 >= legend_box.y1 + 2
        assert legend_box.y0 >= top_of_axes + 2

        return original_savefig(self, *args, **kwargs)

    monkeypatch.setattr(Figure, "savefig", checked_savefig)

    path = _plot_stage_time_distribution_top4(df, Path(local_tmp_path))

    assert path.name == "fig_kpi_stage_time_distribution_top4.png"
    assert path.exists()
