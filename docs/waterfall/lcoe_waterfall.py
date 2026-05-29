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
    3. Flow            -- bigger wells flow more kg/s -> more MW per well.
    4. Temperature     -- deeper/hotter resource -> higher conversion efficiency.
    5. Turbine/efficiency -- supercritical ORC + higher utilization.

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


def lcoe_usd_per_mwh(params: dict) -> tuple:
    """Run GEOPHIRES and return (LCOE $/MWh, net MW, total CAPEX MUSD)."""
    result = client.get_geophires_result(
        GeophiresInputParameters(params=params, from_file_path=BASE_FILE)
    ).result
    summary = result['SUMMARY OF RESULTS']
    lcoe_cents_kwh = summary['Electricity breakeven price']['value']
    mw = summary['Average Net Electricity Production']['value']
    capex = result['CAPITAL COSTS (M$)']['Total capital costs']['value']
    return lcoe_cents_kwh * 10.0, mw, capex  # 1 cent/kWh = 10 $/MWh


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
    ('Conversion\nefficiency', {
        'Power Plant Type': 2,             # subcritical -> supercritical ORC
        'Utilization Factor': 0.90,
        'Circulation Pump Efficiency': 0.85,
    }),
]


def main():
    running = dict(today)
    lcoe0, mw0, cap0 = lcoe_usd_per_mwh(running)
    print(f"{'Today (FOAK sub-scale)':32s} LCOE={lcoe0:7.1f} $/MWh  ({mw0:5.1f} MW, CAPEX {cap0:6.1f} M$)")

    labels = ['Today']
    lcoes = [lcoe0]
    rows = [('Today', lcoe0, mw0, cap0)]

    for name, delta in levers:
        running.update(delta)
        lcoe, mw, cap = lcoe_usd_per_mwh(running)
        flat = name.replace('\n', ' ')
        print(f"+ {flat:30s} LCOE={lcoe:7.1f} $/MWh  ({mw:5.1f} MW, CAPEX {cap:6.1f} M$)  Δ={lcoe-lcoes[-1]:+6.1f}")
        labels.append(name)
        lcoes.append(lcoe)
        rows.append((flat, lcoe, mw, cap))

    labels.append('Stacked\ntarget')
    lcoes.append(lcoes[-1])

    # ---- write csv ----
    import csv
    with open(HERE / 'lcoe_waterfall.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['step', 'LCOE_USD_per_MWh', 'net_MW', 'total_CAPEX_MUSD'])
        for r in rows:
            w.writerow([r[0], round(r[1], 1), round(r[2], 1), round(r[3], 1)])

    plot_waterfall(labels, lcoes)


def plot_waterfall(labels, lcoes):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    n = len(labels)
    fig, ax = plt.subplots(figsize=(12, 6.5))

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
    fig.tight_layout()
    out = HERE / 'lcoe_waterfall.png'
    fig.savefig(out, dpi=150)
    print(f'\nSaved chart -> {out}')


if __name__ == '__main__':
    main()
