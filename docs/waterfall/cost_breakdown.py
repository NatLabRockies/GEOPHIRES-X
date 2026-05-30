"""
Detailed CAPEX / O&M cost breakdown for the FOAK and NOAK cases, exported to Excel.

Pulls GEOPHIRES-X's line-item capital and operating costs for:
  * FOAK  -- the waterfall "today" case (~1.6 MW net)
  * NOAK  -- the waterfall central endpoint (~52 MW net)

Because the runs use the fixed-charge-rate (FCR) economic model, the LCOE
decomposes *exactly* into each line item's contribution:
    capex item -> FCR * item / annual_MWh        ($/MWh)
    O&M item   ->       item / annual_MWh         ($/MWh)
and those contributions sum to the reported breakeven LCOE (checked at runtime).

Output: cost_breakdown.xlsx (+ .csv), sheets: overview, capital_costs, om_costs.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from geophires_x_client import GeophiresXClient
from geophires_x_client.geophires_input_parameters import GeophiresInputParameters

HERE = Path(__file__).parent
EXAMPLE = str(HERE.parent.parent / 'tests' / 'examples' / 'example1.txt')

_BASE = {
    'Reservoir Model': 1, 'Power Plant Type': 1, 'Utilization Factor': 0.85,
    'Well Drilling Cost Correlation': 1, 'Fixed Charge Rate': 0.058,
    'Print Output to Console': 0,
}
FOAK = {**_BASE, 'Reservoir Depth': 3, 'Gradient 1': 50,
        'Number of Production Wells': 1, 'Number of Injection Wells': 1,
        'Production Well Diameter': 6.625, 'Injection Well Diameter': 6.625,
        'Production Flow Rate per Well': 40, 'Productivity Index': 5, 'Injectivity Index': 5,
        'Number of Fractures': 20, 'Fracture Height': 900,
        'Well Drilling and Completion Capital Cost Adjustment Factor': 1.7}
NOAK = {**_BASE, 'Reservoir Depth': 4, 'Gradient 1': 60,
        'Number of Production Wells': 4, 'Number of Injection Wells': 4,
        'Production Well Diameter': 8.5, 'Injection Well Diameter': 8.5,
        'Production Flow Rate per Well': 80, 'Productivity Index': 10, 'Injectivity Index': 10,
        'Number of Fractures': 60, 'Fracture Height': 1000,
        'Capital Cost for Power Plant for Electricity Generation': 2480,
        'Well Drilling and Completion Capital Cost Adjustment Factor': 1.2}

UTIL = 0.85
HOURS = 8760


def _run(params: dict) -> dict:
    return GeophiresXClient().get_geophires_result(
        GeophiresInputParameters(params=params, from_file_path=EXAMPLE)).result


def _items(section: dict) -> dict:
    """Non-null {name: value} from a cost section (drop unit-less / null entries)."""
    out = {}
    for k, v in section.items():
        if isinstance(v, dict) and v.get('value') is not None:
            out[k] = float(v['value'])
    return out


def _case(params: dict) -> dict:
    r = _run(params)
    s = r['SUMMARY OF RESULTS']
    net_mw = s['Average Net Electricity Production']['value']
    n_wells = (s['Number of production wells']['value']
               + s['Number of injection wells']['value'])
    lcoe = s['Electricity breakeven price']['value'] * 10.0  # cents/kWh -> $/MWh
    annual_mwh = net_mw * HOURS * UTIL
    return {
        'net_mw': net_mw, 'n_wells': n_wells, 'lcoe': lcoe, 'annual_mwh': annual_mwh,
        'fcr': r['ECONOMIC PARAMETERS']['Fixed Charge Rate (FCR)']['value'] / 100.0,
        'capex': _items(r['CAPITAL COSTS (M$)']),
        'om': _items(r['OPERATING AND MAINTENANCE COSTS (M$/yr)']),
    }


# items that are sub-totals / not additive components (excluded from % and LCOE sums)
_CAPEX_SKIP = {'Drilling and completion costs per well', 'Total surface equipment costs',
               'Total capital costs', 'Annualized capital costs'}
_OM_SKIP = {'Total operating and maintenance costs'}
_CAPEX_TOTAL = 'Total capital costs'
_OM_TOTAL = 'Total operating and maintenance costs'


def _cost_table(foak: dict, noak: dict, kind: str) -> pd.DataFrame:
    key = 'capex' if kind == 'capex' else 'om'
    skip = _CAPEX_SKIP if kind == 'capex' else _OM_SKIP
    total_key = _CAPEX_TOTAL if kind == 'capex' else _OM_TOTAL
    names = list(dict.fromkeys(list(foak[key]) + list(noak[key])))
    components = [n for n in names if n not in skip]
    rows = []
    for n in components + [total_key]:
        row = {'line_item': n, 'unit': 'MUSD' if kind == 'capex' else 'MUSD/yr'}
        for tag, c in [('FOAK', foak), ('NOAK', noak)]:
            val = c[key].get(n, 0.0)
            tot = c[key].get(total_key, float('nan'))
            # LCOE contribution: capex annualized by FCR; O&M already annual
            annual = (c['fcr'] * val if kind == 'capex' else val) * 1e6
            row[f'{tag}_MUSD'] = round(val, 2)
            row[f'{tag}_pct_of_total'] = round(100 * val / tot, 1) if tot else None
            row[f'{tag}_LCOE_$/MWh'] = round(annual / c['annual_mwh'], 2)
        rows.append(row)
    return pd.DataFrame(rows)


def _overview(foak: dict, noak: dict) -> pd.DataFrame:
    def col(c):
        capex = c['capex'].get(_CAPEX_TOTAL, float('nan'))
        om = c['om'].get(_OM_TOTAL, float('nan'))
        return [
            round(c['net_mw'], 2), int(c['n_wells']), round(c['fcr'] * 100, 1), UTIL,
            round(capex, 2), round(capex * 1e6 / (c['net_mw'] * 1000), 0),
            round(om, 2), round(c['lcoe'], 2),
            # exact LCOE reconciliation: FCR*capex + O&M, over annual MWh
            round((c['fcr'] * capex + om) * 1e6 / c['annual_mwh'], 2),
        ]
    rows = ['Net electricity (MW)', 'Number of wells', 'Fixed charge rate (%)',
            'Utilization factor', 'Total CAPEX (MUSD)', 'CAPEX ($/kW-net)',
            'Annual O&M (MUSD/yr)', 'Breakeven LCOE ($/MWh, GEOPHIRES)',
            'LCOE check = (FCR·CAPEX+O&M)/MWh ($/MWh)']
    return pd.DataFrame({'metric': rows, 'FOAK (~1.6 MW)': col(foak), 'NOAK (~52 MW)': col(noak)})


def main():
    foak, noak = _case(FOAK), _case(NOAK)
    overview = _overview(foak, noak)
    capex = _cost_table(foak, noak, 'capex')
    om = _cost_table(foak, noak, 'om')

    print(overview.to_string(index=False))
    print('\nCAPITAL COSTS:\n', capex.to_string(index=False))
    print('\nO&M COSTS:\n', om.to_string(index=False))

    csv = HERE / 'cost_breakdown.csv'
    with open(csv, 'w') as f:
        f.write('# OVERVIEW\n'); overview.to_csv(f, index=False)
        f.write('\n# CAPITAL COSTS\n'); capex.to_csv(f, index=False)
        f.write('\n# OPERATING & MAINTENANCE COSTS\n'); om.to_csv(f, index=False)
    xlsx = HERE / 'cost_breakdown.xlsx'
    try:
        with pd.ExcelWriter(xlsx, engine='openpyxl') as w:
            overview.to_excel(w, sheet_name='overview', index=False)
            capex.to_excel(w, sheet_name='capital_costs', index=False)
            om.to_excel(w, sheet_name='om_costs', index=False)
        print(f'\nSaved {xlsx} (+ .csv)')
    except ImportError:
        print(f'\nSaved {csv} (install openpyxl for the .xlsx: pip install openpyxl)')


if __name__ == '__main__':
    main()
