"""Lifecycle Race -- animated HTML/CSS/JS component."""
from __future__ import annotations

import json
from typing import Any

import streamlit.components.v1 as components

from utils.theme import CATEGORY_COLORS, ROUTE_COLORS, STAGE_META, STAGE_ORDER

CALENDAR_DELAY_HOURS = {
    "TBILL_MMF": 0.0,
    "PRIVATE_CREDIT": (45 + 30) * 24.0,
}


def _build_lane_data(
    route_id: str,
    stage_mix: dict[str, dict],
    calendar_delay: float = 0.0,
    route_config_stages: dict[str, Any] | None = None,
) -> dict:
    stages = []
    for sid in STAGE_ORDER:
        meta = STAGE_META.get(sid, {"label": sid, "category": "exception"})
        mix = stage_mix.get(sid)
        enabled = mix is not None and float(mix.get("stage_time_hours_mean", 0)) > 0
        if route_config_stages and sid in route_config_stages:
            enabled = route_config_stages[sid].get("enabled", enabled)
        raw_time = float(mix["stage_time_hours_mean"]) if mix else 0.0
        display_time = max(raw_time - calendar_delay, 0.0) if sid == "EXIT_INITIATION" else raw_time
        stages.append({
            "id": sid,
            "label": meta["label"],
            "category": meta["category"],
            "color": CATEGORY_COLORS.get(meta["category"], "#9ca3af"),
            "enabled": enabled,
            "time_hours": display_time,
            "raw_time_hours": raw_time,
        })
    total = sum(s["time_hours"] for s in stages if s["enabled"])
    return {
        "route_id": route_id,
        "color": ROUTE_COLORS.get(route_id, "#666"),
        "stages": stages,
        "total_time_hours": total,
    }


def build_race_html(
    tradfi_mix: dict[str, dict],
    tokenized_mix: dict[str, dict],
    calendar_delay: float = 0.0,
    tradfi_config: dict | None = None,
    tokenized_config: dict | None = None,
) -> str:
    tradfi = _build_lane_data("TRADFI", tradfi_mix, calendar_delay, tradfi_config)
    tokenized = _build_lane_data("TOKENIZED", tokenized_mix, calendar_delay, tokenized_config)
    data_json = json.dumps({"tradfi": tradfi, "tokenized": tokenized})
    cal_days = calendar_delay / 24.0

    cal_note = ""
    if calendar_delay > 0:
        cal_note = (
            f'<div class="cal-note">Calendar wait of <b>{cal_days:.0f} days</b> '
            f'(redemption window + notice period) applies equally to both routes and is excluded from the bars above.</div>'
        )

    cat_legend = "".join(
        f'<span class="leg-item"><span class="leg-dot" style="background:{c};"></span>{cat.title()}</span>'
        for cat, c in CATEGORY_COLORS.items()
        if cat != "exception"
    )

    return f"""
<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
      background:transparent;color:#e2e8f0;}}
.race-wrap{{max-width:1100px;margin:0 auto;padding:16px;}}
.race-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;}}
.race-title{{font-size:18px;font-weight:700;color:#f1f5f9;}}
.controls{{display:flex;gap:8px;align-items:center;}}
.btn{{padding:7px 16px;border-radius:8px;border:1px solid #475569;background:#1e293b;cursor:pointer;
      font-size:13px;font-weight:600;color:#e2e8f0;transition:all .15s;}}
.btn:hover{{background:#334155;}}
.speed-btn{{padding:5px 10px;border-radius:6px;border:1px solid #475569;background:#1e293b;cursor:pointer;
            font-size:12px;font-weight:600;color:#94a3b8;transition:all .15s;min-width:34px;}}
.speed-btn.sel{{background:#3b82f6;color:#fff;border-color:#3b82f6;}}
.lane{{margin-bottom:22px;}}
.lane-head{{display:flex;align-items:center;gap:10px;margin-bottom:8px;}}
.lane-dot{{width:12px;height:12px;border-radius:50%;}}
.lane-name{{font-size:14px;font-weight:700;color:#f1f5f9;}}
.lane-time{{font-size:13px;color:#94a3b8;margin-left:auto;font-variant-numeric:tabular-nums;}}
.track{{position:relative;height:56px;background:#1e293b;border-radius:10px;overflow:hidden;
        border:1px solid #334155;}}
.seg{{position:absolute;top:0;height:100%;display:flex;align-items:center;justify-content:center;
      transition:width .35s ease;overflow:hidden;border-right:1px solid rgba(0,0,0,.2);}}
.seg-inner{{font-size:9px;font-weight:700;color:#fff;white-space:nowrap;
            text-shadow:0 1px 3px rgba(0,0,0,.5);opacity:0;transition:opacity .3s;padding:0 4px;}}
.seg.filled .seg-inner{{opacity:1;}}
.seg.active{{animation:pulse 1s ease infinite;}}


@keyframes pulse{{0%,100%{{filter:brightness(1);}}50%{{filter:brightness(1.2);}}}}
.seg-disabled{{position:absolute;top:18px;height:20px;border-left:2px dashed #475569;}}
.stats{{display:flex;gap:24px;margin-top:8px;font-size:13px;color:#94a3b8;}}
.stats b{{color:#e2e8f0;font-variant-numeric:tabular-nums;}}
.legend{{display:flex;flex-wrap:wrap;gap:14px;margin-top:14px;padding-top:12px;
         border-top:1px solid #334155;}}
.leg-item{{display:flex;align-items:center;gap:5px;font-size:11px;color:#94a3b8;}}
.leg-dot{{width:10px;height:10px;border-radius:3px;}}
.finish-badge{{display:inline-block;background:#10b981;color:#fff;font-size:11px;font-weight:700;
               padding:2px 8px;border-radius:6px;margin-left:8px;opacity:0;transition:opacity .4s;}}
.finish-badge.show{{opacity:1;}}
.cal-note{{margin-top:14px;padding:10px 14px;background:rgba(59,130,246,0.1);border:1px solid #334155;
           border-radius:8px;font-size:12px;color:#94a3b8;line-height:1.5;}}
.cal-note b{{color:#60a5fa;}}
.summary-row{{display:flex;gap:24px;margin-top:14px;padding:10px 0;border-top:1px solid #334155;}}
.summary-cell{{flex:1;text-align:center;}}
.summary-cell .lbl{{font-size:10px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:.5px;}}
.summary-cell .val{{font-size:18px;font-weight:800;margin-top:2px;font-variant-numeric:tabular-nums;}}
.winner{{color:#10b981;}}
.loser{{color:#94a3b8;}}
</style></head><body>
<div class="race-wrap">
  <div class="race-header">
    <div class="race-title">Lifecycle Race</div>
    <div class="controls">
      <button class="btn" id="playBtn" onclick="togglePlay()">Play</button>
      <button class="btn" onclick="resetRace()">Reset</button>
      <span style="font-size:12px;color:#64748b;margin:0 4px;">Speed:</span>
      <button class="speed-btn sel" data-speed="1" onclick="setSpeed(1)">1x</button>
      <button class="speed-btn" data-speed="3" onclick="setSpeed(3)">3x</button>
      <button class="speed-btn" data-speed="6" onclick="setSpeed(6)">6x</button>
      <button class="speed-btn" data-speed="12" onclick="setSpeed(12)">12x</button>
    </div>
  </div>
  <div id="laneContainer"></div>
  <div id="summaryRow" class="summary-row" style="display:none;"></div>
  <div class="legend">{cat_legend}</div>
  {cal_note}
</div>
<script>
const DATA = {data_json};
const CAL_DELAY_H = {calendar_delay};
const BASE_DURATION_MS = 18000;
let speed = 1, playing = false, startTime = null, elapsed = 0, rafId = null;
const maxTime = Math.max(DATA.tradfi.total_time_hours, DATA.tokenized.total_time_hours);

function fmtTime(h) {{
  if (h < 1) return h.toFixed(2) + ' h';
  if (h < 48) return h.toFixed(1) + ' h';
  return (h / 24).toFixed(1) + ' d';
}}

function buildLanes() {{
  const c = document.getElementById('laneContainer');
  c.innerHTML = '';
  document.getElementById('summaryRow').style.display = 'none';
  ['tradfi','tokenized'].forEach(key => {{
    const d = DATA[key];
    const lane = document.createElement('div');
    lane.className = 'lane';
    const rLabel = key === 'tradfi' ? 'TradFi' : 'Tokenized';
    const totalWithCal = d.total_time_hours + CAL_DELAY_H;
    lane.innerHTML = `
      <div class="lane-head">
        <span class="lane-dot" style="background:${{d.color}};"></span>
        <span class="lane-name">${{rLabel}}</span>
        <span class="finish-badge" id="finish-${{key}}">DONE</span>
        <span class="lane-time" id="time-${{key}}">0.0 h</span>
      </div>
      <div class="track" id="track-${{key}}"></div>
      <div class="stats">
        <span>Processing: <b id="el-${{key}}">0.0 h</b></span>
        <span>Total (incl. wait): <b id="tot-${{key}}">${{fmtTime(totalWithCal)}}</b></span>
        <span>Stages: <b id="st-${{key}}">0 / ${{d.stages.filter(s=>s.enabled).length}}</b></span>
      </div>`;
    c.appendChild(lane);
    const track = document.getElementById('track-'+key);
    let leftPct = 0;
    d.stages.forEach((s,i) => {{
      if (!s.enabled) {{
        const dis = document.createElement('div');
        dis.className = 'seg-disabled';
        dis.style.left = leftPct + '%';
        track.appendChild(dis);
        return;
      }}
      const wPct = (s.time_hours / maxTime) * 100;
      const seg = document.createElement('div');
      seg.className = 'seg';
      seg.id = 'seg-'+key+'-'+s.id;
      seg.style.left = leftPct + '%';
      seg.style.width = '0%';
      seg.style.background = s.color;
      seg.dataset.targetWidth = wPct;
      seg.dataset.startHour = leftPct * maxTime / 100;
      seg.dataset.endHour = (leftPct + wPct) * maxTime / 100;
      seg.innerHTML = '<span class="seg-inner">' + s.label + '</span>';
      seg.title = s.label + ' (' + fmtTime(s.time_hours) + ')';
      track.appendChild(seg);
      leftPct += wPct;
    }});
  }});
}}

function showSummary() {{
  const sr = document.getElementById('summaryRow');
  const tT = DATA.tradfi.total_time_hours + CAL_DELAY_H;
  const tK = DATA.tokenized.total_time_hours + CAL_DELAY_H;
  const delta = tK - tT;
  const tWin = delta < 0 ? 'winner' : 'loser';
  const kWin = delta < 0 ? 'loser' : 'winner';
  const fasterRoute = delta < 0 ? 'Tokenized' : 'TradFi';
  const savedH = Math.abs(delta);
  sr.innerHTML = `
    <div class="summary-cell"><div class="lbl">TradFi Total</div><div class="val ${{tWin}}">${{fmtTime(tT)}}</div></div>
    <div class="summary-cell"><div class="lbl">Tokenized Total</div><div class="val ${{kWin}}">${{fmtTime(tK)}}</div></div>
    <div class="summary-cell"><div class="lbl">Advantage</div><div class="val winner">${{fasterRoute}} saves ${{fmtTime(savedH)}}</div></div>`;
  sr.style.display = 'flex';
}}

function frame(ts) {{
  if (!startTime) startTime = ts;
  elapsed = (ts - startTime) * speed;
  const simFrac = Math.min(elapsed / BASE_DURATION_MS, 1);
  const simHour = simFrac * maxTime;

  ['tradfi','tokenized'].forEach(key => {{
    const d = DATA[key];
    let filled = 0;
    d.stages.forEach(s => {{
      if (!s.enabled) return;
      const seg = document.getElementById('seg-'+key+'-'+s.id);
      if (!seg) return;
      const sh = parseFloat(seg.dataset.startHour);
      const eh = parseFloat(seg.dataset.endHour);
      const tw = parseFloat(seg.dataset.targetWidth);
      if (simHour >= eh) {{
        seg.style.width = tw + '%';
        seg.classList.add('filled');
        seg.classList.remove('active');
        filled++;
      }} else if (simHour > sh) {{
        const frac = (simHour - sh) / (eh - sh);
        seg.style.width = (tw * frac) + '%';
        seg.classList.add('active');
        seg.classList.remove('filled');
      }} else {{
        seg.style.width = '0%';
        seg.classList.remove('active','filled');
      }}
    }});
    const elH = Math.min(simHour, d.total_time_hours);
    document.getElementById('el-'+key).textContent = fmtTime(elH);
    document.getElementById('time-'+key).textContent = fmtTime(elH) + ' / ' + fmtTime(d.total_time_hours);
    const en = d.stages.filter(s=>s.enabled).length;
    document.getElementById('st-'+key).textContent = filled + ' / ' + en;
    if (simHour >= d.total_time_hours) document.getElementById('finish-'+key).classList.add('show');
  }});

  if (simFrac < 1 && playing) rafId = requestAnimationFrame(frame);
  else if (simFrac >= 1) {{
    playing = false;
    document.getElementById('playBtn').textContent = 'Play';
    showSummary();
  }}
}}

function togglePlay() {{
  playing = !playing;
  document.getElementById('playBtn').textContent = playing ? 'Pause' : 'Play';
  if (playing) {{
    if (elapsed >= BASE_DURATION_MS) resetRace();
    startTime = null;
    rafId = requestAnimationFrame(frame);
  }} else if (rafId) cancelAnimationFrame(rafId);
}}

function resetRace() {{
  playing = false; startTime = null; elapsed = 0;
  if (rafId) cancelAnimationFrame(rafId);
  document.getElementById('playBtn').textContent = 'Play';
  buildLanes();
}}

function setSpeed(s) {{
  speed = s;
  document.querySelectorAll('.speed-btn').forEach(b => {{
    b.classList.toggle('sel', parseInt(b.dataset.speed) === s);
  }});
}}

buildLanes();
</script></body></html>
"""


def render_race(
    stage_mix_df,
    scenario: str,
    asset: str,
    height: int = 480,
) -> None:
    df = stage_mix_df[
        (stage_mix_df["scenario_id"] == scenario)
        & (stage_mix_df["asset_id"] == asset)
    ].copy()

    calendar_delay = CALENDAR_DELAY_HOURS.get(asset, 0.0)

    tradfi_mix: dict[str, dict] = {}
    tokenized_mix: dict[str, dict] = {}
    for _, row in df.iterrows():
        entry = row.to_dict()
        if row["route_id"] == "TRADFI":
            tradfi_mix[row["stage_id"]] = entry
        else:
            tokenized_mix[row["stage_id"]] = entry

    html = build_race_html(tradfi_mix, tokenized_mix, calendar_delay)
    components.html(html, height=height, scrolling=False)
