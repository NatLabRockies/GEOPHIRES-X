"""
LCOE waterfall -- ALTERNATIVE allocation: cost levers first, then heat levers.

A second view of the same FOAK->NOAK story as `lcoe_waterfall.py`, with the
*same* start (~$192/MWh) and *same* endpoint (~$52/MWh), but the levers are
re-allocated and re-ordered to separate the two kinds of improvement:

  COST-DRIVEN (shrink $ per well -- the LCOE numerator)
     1. Scale            -- more wells amortize fixed exploration/surface cost
                            (this version changes ONLY well count, no cost factor)
     2. Drilling learning -- the ENTIRE drilling-cost reduction (factor 1.7 -> 1.2,
                            campaign + ROP + NOAK learning) consolidated in ONE bar

  HEAT-DRIVEN (grow energy per well -- the LCOE denominator)
     3. Temperature       -- hotter resource -> higher conversion efficiency
     4. Monobore+laterals -> flow -> turbine -- more flow -> more power per well
     5. Subsurface        -- larger heat-exchange area sustains output over life

Because all the drilling learning is applied up front (bar 2), the three
heat-driven levers no longer carry the expensive FOAK drilling cost. Bars are
COLOURED by driver so the eye can see how much of the total reduction is
heat-driven (it is most of it): "heat per well beats cost per well".

This file is intentionally separate from `lcoe_waterfall.py` so the two
allocations can be compared side by side. Outputs:
  lcoe_waterfall_cost_vs_heat.png  and  lcoe_waterfall_cost_vs_heat.csv
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

COST = '#4f81bd'   # cost-driven  (cheaper $ per well)
HEAT = '#e8743b'   # heat-driven  (more energy per well)
ANCHOR = '#34495e'
MOONSHOT = 45.0


def run_case(params: dict) -> dict:
    result = client.get_geophires_result(
        GeophiresInputParameters(params=params, from_file_path=BASE_FILE)
    ).result
    s = result['SUMMARY OF RESULTS']
    surf = result['SURFACE EQUIPMENT SIMULATION RESULTS']
    mw = s['Average Net Electricity Production']['value']
    nprod = s['Number of production wells']['value']
    return {
        'lcoe': s['Electricity breakeven price']['value'] * 10.0,
        'mw': mw, 'nprod': nprod, 'mw_per_well': mw / nprod,
        'flow_per_well': s['Flowrate per production well']['value'],
        'capex': result['CAPITAL COSTS (M$)']['Total capital costs']['value'],
    }


# Same conservative FOAK "today" as lcoe_waterfall.py (FCR 5.8% throughout).
today = {
    'Reservoir Model': 1, 'Reservoir Depth': 3, 'Gradient 1': 50,
    'Number of Production Wells': 1, 'Number of Injection Wells': 1,
    'Production Well Diameter': 6.625, 'Injection Well Diameter': 6.625,
    'Production Flow Rate per Well': 40, 'Productivity Index': 5, 'Injectivity Index': 5,
    'Number of Fractures': 20, 'Fracture Height': 900,
    'Power Plant Type': 1, 'Utilization Factor': 0.85, 'Well Drilling Cost Correlation': 1,
    'Well Drilling and Completion Capital Cost Adjustment Factor': 1.7,
    'Fixed Charge Rate': 0.058, 'Print Output to Console': 0,
}

# (label, driver, short-header, cumulative deltas). Cost levers first, heat later.
levers = [
    ('Scale\n(more wells)', 'cost', 'Scale', {
        'Number of Production Wells': 4, 'Number of Injection Wells': 4,
        # NOTE: no drilling cost-factor change here -- pure fixed-cost amortization
    }),
    ('Drilling learning\n(campaign+ROP+NOAK)', 'cost', 'Drilling', {
        # ALL drilling-cost learning in one bar: 1.7 -> 1.2 (~29%), still conservative
        # vs Fervo's demonstrated ~50% campaign learning, and still 20% above the
        # generic well-cost correlation.
        'Well Drilling and Completion Capital Cost Adjustment Factor': 1.2,
    }),
    ('Temperature', 'heat', 'Temp', {
        'Reservoir Depth': 4, 'Gradient 1': 60,
    }),
    ('Monobore + laterals\n→ flow → turbine', 'heat', 'Monobore+\nlaterals', {
        'Production Well Diameter': 8.5, 'Injection Well Diameter': 8.5,
        'Production Flow Rate per Well': 80, 'Productivity Index': 10, 'Injectivity Index': 10,
        'Capital Cost for Power Plant for Electricity Generation': 2480,  # = GEOPHIRES correlation
    }),
    ('Subsurface\n(lower drawdown)', 'heat', 'Subsurface', {
        'Number of Fractures': 60, 'Fracture Height': 1000,
    }),
]


def main():
    running = dict(today)
    metrics = [run_case(running)]
    drivers = ['anchor']
    labels = ['Today']
    print(f"{'step':34s} {'LCOE':>8s} {'net MW':>8s} {'driver':>8s}  Δ")
    print(f"Today (FOAK){'':22s} {metrics[0]['lcoe']:7.1f}$ {metrics[0]['mw']:7.1f}")
    for label, driver, _short, delta in levers:
        running.update(delta)
        m = run_case(running)
        print(f"+ {label.replace(chr(10), ' '):32s} {m['lcoe']:7.1f}$ {m['mw']:7.1f} "
              f"{driver:>8s}  Δ={m['lcoe'] - metrics[-1]['lcoe']:+6.1f}")
        metrics.append(m); drivers.append(driver); labels.append(label)

    # cost vs heat totals (the headline of this view)
    cost_drop = heat_drop = 0.0
    for i in range(1, len(metrics)):
        d = metrics[i - 1]['lcoe'] - metrics[i]['lcoe']
        if drivers[i] == 'cost':
            cost_drop += d
        else:
            heat_drop += d
    print(f"\nCost-driven levers:  -${cost_drop:.0f}/MWh")
    print(f"Heat-driven levers:  -${heat_drop:.0f}/MWh   "
          f"({100 * heat_drop / (cost_drop + heat_drop):.0f}% of the total reduction)")

    # endpoint anchor
    labels.append('Central case\n(~P50)'); drivers.append('anchor')
    metrics.append(metrics[-1])

    import csv
    with open(HERE / 'lcoe_waterfall_cost_vs_heat.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['step', 'driver', 'LCOE_USD_per_MWh', 'net_MW', 'production_wells',
                    'net_MW_per_well', 'total_CAPEX_MUSD'])
        names = ['Today'] + [lv[0].replace('\n', ' ') for lv in levers]
        for name, drv, m in zip(names, drivers, metrics):
            w.writerow([name, drv, round(m['lcoe'], 1), round(m['mw'], 1), int(m['nprod']),
                        round(m['mw_per_well'], 2), round(m['capex'], 1)])

    plot(labels, drivers, metrics, cost_drop, heat_drop)


def plot(labels, drivers, metrics, cost_drop, heat_drop):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    lcoes = [m['lcoe'] for m in metrics]
    n = len(labels)
    start, target = lcoes[0], lcoes[-2]
    fig, (ax, tax) = plt.subplots(2, 1, figsize=(13, 8),
                                  gridspec_kw={'height_ratios': [4, 1]})

    for i in range(n):
        if i == 0 or i == n - 1:
            val = lcoes[i] if i == 0 else target
            ax.bar(i, val, width=0.6, color=ANCHOR, zorder=3)
            ax.text(i, val + 2, f'${val:.0f}', ha='center', va='bottom',
                    fontweight='bold', fontsize=12)
        else:
            top, bottom = lcoes[i - 1], lcoes[i]
            ax.bar(i, top - bottom, bottom=bottom, width=0.6,
                   color=COST if drivers[i] == 'cost' else HEAT, zorder=3)
            ax.text(i, top + 1.5, f'{bottom - top:+.0f}', ha='center', va='bottom',
                    color='#c0392b', fontsize=11, fontweight='bold')
            ax.plot([i - 1 + 0.3, i + 0.3], [top, top], color='gray', lw=0.8, ls='--', zorder=2)
        if 0 < i < n - 1:
            ax.plot([i + 0.3, i + 1 - 0.3], [lcoes[i], lcoes[i]], color='gray', lw=0.8, ls='--', zorder=2)
        ax.text(i, 1.5, f"{metrics[i]['mw']:.0f} MW", ha='center', va='bottom', fontsize=8,
                color='white' if i in (0, n - 1) else '#555', fontweight='bold', zorder=4)

    ax.set_xticks(range(n)); ax.set_xticklabels(labels, fontsize=9.5)
    ax.set_ylabel('LCOE  ($/MWh)', fontsize=12)
    ax.set_title('Next-Gen Geothermal LCOE Waterfall — Cost levers first, then Heat levers\n'
                 rf'(GEOPHIRES-X; \${start:.0f}/MWh $\rightarrow$ \${target:.0f}/MWh; same start & endpoint as the main waterfall)',
                 fontsize=14, fontweight='bold')
    ax.set_ylim(0, start * 1.12)
    ax.axhline(MOONSHOT, color='#2e7d32', lw=1.2, ls='--', alpha=0.8)
    ax.text(n - 1, MOONSHOT, '  $45 moonshot (favorable case)', color='#2e7d32',
            fontsize=8.5, va='center', ha='right')
    ax.grid(axis='y', alpha=0.3)
    for sp in ['top', 'right']:
        ax.spines[sp].set_visible(False)
    ax.legend(handles=[Patch(color=COST, label=f'Cost-driven — cheaper $/well  (−${cost_drop:.0f}/MWh)'),
                       Patch(color=HEAT, label=f'Heat-driven — more energy/well  (−${heat_drop:.0f}/MWh, '
                                               f'{100 * heat_drop / (cost_drop + heat_drop):.0f}%)')],
              loc='upper right', fontsize=9, framealpha=0.95)

    tax.axis('off')
    row_labels = ['Net power (MW)', 'Production wells', 'Net MW / well', 'Flow / well (kg/s)']
    cell_text = [
        [f"{m['mw']:.1f}" for m in metrics],
        [f"{m['nprod']:.0f}" for m in metrics],
        [f"{m['mw_per_well']:.2f}" for m in metrics],
        [f"{m['flow_per_well']:.0f}" for m in metrics],
    ]
    col_labels = ['Today'] + [lv[2] for lv in levers] + ['Central\n(~P50)']
    tbl = tax.table(cellText=cell_text, rowLabels=row_labels, colLabels=col_labels,
                    cellLoc='center', rowLoc='right', loc='center')
    tbl.auto_set_font_size(False); tbl.set_fontsize(8); tbl.scale(1, 1.4)
    for (r, c), cell in tbl.get_celld().items():
        if r == 0:
            cell.set_text_props(fontweight='bold')
        if c == -1:
            cell.set_text_props(fontweight='bold', ha='right')
        cell.set_edgecolor('#dddddd')

    fig.text(0.01, 0.005,
             'Alternative allocation of the SAME run as lcoe_waterfall.py (identical start & endpoint). All drilling learning (factor 1.7→1.2) is in ONE cost bar; '
             'Scale changes only well count. Colour = driver. Heat-driven levers (temperature, flow, subsurface) deliver most of the reduction — "heat per well beats cost per well".',
             fontsize=6.5, color='#666', style='italic')
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    out = HERE / 'lcoe_waterfall_cost_vs_heat.png'
    fig.savefig(out, dpi=150)
    print(f'\nSaved chart -> {out}')


if __name__ == '__main__':
    main()
