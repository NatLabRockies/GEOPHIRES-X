"""
Tornado + Monte Carlo sensitivity around the NOAK endpoint of the LCOE waterfall.

The waterfall (`lcoe_waterfall.py`) tells a deterministic story from a FOAK field
to a ~$45/MWh NOAK endpoint. This script answers the reviewer's question the
waterfall cannot: *how sensitive is that $45 to the assumptions?*

It produces two figures:

  1. tornado.png  -- one-at-a-time sensitivity. Each of the waterfall's five
     levers (plus a sixth, COST OF CAPITAL, which the waterfall deliberately
     excluded) is swung from a favorable to an unfavorable but realistic 2035
     value, holding everything else at the NOAK base. Bars are sorted by swing.

  2. montecarlo.png -- all uncertain inputs varied *simultaneously* from
     triangular distributions, N runs, giving a P10-P50-P90 band on LCOE and the
     probability of meeting the $45/MWh moonshot target.

Everything is anchored on the same NOAK configuration as the waterfall endpoint.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from geophires_x_client import GeophiresXClient
from geophires_x_client.geophires_input_parameters import GeophiresInputParameters

HERE = Path(__file__).parent
EXAMPLE = str(HERE.parent.parent / 'tests' / 'examples' / 'example1.txt')
TARGET = 45.0  # DOE Enhanced Geothermal Shot 2035 target, $/MWh

# NOAK endpoint of the waterfall (its final stacked state).
BASE = {
    'Reservoir Model': 1,
    'Reservoir Depth': 4,
    'Gradient 1': 60,
    'Number of Production Wells': 4,
    'Number of Injection Wells': 4,
    'Production Well Diameter': 8.5,
    'Injection Well Diameter': 8.5,
    'Production Flow Rate per Well': 80,
    'Productivity Index': 10,
    'Injectivity Index': 10,
    'Number of Fractures': 60,
    'Fracture Height': 1000,
    'Power Plant Type': 1,
    'Utilization Factor': 0.85,
    'Well Drilling Cost Correlation': 1,
    'Well Drilling and Completion Capital Cost Adjustment Factor': 1.2,
    'Capital Cost for Power Plant for Electricity Generation': 2300,
    'Fixed Charge Rate': 0.05,
    'Print Output to Console': 0,
}

# ----- per-process GEOPHIRES client (multiprocessing) -----
_client: GeophiresXClient | None = None


def _init():
    global _client
    _client = GeophiresXClient()


def _lcoe(overrides: dict) -> float:
    """Return breakeven LCOE ($/MWh) for BASE updated with `overrides`."""
    global _client
    if _client is None:
        _client = GeophiresXClient()
    params = {**BASE, **overrides}
    try:
        r = _client.get_geophires_result(
            GeophiresInputParameters(params=params, from_file_path=EXAMPLE)
        ).result
        return r['SUMMARY OF RESULTS']['Electricity breakeven price']['value'] * 10.0
    except Exception:
        return float('nan')


# ---------------------------------------------------------------------------
# Tornado: same categories as the waterfall + cost of capital.
# Each entry: (label, favorable-overrides, unfavorable-overrides).
# "favorable" pushes LCOE down, "unfavorable" pushes it up; ranges are realistic
# 2035 bounds, centered on the NOAK base.
# ---------------------------------------------------------------------------
TORNADO = [
    ('Temperature\n(gradient 52-68 °C/km)',
     {'Gradient 1': 68}, {'Gradient 1': 52}),
    ('Cost of capital\n(FCR 4-9%)',
     {'Fixed Charge Rate': 0.04}, {'Fixed Charge Rate': 0.09}),
    ('Monobore+laterals→flow→turbine\n(flow 66-92 kg/s, plant 2.0-2.8 k$/kW)',
     {'Production Flow Rate per Well': 92, 'Capital Cost for Power Plant for Electricity Generation': 2000},
     {'Production Flow Rate per Well': 66, 'Capital Cost for Power Plant for Electricity Generation': 2800}),
    ('Subsurface / drawdown\n(60→100 vs 30 fractures)',
     {'Number of Fractures': 100, 'Fracture Height': 1200},
     {'Number of Fractures': 30, 'Fracture Height': 650}),
    ('Drilling cost\n(NOAK factor 0.95-1.5)',
     {'Well Drilling and Completion Capital Cost Adjustment Factor': 0.95},
     {'Well Drilling and Completion Capital Cost Adjustment Factor': 1.5}),
    ('Scale / field size\n(6 vs 3 doublets)',
     {'Number of Production Wells': 6, 'Number of Injection Wells': 6},
     {'Number of Production Wells': 3, 'Number of Injection Wells': 3}),
]


def run_tornado(base_lcoe: float):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    rows = []
    for label, fav, unf in TORNADO:
        lo = _lcoe(fav)   # favorable -> low LCOE
        hi = _lcoe(unf)   # unfavorable -> high LCOE
        rows.append((label, lo, hi, abs(hi - lo)))
    rows.sort(key=lambda r: r[3])  # smallest swing at bottom, largest on top

    fig, ax = plt.subplots(figsize=(11, 6.5))
    y = np.arange(len(rows))
    for i, (label, lo, hi, swing) in enumerate(rows):
        left, right = min(lo, hi), max(lo, hi)
        ax.barh(i, right - base_lcoe, left=base_lcoe, color='#c0504d', alpha=0.85,
                edgecolor='white')   # unfavorable side (right of base)
        ax.barh(i, left - base_lcoe, left=base_lcoe, color='#4f81bd', alpha=0.85,
                edgecolor='white')   # favorable side (left of base)
        ax.text(right + 0.4, i, f'${hi:.0f}', va='center', ha='left', fontsize=9, color='#c0504d')
        ax.text(left - 0.4, i, f'${lo:.0f}', va='center', ha='right', fontsize=9, color='#4f81bd')

    ax.axvline(base_lcoe, color='k', lw=1.5)
    ax.text(base_lcoe, len(rows) - 0.3, f'  NOAK base ${base_lcoe:.0f}',
            ha='left', va='bottom', fontsize=9, fontweight='bold')
    ax.axvline(TARGET, color='#2e7d32', lw=1.3, ls='--')
    ax.text(TARGET, -0.9, f'$45 moonshot', ha='center', va='top',
            fontsize=8.5, color='#2e7d32')

    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=8.5)
    ax.set_xlabel('LCOE ($/MWh)')
    ax.set_title('Tornado — sensitivity of the $45/MWh NOAK endpoint\n'
                 '(blue = favorable / red = unfavorable, realistic 2035 bounds)',
                 fontsize=13, fontweight='bold')
    ax.set_ylim(-1.2, len(rows) - 0.2)
    ax.grid(axis='x', alpha=0.3)
    for s in ['top', 'right', 'left']:
        ax.spines[s].set_visible(False)
    fig.text(0.01, 0.01,
             'Blue/red bar = LCOE if that driver alone hits its favorable/unfavorable 2035 value, all else at NOAK base. '
             'Cost of capital (FCR) is the lever the waterfall excluded.',
             fontsize=7, color='#666', style='italic')
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    out = HERE / 'tornado.png'
    fig.savefig(out, dpi=150)
    print(f'Saved {out}')
    print('\nTornado (sorted by swing):')
    for label, lo, hi, swing in reversed(rows):
        print(f'  {label.splitlines()[0]:42s} ${lo:5.1f} .. ${hi:5.1f}   swing ${swing:4.1f}')


# ---------------------------------------------------------------------------
# Monte Carlo: all drivers varied simultaneously (triangular: min, mode, max).
# ---------------------------------------------------------------------------
def _sample(rng) -> dict:
    doublets = int(round(rng.triangular(3, 4, 6)))
    return {
        'Gradient 1': rng.triangular(52, 60, 68),
        'Production Flow Rate per Well': rng.triangular(66, 80, 92),
        'Capital Cost for Power Plant for Electricity Generation': rng.triangular(2000, 2300, 2800),
        'Well Drilling and Completion Capital Cost Adjustment Factor': rng.triangular(0.95, 1.2, 1.5),
        'Fixed Charge Rate': rng.triangular(0.04, 0.05, 0.09),
        'Productivity Index': rng.triangular(7, 10, 14),
        'Injectivity Index': rng.triangular(7, 10, 14),
        'Number of Fractures': int(round(rng.triangular(30, 60, 100))),
        'Fracture Height': rng.triangular(700, 1000, 1200),
        'Number of Production Wells': doublets,
        'Number of Injection Wells': doublets,
    }


def _worker_chunk(seed: int, count: int, csv_path: str):
    """Run `count` MC samples and APPEND their LCOEs to csv_path (one per line).

    Invoked as a fresh subprocess per chunk so GEOPHIRES's per-run memory leak is
    reset and partial results are persisted (a kill cannot wipe earlier chunks).
    """
    rng = np.random.default_rng(seed)
    _init()
    with open(csv_path, 'a') as f:
        for _ in range(count):
            f.write(f'{_lcoe(_sample(rng))}\n')
            f.flush()


def _replay_inputs(n: int, chunk: int = 50) -> list:
    """Reconstruct the exact sampled inputs for an n-run MC from the fixed seeds.

    The MC runs in chunks of `chunk`, chunk `idx` seeded `1000 + idx`. Replaying
    the same RNG stream regenerates the identical inputs WITHOUT re-running
    GEOPHIRES, so results are fully reproducible from the saved LCOEs alone.
    """
    out, done, idx = [], 0, 0
    while done < n:
        c = min(chunk, n - done)
        rng = np.random.default_rng(1000 + idx)
        for _ in range(c):
            out.append(_sample(rng))
        done += c
        idx += 1
    return out


# friendly column name per (distinct) sampled driver, for the spreadsheet
_FRIENDLY = [
    ('Gradient 1', 'gradient_C_per_km'),
    ('Production Flow Rate per Well', 'flow_kg_per_s'),
    ('Capital Cost for Power Plant for Electricity Generation', 'plant_cost_USD_per_kW'),
    ('Well Drilling and Completion Capital Cost Adjustment Factor', 'drilling_factor'),
    ('Fixed Charge Rate', 'fixed_charge_rate'),
    ('Productivity Index', 'productivity_index_kg_s_bar'),
    ('Number of Fractures', 'num_fractures'),
    ('Fracture Height', 'fracture_height_m'),
    ('Number of Production Wells', 'doublets'),
]


def build_workbook(lcoes: np.ndarray):
    """Write montecarlo_results.xlsx (+ .csv) from the LCOE array via input replay."""
    import pandas as pd

    inputs = _replay_inputs(len(lcoes))
    rows = []
    for s, lc in zip(inputs, lcoes):
        row = {friendly: s[key] for key, friendly in _FRIENDLY}
        row['LCOE_USD_per_MWh'] = round(float(lc), 2)
        rows.append(row)
    df = pd.DataFrame(rows)
    df.insert(0, 'run', range(1, len(df) + 1))

    v = df['LCOE_USD_per_MWh'].to_numpy()
    pct = lambda q: round(float(np.percentile(v, q)), 2)
    summary = pd.DataFrame({
        'statistic': ['runs', 'mean', 'std', 'min', 'P10', 'P25', 'P50 (median)',
                      'P75', 'P90', 'max', '% of runs <= $45 (moonshot)',
                      '% of runs <= $52 (central)'],
        'LCOE_USD_per_MWh': [len(v), round(float(v.mean()), 2), round(float(v.std()), 2),
                             round(float(v.min()), 2), pct(10), pct(25), pct(50), pct(75),
                             pct(90), round(float(v.max()), 2),
                             round(float((v <= 45).mean() * 100), 1),
                             round(float((v <= 52).mean() * 100), 1)],
    })

    # tornado (recompute -- 12 GEOPHIRES runs) for a self-contained workbook
    _init()
    base = _lcoe({})
    trows = []
    for label, fav, unf in TORNADO:
        lo, hi = _lcoe(fav), _lcoe(unf)
        trows.append({'driver': label.replace('\n', ' '),
                      'favorable_LCOE': round(lo, 2), 'base_LCOE': round(base, 2),
                      'unfavorable_LCOE': round(hi, 2), 'swing': round(abs(hi - lo), 2)})
    tornado_df = pd.DataFrame(trows).sort_values('swing', ascending=False)

    inputs_doc = pd.DataFrame({
        'driver': [f for _, f in _FRIENDLY],
        'distribution': ['triangular(min, mode, max)'] * len(_FRIENDLY),
        'min': [52, 66, 2000, 0.95, 0.04, 7, 30, 700, 3],
        'mode': [60, 80, 2300, 1.2, 0.05, 10, 60, 1000, 4],
        'max': [68, 92, 2800, 1.5, 0.09, 14, 100, 1200, 6],
    })

    df.to_csv(HERE / 'montecarlo_results.csv', index=False)
    xlsx = HERE / 'montecarlo_results.xlsx'
    try:
        with pd.ExcelWriter(xlsx, engine='openpyxl') as w:
            summary.to_excel(w, sheet_name='summary', index=False)
            df.to_excel(w, sheet_name='monte_carlo_runs', index=False)
            inputs_doc.to_excel(w, sheet_name='input_distributions', index=False)
            tornado_df.to_excel(w, sheet_name='tornado', index=False)
        print(f'Saved {xlsx} (+ .csv)  [{len(df)} runs, 4 sheets]')
    except ImportError:
        print(f'Saved {HERE / "montecarlo_results.csv"} '
              f'(install openpyxl for the .xlsx workbook: pip install openpyxl)')


def run_montecarlo(n: int, base_lcoe: float):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    # NOTE: GEOPHIRES (a) serializes across processes (JIT/file-lock contention)
    # and (b) leaks memory across hundreds of runs in one process (it OOM-kills
    # near ~400 runs). So we run the MC in *fresh subprocess chunks* that each
    # append results to a CSV: the leak resets every chunk, and partial results
    # survive a kill. See `_worker_chunk` and the CLI dispatch at the bottom.
    import subprocess
    import sys
    import time

    csv = HERE / 'montecarlo_samples.csv'
    csv.unlink(missing_ok=True)
    chunk = 50
    env = {**os.environ, 'PYTHONPATH': 'src' + os.pathsep + os.environ.get('PYTHONPATH', '')}
    t0 = time.time()
    done = 0
    idx = 0
    while done < n:
        c = min(chunk, n - done)
        subprocess.run([sys.executable, __file__, '_mcworker', str(1000 + idx), str(c), str(csv)],
                       check=True, env=env)
        done += c
        idx += 1
        have = sum(1 for _ in open(csv)) if csv.exists() else 0
        rate = have / (time.time() - t0) if have else 0
        print(f'  MC chunk {idx}: {have}/{n} done ({rate:.2f}/s, eta {((n - have) / rate if rate else 0):.0f}s)',
              flush=True)

    lcoes = np.loadtxt(csv)
    lcoes = lcoes[np.isfinite(lcoes)]

    p10, p50, p90 = np.percentile(lcoes, [10, 50, 90])
    p_target = float((lcoes <= TARGET).mean() * 100)

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.hist(lcoes, bins=45, color='#4f81bd', alpha=0.8, edgecolor='white')
    for x, c, lab in [(p10, '#2e7d32', f'P10 ${p10:.0f}'),
                      (p50, 'k', f'P50 ${p50:.0f}'),
                      (p90, '#c0504d', f'P90 ${p90:.0f}')]:
        ax.axvline(x, color=c, lw=1.6)
        ax.text(x, ax.get_ylim()[1] * 0.96, '  ' + lab, rotation=90,
                va='top', ha='left', fontsize=9, color=c, fontweight='bold')
    ax.axvline(TARGET, color='#2e7d32', lw=1.4, ls='--')
    ax.text(TARGET, ax.get_ylim()[1] * 0.55, f'  $45 moonshot\n  ({p_target:.0f}% of runs ≤ target)',
            va='center', ha='left', fontsize=9, color='#2e7d32')

    ax.set_xlabel('LCOE ($/MWh)')
    ax.set_ylabel('runs')
    ax.set_title(f'Monte Carlo — {len(lcoes)} runs, all 2035 drivers varied simultaneously\n'
                 f'P50 ${p50:.0f}/MWh, P10-P90 ${p10:.0f}-${p90:.0f}/MWh',
                 fontsize=13, fontweight='bold')
    ax.grid(axis='y', alpha=0.3)
    for s in ['top', 'right']:
        ax.spines[s].set_visible(False)
    fig.text(0.01, 0.01,
             'Triangular distributions (min, mode=NOAK base, max) on temperature, flow, plant $/kW, drilling factor, '
             'cost of capital (FCR), productivity, fractures and field size. See hypothesis.md for ranges.',
             fontsize=7, color='#666', style='italic')
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    out = HERE / 'montecarlo.png'
    fig.savefig(out, dpi=150)
    print(f'Saved {out}')
    print(f'\nMonte Carlo ({len(lcoes)} runs): P10=${p10:.1f} P50=${p50:.1f} P90=${p90:.1f}  '
          f'| {p_target:.0f}% meet the $45 target  | mean=${lcoes.mean():.1f}')
    build_workbook(lcoes)
    return p10, p50, p90, p_target


def main():
    base = _lcoe({})
    print(f'NOAK base LCOE = ${base:.1f}/MWh\n')
    run_tornado(base)
    print()
    run_montecarlo(400, base)


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '_mcworker':
        # _mcworker <seed> <count> <csv_path>  -- internal chunk worker
        _worker_chunk(int(sys.argv[2]), int(sys.argv[3]), sys.argv[4])
    elif len(sys.argv) > 1 and sys.argv[1] == 'excel':
        # rebuild montecarlo_results.xlsx from saved montecarlo_samples.csv (no rerun)
        build_workbook(np.loadtxt(HERE / 'montecarlo_samples.csv'))
    else:
        main()
