"""
LCOE cost-reduction waterfall for next-gen (EGS) geothermal.

Reproduces the "innovations concatenate into a step-change in cost" story
(slide 45c) using GEOPHIRES-X. A conservative first-of-a-kind (FOAK) EGS field
is taken as "today" (~$190/MWh); levers are applied *cumulatively* and the
levelized cost of electricity (LCOE) is read after each step. The stack lands at
~$52/MWh -- the EXPECTED (central / Monte-Carlo-median) outcome under realistic
2035 uncertainty (see tornado_montecarlo.py). The endpoint is deliberately
anchored on *central*, not favorable, assumptions: cost of capital at the median
fixed charge rate (5.8%, not an optimistic 5.0%) and plant $/kW at GEOPHIRES's
own size correlation (no asserted economy-of-scale discount). The $45/MWh DOE
"moonshot" is still reachable but is a favorable (~P15-P20) case, not the
central expectation -- so the headline does not oversell.

Five levers, in order (order matters in a cumulative waterfall):
    1. Scale          -- "drill the field": more wells amortize fixed
                         (exploration/surface) cost + cross-well learning.
    2. Temperature    -- deeper/hotter resource. Conversion efficiency is
                         coupled to temperature, so this carries the efficiency
                         gain (plant held at subcritical ORC throughout).
    3. Monobore + laterals -> flow -> turbine -- one causal chain: a wider
                         monobore plus horizontal/multilateral laterals push
                         far more flow per well (low parasitic pumping), which
                         lifts power per well and unlocks a larger, cheaper
                         turbine (lower plant $/kW).
    4. Subsurface     -- reservoir engineering: a larger heat-exchange network
                         lowers thermal drawdown over the project life. Applied
                         AFTER the flow lever because higher flow draws the
                         reservoir down faster; this lever recovers the
                         sustained output (the two are physically coupled).
    5. Drilling cost  -- faster/simpler drilling (higher ROP, monobore) plus the
                         drilling-cost share of FOAK->NOAK learning-by-doing.

What is model physics vs. assumption:
    * GEOPHIRES OUTPUTS (derived): scale, temperature/efficiency, subsurface
      drawdown, flow, monobore pumping.
    * INPUT ASSUMPTIONS (asserted): turbine $/kW, drilling-cost factors.
    (No cost-of-capital lever: economics use a fixed charge rate throughout.)

Run:  python docs/waterfall/lcoe_waterfall.py
Outputs: lcoe_waterfall.png and lcoe_waterfall.csv in this folder.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'src'))

from geophires_x_client import GeophiresXClient
from geophires_x_client.geophires_input_parameters import GeophiresInputParameters

BASE_FILE = REPO / 'tests' / 'examples' / 'example1.txt'

client = GeophiresXClient()


def run_case(params: dict) -> dict:
    """Run GEOPHIRES and return key techno-economic metrics for one case."""
    result = client.get_geophires_result(
        GeophiresInputParameters(params=params, from_file_path=BASE_FILE)
    ).result
    summary = result['SUMMARY OF RESULTS']
    surf = result['SURFACE EQUIPMENT SIMULATION RESULTS']
    mw = summary['Average Net Electricity Production']['value']
    nprod = summary['Number of production wells']['value']
    return {
        'lcoe': summary['Electricity breakeven price']['value'] * 10.0,  # 1 cent/kWh = 10 $/MWh
        'mw': mw,
        'nprod': nprod,
        'mw_per_well': mw / nprod,
        'flow_per_well': summary['Flowrate per production well']['value'],
        'pump_mw': surf['Average Pumping Power']['value'],
        'capex': result['CAPITAL COSTS (M$)']['Total capital costs']['value'],
    }


# ----------------------------------------------------------------------------
# "Today": conservative FOAK EGS field -- small (2 doublets), cool resource,
# narrow bore, low flow, baseline reservoir, subcritical ORC, FOAK cost premium.
# ----------------------------------------------------------------------------
today = {
    'Reservoir Model': 1,                  # multiple parallel fractures (EGS)
    'Reservoir Depth': 3,                  # km
    'Gradient 1': 50,                      # degC/km
    'Number of Production Wells': 1,
    'Number of Injection Wells': 1,
    'Production Well Diameter': 6.625,     # inch (narrow / telescoped)
    'Injection Well Diameter': 6.625,      # inch
    'Production Flow Rate per Well': 40,   # kg/s (low)
    'Productivity Index': 5,               # kg/s/bar
    'Injectivity Index': 5,
    'Number of Fractures': 20,             # baseline heat-exchange network
    'Fracture Height': 900,                # m
    'Power Plant Type': 1,                 # subcritical ORC (held throughout)
    'Utilization Factor': 0.85,
    'Well Drilling Cost Correlation': 1,
    'Well Drilling and Completion Capital Cost Adjustment Factor': 1.7,  # FOAK premium
    'Fixed Charge Rate': 0.058,            # cost of capital: central/median case (see below)
    'Print Output to Console': 0,
}

# Cumulative lever deltas applied on top of the running case.
levers = [
    ('Scale\n(more wells)', {
        'Number of Production Wells': 4,
        'Number of Injection Wells': 4,
        'Well Drilling and Completion Capital Cost Adjustment Factor': 1.5,  # cross-well learning
    }),
    ('Temperature', {
        'Reservoir Depth': 4,
        'Gradient 1': 60,                  # ~260 C bottom-hole
    }),
    ('Monobore + laterals\n→ flow → turbine', {
        # wider monobore + laterals: far more flow per well at low pumping
        'Production Well Diameter': 8.5,
        'Injection Well Diameter': 8.5,
        'Production Flow Rate per Well': 80,
        'Productivity Index': 10,
        'Injectivity Index': 10,
        # the bigger plant gets a larger turbine, but we assert NO economy-of-scale
        # discount: 2480 $/kW is GEOPHIRES's own size-correlated estimate for this
        # plant. This is the central (not favorable) cost. (Input assumption.)
        'Capital Cost for Power Plant for Electricity Generation': 2480,  # $/kW
    }),
    ('Subsurface\n(lower drawdown)', {
        'Number of Fractures': 60,         # more frac stages (multilateral laterals)
        'Fracture Height': 1000,           # larger heat-exchange area resists drawdown
    }),
    ('Drilling cost\n(ROP + NOAK)', {
        # faster/simpler drilling + drilling share of FOAK->NOAK learning.
        # 1.2 keeps a realistic deep-EGS premium over the generic correlation
        # (NOT driven below the baseline).
        'Well Drilling and Completion Capital Cost Adjustment Factor': 1.2,
    }),
]


def main():
    running = dict(today)
    hdr = f"{'step':30s} {'LCOE':>8s} {'net MW':>8s} {'wells':>6s} {'MW/well':>8s} {'pump MW':>8s}"
    print(hdr); print('-' * len(hdr))

    def show(tag, m, prev=None):
        d = '' if prev is None else f'  Δ={m["lcoe"]-prev:+7.1f}'
        print(f"{tag:30s} {m['lcoe']:7.1f}$ {m['mw']:7.1f} {m['nprod']:6.0f} "
              f"{m['mw_per_well']:7.2f} {m['pump_mw']:7.2f}{d}")

    metrics = [run_case(running)]
    labels = ['Today']
    show('Today (FOAK)', metrics[0])

    for name, delta in levers:
        running.update(delta)
        m = run_case(running)
        show('+ ' + name.replace('\n', ' '), m, metrics[-1]['lcoe'])
        metrics.append(m)
        labels.append(name)

    lcoes = [m['lcoe'] for m in metrics]
    labels.append('Central case\n(~P50)')
    lcoes.append(lcoes[-1])
    metrics.append(metrics[-1])

    # ---- write csv ----
    import csv
    with open(HERE / 'lcoe_waterfall.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['step', 'LCOE_USD_per_MWh', 'net_MW', 'production_wells',
                    'net_MW_per_well', 'flow_per_well_kg_s', 'pump_MW', 'total_CAPEX_MUSD'])
        cols = ['Today'] + [n.replace('\n', ' ') for n, _ in levers]
        for name, m in zip(cols, metrics):
            w.writerow([name, round(m['lcoe'], 1), round(m['mw'], 1), int(m['nprod']),
                        round(m['mw_per_well'], 2), round(m['flow_per_well'], 0),
                        round(m['pump_mw'], 2), round(m['capex'], 1)])

    plot_waterfall(labels, lcoes, metrics)


def plot_waterfall(labels, lcoes, metrics):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    anchor = '#34495e'
    lever = '#2e86c1'
    n = len(labels)
    fig, (ax, tax) = plt.subplots(
        2, 1, figsize=(13, 8), gridspec_kw={'height_ratios': [4, 1]})

    start = lcoes[0]
    target = lcoes[-2]

    for i in range(n):
        if i == 0 or i == n - 1:
            val = lcoes[i] if i == 0 else target
            ax.bar(i, val, width=0.6, color=anchor, zorder=3)
            ax.text(i, val + 2, f'${val:.0f}', ha='center', va='bottom',
                    fontweight='bold', fontsize=12)
        else:
            top = lcoes[i - 1]
            bottom = lcoes[i]
            ax.bar(i, top - bottom, bottom=bottom, width=0.6, color=lever, zorder=3)
            ax.text(i, top + 1.5, f'{bottom - top:+.0f}', ha='center', va='bottom',
                    color='#c0392b', fontsize=11, fontweight='bold')
            ax.plot([i - 1 + 0.3, i + 0.3], [top, top], color='gray',
                    lw=0.8, ls='--', zorder=2)
        if 0 < i < n - 1:
            ax.plot([i + 0.3, i + 1 - 0.3], [lcoes[i], lcoes[i]],
                    color='gray', lw=0.8, ls='--', zorder=2)
        ax.text(i, 1.5, f"{metrics[i]['mw']:.0f} MW", ha='center', va='bottom',
                fontsize=8, color='white' if i in (0, n - 1) else '#555',
                fontweight='bold', zorder=4)

    ax.set_xticks(range(n))
    ax.set_xticklabels(labels, fontsize=9.5)
    ax.set_ylabel('LCOE  ($/MWh)', fontsize=12)
    ax.set_title('Next-Gen Geothermal LCOE Waterfall — Innovations Concatenate\n'
                 rf'(GEOPHIRES-X; \${start:.0f}/MWh $\rightarrow$ \${target:.0f}/MWh, subcritical ORC throughout)',
                 fontsize=14, fontweight='bold')
    ax.set_ylim(0, start * 1.12)
    # $45 DOE moonshot reference -- below the $52 central endpoint (favorable case)
    ax.axhline(45, color='#2e7d32', lw=1.2, ls='--', alpha=0.8)
    ax.text(n - 1, 45, '  $45 moonshot (favorable case)', color='#2e7d32',
            fontsize=8.5, va='center', ha='right')
    ax.grid(axis='y', alpha=0.3)
    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)

    # ---- power table ----
    tax.axis('off')
    row_labels = ['Net power (MW)', 'Production wells', 'Net MW / well', 'Flow / well (kg/s)']
    cell_text = [
        [f"{m['mw']:.1f}" for m in metrics],
        [f"{m['nprod']:.0f}" for m in metrics],
        [f"{m['mw_per_well']:.2f}" for m in metrics],
        [f"{m['flow_per_well']:.0f}" for m in metrics],
    ]
    # short headers so the 7 columns don't overlap
    col_labels = ['Today', 'Scale', 'Temp', 'Monobore+\nlaterals',
                  'Subsurface', 'Drilling', 'Central\n(~P50)']
    tbl = tax.table(cellText=cell_text, rowLabels=row_labels, colLabels=col_labels,
                    cellLoc='center', rowLoc='right', loc='center')
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    tbl.scale(1, 1.4)
    for (r, c), cell in tbl.get_celld().items():
        if r == 0:
            cell.set_text_props(fontweight='bold')
        if c == -1:
            cell.set_text_props(fontweight='bold', ha='right')
        cell.set_edgecolor('#dddddd')

    fig.text(0.01, 0.005,
             'Notes: Endpoint ~ \\$52/MWh = central (Monte-Carlo-median) case. Anchored on central assumptions: cost of capital at median FCR 5.8% and plant \\$/kW at GEOPHIRES\'s own ~2480 correlation (no economy-of-scale discount).\n'
             'The \\$45 DOE moonshot is reachable but is a favorable (~P15-20) case. Flow & subsurface are coupled; turbine \\$/kW, drilling factors and FCR are input assumptions, not GEOPHIRES outputs. See tornado_montecarlo.py / PHYSICS.md.',
             fontsize=6.5, color='#666', style='italic')

    fig.tight_layout(rect=(0, 0.02, 1, 1))
    out = HERE / 'lcoe_waterfall.png'
    fig.savefig(out, dpi=150)
    print(f'\nSaved chart -> {out}')


if __name__ == '__main__':
    main()
