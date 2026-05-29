"""
LCOE cost-reduction waterfall for next-gen (EGS) geothermal -- COMPREHENSIVE.

Reproduces the "innovations concatenate into a step-change in cost" story
(slide 45c) using GEOPHIRES-X, broken into the full set of defensible levers
(technical backup version). A conservative first-of-a-kind (FOAK) EGS field is
taken as "today"; levers are applied *cumulatively* and the levelized cost of
electricity (LCOE) is read after each step.

Levers, in order (order matters in a cumulative waterfall):
    1. Scale            -- "drill the field": more wells. Amortizes fixed
                           (exploration/surface) cost + cross-well learning.
    2. Temperature      -- deeper/hotter resource. Conversion efficiency is
                           coupled to temperature, so this carries the
                           efficiency gain (plant held at subcritical ORC).
    3. Flow / laterals  -- more throughput per well. Models the *effect* of
                           horizontal/multilateral laterals (more flow + better
                           connectivity); explicit lateral geometry would need a
                           closed-loop reservoir model, so it is represented
                           here by flow + productivity index.
    4. Monobore         -- wider bore cuts parasitic pumping (friction ~1/D^5).
                           Small in $/MWh but it is what makes high flow viable.
    5. Subsurface       -- reservoir engineering: a larger heat-exchange network
                           resists thermal drawdown so the high flow pays off
                           (coupled with lever 3).
    6. Drilling ROP     -- faster/simpler drilling (MWD/information) lowers the
                           per-well drilling cost (technology learning).
    7. Turbine scale    -- the larger plant unlocks a bigger, cheaper turbine
                           (lower plant $/kW). INPUT ASSUMPTION, not a model
                           output.
    8. Cost of capital  -- FOAK -> NOAK de-risking: lower discount rate, plus a
                           further drilling-cost reduction from repeated
                           execution.

Note on what is model physics vs. assumption:
    * GEOPHIRES OUTPUTS (derived): scale, temperature/efficiency, flow, monobore
      pumping, subsurface drawdown, discount-rate effect.
    * INPUT ASSUMPTIONS (asserted): turbine $/kW, drilling-cost factors.

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
# narrow bore, low flow, baseline reservoir, subcritical ORC, FOAK cost premium,
# high (FOAK) discount rate. Economic Model 2 so the discount rate is explicit.
# ----------------------------------------------------------------------------
today = {
    'Reservoir Model': 1,                  # multiple parallel fractures (EGS)
    'Reservoir Depth': 3,                  # km
    'Gradient 1': 50,                      # degC/km
    'Number of Production Wells': 2,
    'Number of Injection Wells': 2,
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
    'Well Drilling and Completion Capital Cost Adjustment Factor': 1.5,  # FOAK premium
    'Economic Model': 2,                   # standard levelized cost (uses Discount Rate)
    'Discount Rate': 0.10,                 # FOAK cost of capital
    'Print Output to Console': 0,
}

# Cumulative lever deltas. 'cat' tags the bar colour: 'phys' = GEOPHIRES-derived
# physics, 'cost' = input cost/finance assumption.
levers = [
    ('Scale\n(more wells)', 'phys', {
        'Number of Production Wells': 8,
        'Number of Injection Wells': 8,
        'Well Drilling and Completion Capital Cost Adjustment Factor': 1.35,  # cross-well learning
    }),
    ('Temperature', 'phys', {
        'Reservoir Depth': 4,
        'Gradient 1': 60,                  # ~260 C bottom-hole
    }),
    ('Flow /\nlaterals', 'phys', {
        'Production Flow Rate per Well': 80,
        'Productivity Index': 15,
        'Injectivity Index': 15,
    }),
    ('Monobore\n(wider bore)', 'phys', {
        'Production Well Diameter': 8.5,
        'Injection Well Diameter': 8.5,
    }),
    ('Subsurface\n(reservoir eng.)', 'phys', {
        'Number of Fractures': 40,
        'Fracture Height': 1500,           # larger heat-exchange area resists drawdown
    }),
    ('Drilling ROP\n(tech)', 'cost', {
        'Well Drilling and Completion Capital Cost Adjustment Factor': 1.0,
    }),
    ('Turbine\neconomy of scale', 'cost', {
        'Capital Cost for Power Plant for Electricity Generation': 1200,  # $/kW (ASSUMPTION)
    }),
    ('Cost of capital\n(FOAK→NOAK)', 'cost', {
        'Discount Rate': 0.06,
        'Well Drilling and Completion Capital Cost Adjustment Factor': 0.8,  # NOAK learning-by-doing
    }),
]


def main():
    running = dict(today)
    hdr = f"{'step':26s} {'LCOE':>8s} {'net MW':>8s} {'wells':>6s} {'MW/well':>8s} {'pump MW':>8s}"
    print(hdr); print('-' * len(hdr))

    def show(tag, m, prev=None):
        d = '' if prev is None else f'  Δ={m["lcoe"]-prev:+7.1f}'
        print(f"{tag:26s} {m['lcoe']:7.1f}$ {m['mw']:7.1f} {m['nprod']:6.0f} "
              f"{m['mw_per_well']:7.2f} {m['pump_mw']:7.2f}{d}")

    metrics = [run_case(running)]
    labels = ['Today']
    cats = ['anchor']
    show('Today (FOAK)', metrics[0])

    for name, cat, delta in levers:
        running.update(delta)
        m = run_case(running)
        show('+ ' + name.replace('\n', ' '), m, metrics[-1]['lcoe'])
        metrics.append(m)
        labels.append(name)
        cats.append(cat)

    lcoes = [m['lcoe'] for m in metrics]
    labels.append('Stacked\ntarget')
    cats.append('anchor')
    lcoes.append(lcoes[-1])
    metrics.append(metrics[-1])

    # ---- write csv ----
    import csv
    with open(HERE / 'lcoe_waterfall.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['step', 'category', 'LCOE_USD_per_MWh', 'net_MW', 'production_wells',
                    'net_MW_per_well', 'flow_per_well_kg_s', 'pump_MW', 'total_CAPEX_MUSD'])
        cols = ['Today'] + [n.replace('\n', ' ') for n, _, _ in levers]
        catcol = ['anchor'] + [c for _, c, _ in levers]
        for name, cat, m in zip(cols, catcol, metrics):
            w.writerow([name, cat, round(m['lcoe'], 1), round(m['mw'], 1), int(m['nprod']),
                        round(m['mw_per_well'], 2), round(m['flow_per_well'], 0),
                        round(m['pump_mw'], 2), round(m['capex'], 1)])

    plot_waterfall(labels, lcoes, cats, metrics)


def plot_waterfall(labels, lcoes, cats, metrics):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    colors = {'anchor': '#34495e', 'phys': '#2e86c1', 'cost': '#e67e22'}
    n = len(labels)
    fig, (ax, tax) = plt.subplots(
        2, 1, figsize=(16, 8.6), gridspec_kw={'height_ratios': [4, 1.25]})

    start = lcoes[0]
    target = lcoes[-2]

    for i in range(n):
        if i == 0 or i == n - 1:
            val = lcoes[i] if i == 0 else target
            ax.bar(i, val, width=0.62, color=colors['anchor'], zorder=3)
            ax.text(i, val + 4, f'${val:.0f}', ha='center', va='bottom',
                    fontweight='bold', fontsize=11)
        else:
            top = lcoes[i - 1]
            bottom = lcoes[i]
            ax.bar(i, top - bottom, bottom=bottom, width=0.62,
                   color=colors[cats[i]], zorder=3)
            ax.text(i, top + 3, f'{bottom - top:+.0f}', ha='center', va='bottom',
                    color='#c0392b', fontsize=9, fontweight='bold')
            ax.plot([i - 1 + 0.31, i + 0.31], [top, top], color='gray',
                    lw=0.8, ls='--', zorder=2)
        if 0 < i < n - 1:
            ax.plot([i + 0.31, i + 1 - 0.31], [lcoes[i], lcoes[i]],
                    color='gray', lw=0.8, ls='--', zorder=2)
        ax.text(i, 2, f"{metrics[i]['mw']:.0f} MW", ha='center', va='bottom',
                fontsize=7.5, color='white' if i in (0, n - 1) else '#555',
                fontweight='bold', zorder=4)

    ax.set_xticks(range(n))
    ax.set_xticklabels(labels, fontsize=8.5)
    ax.set_ylabel('LCOE  ($/MWh)', fontsize=11)
    ax.set_title('Next-Gen Geothermal LCOE Waterfall — Innovations Concatenate (comprehensive)\n'
                 rf'(GEOPHIRES-X; \${start:.0f}/MWh $\rightarrow$ \${target:.0f}/MWh, subcritical ORC throughout)',
                 fontsize=13, fontweight='bold')
    ax.set_ylim(0, start * 1.12)
    ax.grid(axis='y', alpha=0.3)
    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)

    # legend for categories
    from matplotlib.patches import Patch
    ax.legend(handles=[
        Patch(color=colors['phys'], label='Modeled physics (GEOPHIRES output)'),
        Patch(color=colors['cost'], label='Cost / finance (input assumption)'),
    ], loc='upper right', fontsize=9, frameon=False)

    # ---- power table ----
    tax.axis('off')
    row_labels = ['Net power (MW)', 'Production wells', 'Net MW / well',
                  'Flow / well (kg/s)', 'Pumping (MW)']
    cell_text = [
        [f"{m['mw']:.1f}" for m in metrics],
        [f"{m['nprod']:.0f}" for m in metrics],
        [f"{m['mw_per_well']:.2f}" for m in metrics],
        [f"{m['flow_per_well']:.0f}" for m in metrics],
        [f"{m['pump_mw']:.2f}" for m in metrics],
    ]
    col_labels = [lbl.replace('\n', ' ') for lbl in labels]
    tbl = tax.table(cellText=cell_text, rowLabels=row_labels, colLabels=col_labels,
                    cellLoc='center', rowLoc='right', loc='center')
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(7)
    tbl.scale(1, 1.35)
    for (r, c), cell in tbl.get_celld().items():
        if r == 0:
            cell.set_text_props(fontweight='bold')
        if c == -1:
            cell.set_text_props(fontweight='bold', ha='right')
        cell.set_edgecolor('#dddddd')

    fig.text(0.01, 0.005,
             'Notes: Flow & Subsurface are coupled — high flow only pays off with a drawdown-resistant reservoir. '
             'Laterals shown via per-well flow + connectivity (explicit multilateral geometry needs a closed-loop model). '
             'Turbine $/kW and drilling-cost factors are input assumptions, not GEOPHIRES outputs.',
             fontsize=6.5, color='#666', style='italic')

    fig.tight_layout(rect=(0, 0.02, 1, 1))
    out = HERE / 'lcoe_waterfall.png'
    fig.savefig(out, dpi=150)
    print(f'\nSaved chart -> {out}')


if __name__ == '__main__':
    main()
