"""
LCOE cost-reduction waterfall for next-gen (EGS) geothermal.

Reproduces the "innovations concatenate into a step-change in cost" story
(slide 45c) using GEOPHIRES-X. A conservative, sub-scale, first-of-a-kind
(FOAK) EGS doublet is taken as "today". Five physics-backed levers are then
applied *cumulatively* and the levelized cost of electricity (LCOE) is read
after each step. The descending steps form the waterfall.

Levers (in order):
    1. Scale          -- "drill the field, not the well": more wells amortize
                         fixed (exploration/surface) cost + cross-well learning
                         lowers per-well drilling cost.
    2. Drilling/monobore -- larger-diameter monobore + conventional-rig
                         efficiency lowers $/well.
    3. Temperature     -- deeper/hotter resource. Conversion efficiency is
                          physically coupled to temperature, so this lever
                          captures the efficiency gain too (plant held at
                          subcritical ORC throughout).
    4. Flow / turbine scale -- bigger bore + better connectivity flow more kg/s,
                          and the larger throughput unlocks a bigger, cheaper
                          turbine (lower plant $/kW).

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
    mw = summary['Average Net Electricity Production']['value']
    nprod = summary['Number of production wells']['value']
    return {
        'lcoe': summary['Electricity breakeven price']['value'] * 10.0,  # 1 cent/kWh = 10 $/MWh
        'mw': mw,
        'nprod': nprod,
        'mw_per_well': mw / nprod,
        'flow_per_well': summary['Flowrate per production well']['value'],
        'capex': result['CAPITAL COSTS (M$)']['Total capital costs']['value'],
    }


# ----------------------------------------------------------------------------
# "Today": conservative, sub-scale, FOAK EGS doublet (1 prod + 1 inj well),
# narrow wellbore, modest flow, cool resource, subcritical ORC, FOAK cost premium.
# ----------------------------------------------------------------------------
today = {
    'Reservoir Model': 1,                  # multiple parallel fractures (EGS)
    'Reservoir Depth': 3,                  # km
    'Gradient 1': 50,                      # degC/km  -> ~170 C resource
    'Number of Production Wells': 1,
    'Number of Injection Wells': 1,
    'Production Well Diameter': 6.625,     # inch (narrow / telescoped)
    'Injection Well Diameter': 6.625,      # inch
    'Production Flow Rate per Well': 40,   # kg/s (low)
    'Power Plant Type': 1,                 # subcritical ORC (lower efficiency)
    'Utilization Factor': 0.85,
    'Well Drilling Cost Correlation': 1,
    'Well Drilling and Completion Capital Cost Adjustment Factor': 1.4,  # FOAK premium
    'Print Output to Console': 0,          # keep our console clean
}

# Cumulative lever deltas applied on top of the running case.
# NOTE: order matters in a cumulative waterfall. Temperature is pulled before
# Flow so that the extra mass flow lands on a hotter resource (more net MW,
# not just more parasitic pumping).
levers = [
    ('Scale\n(drill the field)', {
        'Number of Production Wells': 6,
        'Number of Injection Wells': 6,
        # cross-well learning brings the FOAK premium down toward NOAK
        'Well Drilling and Completion Capital Cost Adjustment Factor': 1.15,
    }),
    ('Drilling /\nmonobore', {
        'Production Well Diameter': 8.5,
        'Injection Well Diameter': 8.5,
        'Well Drilling and Completion Capital Cost Adjustment Factor': 0.85,
    }),
    ('Temperature', {
        'Reservoir Depth': 4,
        'Gradient 1': 60,                  # ~250 C resource
    }),
    ('Flow /\nturbine scale', {
        # bigger bore + better-stimulated reservoir delivers more kg/s without
        # the parasitic-pumping penalty (raise reservoir deliverability too) ...
        'Production Flow Rate per Well': 80,
        'Productivity Index': 15,
        'Injectivity Index': 15,
        # ... and the larger throughput unlocks a bigger, cheaper turbine:
        # move down the turbine size curve from the default correlation
        # (~$4,000/kW gross here) to a large-unit specific cost.
        'Capital Cost for Power Plant for Electricity Generation': 1200,  # $/kW
    }),
    # NOTE: no separate "conversion efficiency" lever. Conversion efficiency is
    # physically coupled to resource temperature and is already captured by the
    # Temperature lever (GEOPHIRES derives plant efficiency from temperature for
    # the given plant type). The plant is held at subcritical ORC throughout.
]


def main():
    running = dict(today)
    hdr = f"{'step':24s} {'LCOE':>8s} {'net MW':>8s} {'wells':>6s} {'MW/well':>8s} {'flow/well':>10s}"
    print(hdr); print('-' * len(hdr))

    def show(tag, m, prev_lcoe=None):
        d = '' if prev_lcoe is None else f'  Δ={m["lcoe"]-prev_lcoe:+6.1f}'
        print(f"{tag:24s} {m['lcoe']:7.1f}$ {m['mw']:7.1f} {m['nprod']:6.0f} "
              f"{m['mw_per_well']:7.2f} {m['flow_per_well']:8.0f} kg/s{d}")

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
    labels.append('Stacked\ntarget')
    lcoes.append(lcoes[-1])
    metrics.append(metrics[-1])  # target column repeats final config

    # ---- write csv ----
    import csv
    with open(HERE / 'lcoe_waterfall.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['step', 'LCOE_USD_per_MWh', 'net_MW', 'production_wells',
                    'net_MW_per_well', 'flow_per_well_kg_s', 'total_CAPEX_MUSD'])
        cols = ['Today'] + [n.replace('\n', ' ') for n, _ in levers]
        for name, m in zip(cols, metrics):
            w.writerow([name, round(m['lcoe'], 1), round(m['mw'], 1), int(m['nprod']),
                        round(m['mw_per_well'], 2), round(m['flow_per_well'], 0),
                        round(m['capex'], 1)])

    plot_waterfall(labels, lcoes, metrics)


def plot_waterfall(labels, lcoes, metrics):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    n = len(labels)
    fig, (ax, tax) = plt.subplots(
        2, 1, figsize=(12, 7.8), gridspec_kw={'height_ratios': [4, 1]})

    start = lcoes[0]
    target = lcoes[-2]  # last computed lever value

    # bar bottoms/heights for the descending steps
    for i in range(n):
        if i == 0 or i == n - 1:
            # anchor bars (Today, Target): full-height columns
            val = lcoes[i] if i == 0 else target
            ax.bar(i, val, width=0.6, color='#34495e', zorder=3)
            ax.text(i, val + 3, f'${val:.0f}', ha='center', va='bottom',
                    fontweight='bold', fontsize=11)
        else:
            top = lcoes[i - 1]
            bottom = lcoes[i]
            ax.bar(i, top - bottom, bottom=bottom, width=0.6,
                   color='#2e86c1', zorder=3)
            drop = bottom - top
            ax.text(i, top + 2, f'{drop:+.0f}', ha='center', va='bottom',
                    color='#c0392b', fontsize=10, fontweight='bold')
            # connector line
            ax.plot([i - 1 + 0.3, i + 0.3], [top, top], color='gray',
                    lw=0.8, ls='--', zorder=2)
        if 0 < i < n - 1:
            ax.plot([i + 0.3, i + 1 - 0.3], [lcoes[i], lcoes[i]],
                    color='gray', lw=0.8, ls='--', zorder=2)
        # net power tag at the foot of every column
        ax.text(i, 1.5, f"{metrics[i]['mw']:.0f} MW", ha='center', va='bottom',
                fontsize=8, color='white' if i in (0, n - 1) else '#555',
                fontweight='bold', zorder=4)

    ax.set_xticks(range(n))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel('LCOE  ($/MWh)', fontsize=11)
    ax.set_title('Next-Gen Geothermal LCOE Waterfall — Innovations Concatenate\n'
                 rf'(GEOPHIRES-X; \${start:.0f}/MWh $\rightarrow$ \${target:.0f}/MWh)',
                 fontsize=13, fontweight='bold')
    ax.set_ylim(0, start * 1.15)
    ax.grid(axis='y', alpha=0.3)
    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)

    # ---- power table beneath the waterfall ----
    tax.axis('off')
    row_labels = ['Net power (MW)', 'Production wells', 'Net MW / well', 'Flow / well (kg/s)']
    cell_text = [
        [f"{m['mw']:.1f}" for m in metrics],
        [f"{m['nprod']:.0f}" for m in metrics],
        [f"{m['mw_per_well']:.2f}" for m in metrics],
        [f"{m['flow_per_well']:.0f}" for m in metrics],
    ]
    col_labels = [lbl.replace('\n', ' ') for lbl in labels]
    tbl = tax.table(cellText=cell_text, rowLabels=row_labels, colLabels=col_labels,
                    cellLoc='center', rowLoc='right', loc='center')
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    tbl.scale(1, 1.4)
    for (r, c), cell in tbl.get_celld().items():
        if r == 0:                       # header row
            cell.set_text_props(fontweight='bold')
        if c == -1:                      # row labels
            cell.set_text_props(fontweight='bold', ha='right')
        cell.set_edgecolor('#dddddd')

    fig.tight_layout()
    out = HERE / 'lcoe_waterfall.png'
    fig.savefig(out, dpi=150)
    print(f'\nSaved chart -> {out}')


if __name__ == '__main__':
    main()
