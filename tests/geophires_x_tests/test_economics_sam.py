from __future__ import annotations

import logging
import math
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import numpy_financial as npf
import pandas as pd

from geophires_x.Parameter import listParameter

from base_test_case import BaseTestCase

# ruff: noqa: I001  # Successful module initialization is dependent on this specific import order.
from geophires_x.Model import Model

# noinspection PyProtectedMember
from geophires_x.EconomicsSam import (
    calculate_sam_economics,
    get_sam_cash_flow_profile_tabulated_output,
    _ppa_pricing_model,
    _get_fed_and_state_tax_rates,
    SamEconomicsCalculations,
    _get_royalty_rate_schedule,
    _validate_construction_capex_schedule,
    _calculate_nominal_discount_rate_from_real_and_inflation_pct,
)
from geophires_x.GeoPHIRESUtils import sig_figs, quantity, is_float

# noinspection PyProtectedMember
from geophires_x.EconomicsSamCashFlow import (
    _clean_profile,
    _is_category_row_label,
    _is_designator_row_label,
    _SAM_CASH_FLOW_NAN_STR,
)
from geophires_x.Units import convertible_unit
from geophires_x_client import GeophiresInputParameters, ImmutableGeophiresInputParameters
from geophires_x_client import GeophiresXClient
from geophires_x_client import GeophiresXResult

_log = logging.getLogger(__name__)


class EconomicsSamTestCase(BaseTestCase):

    def _egs_test_file_path(self) -> str:
        return self._get_test_file_path('generic-egs-case-2_sam-single-owner-ppa.txt')

    def _get_result(self, _params, file_path=None) -> GeophiresXResult:
        if file_path is None:
            file_path = self._egs_test_file_path()

        return GeophiresXClient().get_geophires_result(
            GeophiresInputParameters(
                from_file_path=file_path,
                params={'Economic Model': 5, **_params},
            )
        )

    def test_economic_model_single_owner_ppa_sam(self):
        def _lcoe(r: GeophiresXResult) -> float:
            return r.result['SUMMARY OF RESULTS']['Electricity breakeven price']['value']

        base_result = self._get_result({})
        base_lcoe = _lcoe(base_result)
        self.assertGreater(base_lcoe, 7)

        ir = base_result.result['ECONOMIC PARAMETERS']['Interest Rate']
        self.assertIsNone(ir)

        rdr = base_result.result['ECONOMIC PARAMETERS']['Real Discount Rate']
        self.assertEqual(rdr['value'], 7.0)
        self.assertEqual(rdr['unit'], '%')

    def test_drawdown(self):
        r = self._get_result(
            {'Plant Lifetime': 20, 'End-Use Option': 1}, file_path=self._get_test_file_path('../examples/example13.txt')
        )

        cash_flow = r.result['SAM CASH FLOW PROFILE']

        def get_row(name: str) -> list[float]:
            return EconomicsSamTestCase._get_cash_flow_row(cash_flow, name)

        elec_net_kWh = get_row('Electricity to grid net (kWh)')
        self.assertLess(elec_net_kWh[15], elec_net_kWh[14])
        self.assertGreater(elec_net_kWh[16], elec_net_kWh[15])
        self.assertLess(elec_net_kWh[20], elec_net_kWh[16])

    def test_plant_lifetime(self):
        r = self._get_result({'Plant Lifetime': 30})

        cash_flow = r.result['SAM CASH FLOW PROFILE']

        def get_row(name: str) -> list[float]:
            return EconomicsSamTestCase._get_cash_flow_row(cash_flow, name)

        self.assertEqual(32, len(cash_flow[0]))
        self.assertEqual('Year 30', cash_flow[0][-1])
        self.assertEqual(31, len(get_row('Electricity to grid net (kWh)')))

    def test_npv(self):
        def _npv(r: GeophiresXResult) -> float:
            return r.result['ECONOMIC PARAMETERS']['Project NPV']['value']

        _pricing_conversion_constant = 0.745
        inflation = 0.02
        rate_params = [
            {
                'Starting Electricity Sale Price': x / 100.0,
                # Escalation rate must remain constant percent
                'Electricity Escalation Rate Per Year': x * inflation / 100.0 / _pricing_conversion_constant,
            }
            for x in range(1, 20, 4)
        ]
        npvs = [_npv(self._get_result(rp)) for rp in rate_params]
        for i in range(len(npvs) - 1):
            self.assertLess(npvs[i], npvs[i + 1])

    def test_npv_and_irr_for_net_cash_flow(self):
        """
        Verification relevant to discussion at https://github.com/NREL/SAM/issues/2129#issuecomment-3687452532
        """

        def prnt(msg: str) -> None:
            if self._is_github_actions():
                _log.info(msg)
            else:
                print(msg)

        with open(self._get_test_file_path('test_npv_2-cash_flow.csv')) as f:
            df = pd.read_csv(f, index_col=0)

        # Extract the cash flow row
        cash_flows = df.loc['After-tax net cash flow ($)'].values.astype(float)

        # Extract the expected IRR and NPV rows
        cash_flow_irr = df.loc['After-tax cumulative IRR (%)'].values
        cash_flow_npv = df.loc['After-tax cumulative NPV ($)'].values.astype(float)

        # Discount rate
        real_discount_rate = 0.08
        discount_rate = _calculate_nominal_discount_rate_from_real_and_inflation_pct(real_discount_rate, 0.023) / 100.0

        prnt('Verifying NPV and IRR calculations for all years:\n')
        prnt('=' * 100)

        calculated_npvs = []
        irr_matches = []
        npv_matches = []

        # Verify for each year
        for i in range(len(cash_flows)):
            # Get cash flows up to current year (inclusive)
            cash_flows_to_date = cash_flows[: i + 1]

            # Calculate NPV
            calculated_npv = npf.npv(discount_rate, cash_flows_to_date)
            calculated_npvs.append(calculated_npv)
            cash_flow_npv_value = cash_flow_npv[i]
            npv_match = abs(calculated_npv - cash_flow_npv_value) < 1  # Allow for rounding
            npv_matches.append(npv_match)

            # Calculate IRR
            try:
                calculated_irr = npf.irr(cash_flows_to_date) * 100  # Convert to percentage
                cash_flow_irr_value = cash_flow_irr[i]

                if pd.isna(cash_flow_irr_value):
                    irr_match = pd.isna(calculated_irr) or calculated_irr != calculated_irr
                    irr_status = '✓ Both NaN'
                else:
                    expected_irr_float = float(cash_flow_irr_value)
                    irr_match = abs(calculated_irr - expected_irr_float) < 0.01  # Allow small difference
                    irr_status = (
                        '✓ Match' if irr_match else f'✗ Mismatch (diff: {calculated_irr - expected_irr_float:.4f})'
                    )
            except Exception:
                calculated_irr = float('nan')
                irr_match = pd.isna(cash_flow_irr[i])

                irr_status = '✓ Both NaN' if irr_match else '✗ Error calculating'

            irr_matches.append(irr_match)

            npv_status = '✓ Match' if npv_match else f'✗ Mismatch (diff: {calculated_npv - cash_flow_npv_value:,.0f})'

            year_label = df.columns[i]
            prnt(f'\n{year_label}:')
            prnt(f'  Cash flows used: {cash_flows_to_date.tolist()}')
            prnt(
                f'  NPV: Calculated (Expected)={calculated_npv:,.0f}, Value in Cash Flow={cash_flow_npv_value:,.0f} - {npv_status}'
            )
            prnt(
                f'  IRR: Calculated (Expected)={calculated_irr:.2f}%, Value in Cash Flow={cash_flow_irr[i]} - {irr_status}'
            )

        prnt('\n' + '=' * 100)
        # prnt("\nSummary:")
        prnt(f'Total years checked: {len(cash_flows)}')

        self.assertEqual(len(cash_flows), len(npv_matches))
        self.assertTrue(all(npv_matches))
        self.assertEqual(len(cash_flows), len(irr_matches))
        self.assertTrue(all(irr_matches))

    def test_electricity_generation_profile(self):
        r = self._get_result({})
        lifetime = r.result['ECONOMIC PARAMETERS']['Project lifetime']['value']

        cash_flow = r.result['SAM CASH FLOW PROFILE']

        def get_row(name: str) -> list[float]:
            return EconomicsSamTestCase._get_cash_flow_row(cash_flow, name)

        geophires_avg_net_gen_GWh = r.result['SURFACE EQUIPMENT SIMULATION RESULTS'][
            'Average Annual Net Electricity Generation'
        ]['value']

        sam_gen_profile = get_row('Electricity to grid net (kWh)')

        # Discrepancy is probably due to windowing and/or rounding effects,
        #  may merit further investigation when time permits.
        allowed_delta_percent = 5
        self.assertAlmostEqualWithinPercentage(
            geophires_avg_net_gen_GWh,
            np.average(sam_gen_profile) * 1e-6,
            percent=allowed_delta_percent,
        )

        elec_idx = r.result['HEAT AND/OR ELECTRICITY EXTRACTION AND GENERATION PROFILE'][0].index(
            'ELECTRICITY PROVIDED (GWh/year)'
        )
        for i in range(lifetime):
            geophires_elec = r.result['HEAT AND/OR ELECTRICITY EXTRACTION AND GENERATION PROFILE'][1:][i][elec_idx]
            sam_elec = sam_gen_profile[i + 1] * 1e-6
            self.assertAlmostEqual(geophires_elec, sam_elec, places=0)

    def test_cash_flow(self):
        m: Model = EconomicsSamTestCase._new_model(Path(self._egs_test_file_path()))

        sam_econ = calculate_sam_economics(m)
        cash_flow = sam_econ.sam_cash_flow_profile
        self.assertIsNotNone(cash_flow)

        print(
            get_sam_cash_flow_profile_tabulated_output(
                m,
                # cash_flow,
                # tablefmt='pretty',
                # tablefmt='psql',
                # tablefmt='simple_grid',
                # tablefmt='fancy_grid',
                # headers='keys'
            )
        )

        self.assertEqual(22, len(cash_flow[0]))

        def get_row(name: str) -> list[float]:
            return EconomicsSamTestCase._get_cash_flow_row(cash_flow, name)

        def get_single_value(name: str) -> list[float]:
            return EconomicsSamTestCase._get_cash_flow_row(cash_flow, name)[0]

        self.assertListEqual(get_row('PPA revenue ($)')[:-1], get_row('Total revenue ($)')[:-1])

        tic = get_single_value('Total installed cost ($)')
        self.assertLess(tic, 0)
        self.assertAlmostEqual(get_single_value('Cash flow from investing activities ($)'), tic, places=2)

        self.assertAlmostEqual(get_single_value('Cash flow from financing activities ($)'), -1.0 * tic, places=2)

        self.assertAlmostEqual(
            m.economics.LCOE.value, get_single_value('LCOE Levelized cost of energy nominal (cents/kWh)'), places=2
        )

    @staticmethod
    def _get_cash_flow_row(cash_flow: list[list[Any]], name: str) -> list[Any]:

        def r_0(r):
            if r is not None and len(r) > 0:
                return r[0]

            return None

        return next(
            [GeophiresXResult._get_sam_cash_flow_profile_entry_display_to_entry_val(ed) for ed in r]
            for r in cash_flow
            if r_0(r) == name
        )[1:]

    def test_only_electricity_end_use_supported(self):
        with self.assertRaises(RuntimeError) as e:
            self._get_result({'End-Use Option': 2})

        self.assertIn('Invalid End-Use Option (Direct-Use Heat)', str(e.exception))

    def test_multiple_construction_years(self):
        construction_years_2: GeophiresXResult = self._get_result(
            {
                'Construction Years': 2,
                'Construction CAPEX Schedule': '0.5,0.5',
                'Fraction of Investment in Bonds': 0.25,
            }
        )
        self.assertIsNotNone(construction_years_2)
        cy2_cf = construction_years_2.result['SAM CASH FLOW PROFILE']
        self.assertEqual('Year -1', cy2_cf[0][1])
        self.assertEqual('Year 20', cy2_cf[0][-1])

        try:
            with self.assertLogs(level='INFO') as logs:
                construction_years_4 = self._get_result(
                    {'Construction Years': 4, 'Construction CAPEX Schedule': '0.5,0.5'}
                )

                self.assertHasLogRecordWithMessage(
                    logs, 'has been adjusted to: [0.25, 0.25, 0.25, 0.25]', treat_substring_match_as_match=True
                )
        except AssertionError as ae:
            self._handle_assert_logs_failure(ae)

        cy4_cf = construction_years_4.result['SAM CASH FLOW PROFILE']

        cy4_result_npv = construction_years_4.result['ECONOMIC PARAMETERS']['Project NPV']
        self.assertAlmostEqualWithinSigFigs(
            quantity(cy4_result_npv['value'], cy4_result_npv['unit']).to('USD').magnitude,
            self._get_cash_flow_row(cy4_cf, 'After-tax cumulative NPV ($)')[-1],
            num_sig_figs=4,
        )

        cy4_result_irr = construction_years_4.result['ECONOMIC PARAMETERS']['After-tax IRR']

        self.assertAlmostEqualWithinSigFigs(
            quantity(cy4_result_irr['value'], cy4_result_irr['unit']).to(convertible_unit('percent')).magnitude,
            self._get_cash_flow_row(cy4_cf, 'After-tax cumulative IRR (%)')[-1],
        )

        def _floats(_cf: list[Any]) -> list[float]:
            return [float(it) for it in _cf if is_float(it)]

        self.assertEqual(
            _floats(self._get_cash_flow_row(cy4_cf, 'Debt balance [construction] ($)'))[-1],
            _floats(self._get_cash_flow_row(cy4_cf, 'Debt balance ($)'))[0],
        )

        def _sum(cf_row_name: str, abs_val: bool = False) -> float:
            return sum([abs(it) if abs_val else it for it in _floats(self._get_cash_flow_row(cy4_cf, cf_row_name))])

        idc_sum = _sum('Debt interest payment [construction] ($)')

        cy4_idc = construction_years_4.result['CAPITAL COSTS (M$)']['Interest during construction']
        self.assertAlmostEqualWithinSigFigs(
            idc_sum, quantity(cy4_idc['value'], cy4_idc['unit']).to('USD').magnitude, num_sig_figs=4
        )

        installed_cost_from_construction_cash_flow = (
            _sum('Nominal capital expenditure [construction] ($)', abs_val=True) + idc_sum
        )

        sam_total_installed_cost_usd = abs(_floats(self._get_cash_flow_row(cy4_cf, 'Total installed cost ($)'))[0])
        self.assertEqual(
            sam_total_installed_cost_usd,
            installed_cost_from_construction_cash_flow,
        )

        installed_cost_construction_line_item_sum = _sum('Installed cost [construction] ($)', abs_val=True)
        self.assertAlmostEqualWithinSigFigs(sam_total_installed_cost_usd, installed_cost_construction_line_item_sum, 8)

        self.assertLess(
            construction_years_4.result['CAPITAL COSTS (M$)']['Overnight Capital Cost']['value'],
            installed_cost_from_construction_cash_flow,
        )

        self.assertLess(
            construction_years_4.result['CAPITAL COSTS (M$)']['Overnight Capital Cost']['value'],
            construction_years_4.result['CAPITAL COSTS (M$)']['Total CAPEX']['value'],
        )

        self.assertAlmostEqualWithinSigFigs(
            _sum('Issuance of equity [construction] ($)'),
            _floats(self._get_cash_flow_row(cy4_cf, 'Issuance of equity ($)'))[0],
            8,
        )

    def test_validate_construction_capex_schedule(self):
        model = self._new_model(self._egs_test_file_path(), {'Print Output to Console': 1})
        model_logger = model.logger

        def _sched(sched: list[float]) -> listParameter:
            construction_capex_schedule_name = 'Construction CAPEX Schedule'
            schedule_param = listParameter(
                construction_capex_schedule_name,
                DefaultValue=[1.0],
                Min=0.0,
                Max=1.0,
                ToolTipText=construction_capex_schedule_name,
            )
            schedule_param.value = sched
            return schedule_param

        half_half = [0.5, 0.5]
        self.assertListEqual(half_half, _validate_construction_capex_schedule(_sched(half_half), 2, model))

        try:
            with self.assertLogs(logger=model_logger.name, level='WARNING') as logs:
                quarters = [0.25] * 4
                self.assertListEqual(half_half, _validate_construction_capex_schedule(_sched(quarters), 2, model))
                self.assertHasLogRecordWithMessage(
                    logs, 'has been adjusted to: [0.5, 0.5]', treat_substring_match_as_match=True
                )
        except AssertionError as ae:
            self._handle_assert_logs_failure(ae)

        try:
            with self.assertLogs(logger=model_logger.name, level='WARNING') as logs2:
                double_ones = [1.0, 1.0]
                self.assertListEqual(half_half, _validate_construction_capex_schedule(_sched(double_ones), 2, model))
                self.assertHasLogRecordWithMessage(logs2, 'does not sum to 1.0', treat_substring_match_as_match=True)
        except AssertionError as ae:
            self._handle_assert_logs_failure(ae)

    def test_bond_interest_rate_during_construction(self):
        fraction_in_bonds: float = 0.5
        r: GeophiresXResult = self._get_result(
            {
                'Construction Years': 2,
                'Inflation Rate During Construction': 0,
                'Fraction of Investment in Bonds': fraction_in_bonds,
                'Inflated Bond Interest Rate During Construction': 0,
            }
        )

        def get_equity_usd(_r: GeophiresXResult) -> float:
            equity_str = self._get_cash_flow_row(_r.result['SAM CASH FLOW PROFILE'], 'Issuance of equity ($)')[-1]

            return float(equity_str)

        equity_musd = quantity(get_equity_usd(r), 'USD').to('MUSD').magnitude
        total_capex_musd = r.result['SUMMARY OF RESULTS']['Total CAPEX']['value']
        self.assertAlmostEqual(total_capex_musd * fraction_in_bonds, equity_musd, places=2)

    def test_bond_financing_start_year(self):
        construction_years = 4

        def _get_result_(_financing_start_year: int, _construction_years: int = construction_years) -> GeophiresXResult:
            return self._get_result(
                {
                    'Construction Years': _construction_years,
                    'Inflation Rate During Construction': 0,
                    'Fraction of Investment in Bonds': 0.5,
                    'Bond Financing Start Year': _financing_start_year,
                }
            )

        def get_debt_issuance_usd(_r: GeophiresXResult) -> list[float]:
            return self._get_cash_flow_row(_r.result['SAM CASH FLOW PROFILE'], 'Issuance of debt [construction] ($)')

        def _assert_debt_issuance_cash_flow_reflects_bond_financing_start_year(_r, _financing_start_year: int) -> None:
            di = get_debt_issuance_usd(_r)
            year_indexes = [int(it.replace('Year ', '')) for it in _r.result['SAM CASH FLOW PROFILE'][0][1:]]
            bond_financing_start_cash_flow_index = (
                year_indexes.index(_financing_start_year) if year_indexes[0] <= _financing_start_year else 0
            )
            self.assertTrue(all(it == 0 for it in di[:bond_financing_start_cash_flow_index]))
            self.assertTrue(all(it > 0 for it in di[bond_financing_start_cash_flow_index:]))

        for financing_start_year in range(-1 * (construction_years - 1), 1):
            r: GeophiresXResult = _get_result_(financing_start_year)
            _assert_debt_issuance_cash_flow_reflects_bond_financing_start_year(r, financing_start_year)

        fsy_min = -13
        r_prior_construction: GeophiresXResult = _get_result_(fsy_min)
        _assert_debt_issuance_cash_flow_reflects_bond_financing_start_year(r_prior_construction, fsy_min)

        max_construction_years = 14
        _assert_debt_issuance_cash_flow_reflects_bond_financing_start_year(
            _get_result_(fsy_min, _construction_years=max_construction_years), fsy_min
        )

        with self.assertRaises(RuntimeError):
            _get_result_(1)  # Bond financing start year is negative year indexed, so value must be less than 0

    def test_ppa_pricing_model(self):
        self.assertListEqual(
            [
                0.15,
                0.15,
                0.154053223,
                0.15810644599999998,
                0.162159669,
                0.166212892,
                0.170266115,
                0.174319338,
                0.17837256099999999,
                0.18242578399999998,
                0.186479007,
                0.19053223,
                0.194585453,
                0.198638676,
                0.202691899,
                0.206745122,
                0.210798345,
                0.214851568,
                0.218904791,
                0.22295801399999998,
            ],
            _ppa_pricing_model(20, 0.15, 1.00, 1, 0.004053223),
        )

    def test_property_tax_rate(self):
        pt_rate = 0.01
        m: Model = EconomicsSamTestCase._new_model(
            self._egs_test_file_path(), additional_params={'Property Tax Rate': pt_rate}
        )

        sam_econ = calculate_sam_economics(m)
        cash_flow = sam_econ.sam_cash_flow_profile

        def get_row(name: str):
            return EconomicsSamTestCase._get_cash_flow_row(cash_flow, name)

        ptv_row = get_row('Property tax net assessed value ($)')
        pte_row = get_row('Property tax expense ($)')
        self.assertIsNotNone(pte_row)
        self.assertAlmostEqual(ptv_row[1] * pt_rate, pte_row[1], places=0)  # Assumes 100% property tax basis

    def test_incentives(self):
        def assert_incentives(params, expected_ibi_usd):
            m: Model = EconomicsSamTestCase._new_model(self._egs_test_file_path(), additional_params=params)

            sam_econ = calculate_sam_economics(m)
            cash_flow = sam_econ.sam_cash_flow_profile

            def get_row(name: str):
                return EconomicsSamTestCase._get_cash_flow_row(cash_flow, name)

            other_ibi = get_row('Other IBI income ($)')[0]
            total_ibi = get_row('Total IBI income ($)')[0]
            self.assertEqual(expected_ibi_usd, other_ibi)
            self.assertEqual(other_ibi, total_ibi)

        assert_incentives({'One-time Grants Etc': 1}, 1_000_000)
        assert_incentives({'Other Incentives': 2.5}, 2_500_000)

        assert_incentives({'One-time Grants Etc': 100, 'Other Incentives': 0.1}, 100_100_000)

    def test_inflation_rate_during_construction(self):
        infl_rate = 0.05
        r_no_infl = self._get_result({'Inflation Rate During Construction': 0})
        r_infl = self._get_result({'Inflation Rate During Construction': infl_rate})

        cash_flow_no_infl = r_no_infl.result['SAM CASH FLOW PROFILE']
        cash_flow_infl = r_infl.result['SAM CASH FLOW PROFILE']

        tic = 'Total installed cost ($)'
        tic_no_infl = EconomicsSamTestCase._get_cash_flow_row(cash_flow_no_infl, tic)[0]
        tic_infl = EconomicsSamTestCase._get_cash_flow_row(cash_flow_infl, tic)[0]

        self.assertAlmostEqual(tic_no_infl * (1 + infl_rate), tic_infl, places=0)

        def _infl_cost_musd(r: GeophiresXResult) -> float:
            return r.result['CAPITAL COSTS (M$)']['Inflation costs during construction']['value']

        params_3 = {
            'Construction Years': 3,
            'Inflation Rate': 0.04769,
            'Inflated Bond Interest Rate During Construction': 0,
        }
        r3: GeophiresXResult = self._get_result(
            params_3, file_path=self._get_test_file_path('generic-egs-case-3_no-inflation-rate-during-construction.txt')
        )

        # Validate that inflation during construction is calculated by compounding the inflation rate over construction years
        occ_3 = r3.result['CAPITAL COSTS (M$)']['Overnight Capital Cost']['value']
        infl_rate_3 = params_3['Inflation Rate']
        # Default uniform schedule for 3 years
        schedule = [1 / 3, 1 / 3, 1 / 3]

        expected_infl_cost_3 = sum([occ_3 * s * ((1 + infl_rate_3) ** (y + 1) - 1) for y, s in enumerate(schedule)])

        self.assertAlmostEqual(expected_infl_cost_3, _infl_cost_musd(r3), places=1)

        cash_flow_3 = r3.result['SAM CASH FLOW PROFILE']
        tic_3 = EconomicsSamTestCase._get_cash_flow_row(cash_flow_3, tic)[-1]

        # Verify TIC matches OCC + Inflation Cost (IDC is 0)
        self.assertAlmostEqual(occ_3 + expected_infl_cost_3, quantity(abs(tic_3), 'USD').to('MUSD').magnitude, places=0)

        params4 = {
            'Construction Years': 3,
            'Inflation Rate During Construction': 0.15,
            'Inflated Bond Interest Rate During Construction': 0,
        }
        r4: GeophiresXResult = self._get_result(
            params4, file_path=self._get_test_file_path('generic-egs-case-3_no-inflation-rate-during-construction.txt')
        )

        # r4 treats 'Inflation Rate During Construction' as the annual inflation rate in the current implementation
        infl_rate_4 = params4['Inflation Rate During Construction']
        occ_4 = r4.result['CAPITAL COSTS (M$)']['Overnight Capital Cost']['value']

        expected_infl_cost_4 = sum([occ_4 * s * ((1 + infl_rate_4) ** (y + 1) - 1) for y, s in enumerate(schedule)])
        self.assertAlmostEqual(expected_infl_cost_4, _infl_cost_musd(r4), places=1)

    def test_ptc(self):
        def assert_ptc(params, expected_ptc_usd_per_kWh):
            m: Model = EconomicsSamTestCase._new_model(self._egs_test_file_path(), additional_params=params)

            sam_econ = calculate_sam_economics(m)
            cash_flow = sam_econ._sam_cash_flow_profile_operational_years

            def get_row(name: str):
                return EconomicsSamTestCase._get_cash_flow_row(cash_flow, name)

            ptc_vals = get_row('Federal PTC income ($)')
            self.assertListAlmostEqual(expected_ptc_usd_per_kWh, ptc_vals, percent=1)

        assert_ptc({}, [0] * 21)

        base_expected = [
            0,
            126447893,
            127031474,
            127215192,
            127324226,
            127400735,
            127459143,
            127506088,
            127545160,
            127578508,
            127607522,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
        ]

        assert_ptc({'Production Tax Credit Electricity': 0.04}, base_expected)

        inflation_rate = 0.03

        # Ideally this would be calculated from first principles here in the test (approximately: base_expected *
        # an inflation vector with correct offset for PTC escalation year = 2), but this is fine for now.
        inflation_expected = [
            0,
            126447893,
            130207261,
            133575951,
            140056649,
            143325827,
            146578015,
            153007306,
            156242820,
            162662598,
            165889779,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
        ]

        assert_ptc(
            {
                'Production Tax Credit Electricity': 0.04,
                'Production Tax Credit Inflation Adjusted': True,
                'Inflation Rate': inflation_rate,
            },
            inflation_expected,
        )

        shortened_term_duration_yr = 9
        shortened_term_expected = base_expected.copy()
        shortened_term_expected[shortened_term_duration_yr + 1] = 0
        assert_ptc(
            {'Production Tax Credit Electricity': 0.04, 'Production Tax Credit Duration': 9}, shortened_term_expected
        )

    def test_capacity_factor(self):
        r_90 = self._get_result({'Utilization Factor': 0.9})
        cash_flow_90 = r_90.result['SAM CASH FLOW PROFILE']

        r_20 = self._get_result({'Utilization Factor': 0.2})
        cash_flow_20 = r_20.result['SAM CASH FLOW PROFILE']

        etg = 'Electricity to grid (kWh)'

        etg_90 = EconomicsSamTestCase._get_cash_flow_row(cash_flow_90, etg)
        etg_20 = EconomicsSamTestCase._get_cash_flow_row(cash_flow_20, etg)

        etg_20_expected = [(etg_90_entry / 0.9) * 0.2 for etg_90_entry in etg_90]

        self.assertListAlmostEqual(etg_20_expected, etg_20, percent=1)

    def test_unsupported_econ_params_ignored_with_warning(self):
        is_github_actions = 'CI' in os.environ or 'TOXPYTHON' in os.environ
        try:
            with self.assertLogs(level='INFO') as logs:
                gtr_provided_result = self._get_result({'Gross Revenue Tax Rate': 0.5})

                self.assertHasLogRecordWithMessage(
                    logs,
                    'Gross Revenue Tax Rate provided value (0.5) will be ignored. '
                    '(SAM Economics tax rates are determined from Combined Income Tax Rate and Property Tax Rate.)',
                )
        except AssertionError as ae:
            if is_github_actions:
                # TODO to investigate and fix
                self.skipTest('Skipping due to intermittent failure on GitHub Actions')
            else:
                raise ae

        def _npv(r: GeophiresXResult) -> float:
            return r.result['ECONOMIC PARAMETERS']['Project NPV']['value']

        default_result = self._get_result({})

        self.assertEqual(_npv(default_result), _npv(gtr_provided_result))  # Check GTR is ignored in calculations

        try:
            with self.assertLogs(level='INFO') as logs:
                eir_provided_result = self._get_result({'Inflated Equity Interest Rate': 0.25})

                self.assertHasLogRecordWithMessage(
                    logs,
                    'Inflated Equity Interest Rate provided value (0.25) will be ignored. '
                    '(SAM Economics does not support Inflated Equity Interest Rate.)',
                )
        except AssertionError as ae:
            if is_github_actions:
                # TODO to investigate and fix
                self.skipTest('Skipping due to intermittent failure on GitHub Actions')
            else:
                raise ae

        self.assertEqual(_npv(default_result), _npv(eir_provided_result))  # Check EIR is ignored in calculations

    def test_carbon_calculations(self):
        r = self._get_result(
            {
                'Do Carbon Price Calculations': True,
                'Starting Carbon Credit Value': 0.015,
                'Ending Carbon Credit Value': 0.1,
                'Carbon Escalation Start Year': 5,
                'Carbon Escalation Rate Per Year': 0.01,
                'Units:Total Saved Carbon Production': 'kilotonne',
            }
        )

        ace = r.result['SUMMARY OF RESULTS']['Total Avoided Carbon Emissions']
        self.assertEqual('kilotonne', ace['unit'])
        self.assertAlmostEqualWithinPercentage(27159, ace['value'], percent=20)

    def test_clean_profile(self):
        profile = [
            ['foo', 1, 2, 3],
            [None] * 4,
            ['bar', 4, 5, 6],
            [None] * 4,
            [None] * 4,
            ['baz', 7, 8, 9],
        ]

        clean = _clean_profile(profile)

        self.assertListEqual(
            clean,
            [
                ['foo', 1, 2, 3],
                [None] * 4,
                ['bar', 4, 5, 6],
                [None] * 4,
                ['baz', 7, 8, 9],
            ],
        )

    def test_is_category_row_label(self):
        self.assertTrue(_is_category_row_label('OPERATING ACTIVITIES'))
        self.assertFalse(_is_category_row_label('plus PBI if not available for debt service:'))

    def test_is_designator_row_label(self):
        self.assertTrue(_is_designator_row_label('plus PBI if not available for debt service:'))

    def test_sig_figs(self):
        self.assertListEqual(sig_figs([1.14, 2.24], 2), [1.1, 2.2])
        self.assertListEqual(sig_figs((1.14, 2.24), 2), [1.1, 2.2])

    def test_get_fed_and_state_tax_rates(self):
        self.assertEqual(([21], [7]), _get_fed_and_state_tax_rates(0.28))
        self.assertEqual(([21], [0]), _get_fed_and_state_tax_rates(0.21))
        self.assertEqual(([21], [9]), _get_fed_and_state_tax_rates(0.3))
        self.assertEqual(([10], [0]), _get_fed_and_state_tax_rates(0.1))

    def test_nan_after_tax_irr_output_param(self):
        """
        Verify that After-tax IRRs that would have been calculated as NaN by SAM are instead calculated with
        numpy-financial.irr
        """

        def _irr(_r: GeophiresXResult) -> float:
            return _r.result['ECONOMIC PARAMETERS']['After-tax IRR']['value']

        rate_params = {
            'Electricity Escalation Rate Per Year': 0.00348993288590604,
            'Starting Electricity Sale Price': 0.13,
        }
        r: GeophiresXResult = self._get_result(rate_params)
        after_tax_irr_cash_flow_entries = EconomicsSamTestCase._get_cash_flow_row(
            r.result['SAM CASH FLOW PROFILE'], 'After-tax cumulative IRR (%)'
        )
        sam_after_tax_irr_calc = float(after_tax_irr_cash_flow_entries[-1])

        try:
            # As of 2025-11-14, this assertion is expected to fail because After-tax cumulative IRR is now backfilled
            # upstream by the SAM-EM as part of adjusting IRR for multi-year construction periods.
            # However, we would want to run the remainder of the test if the assertion does pass, hence why skipping
            # is conditional.
            assert math.isnan(sam_after_tax_irr_calc)
        except AssertionError:
            self.skipTest('Skipping because NaN after-tax IRR is now handled upstream by SAM-EM')

        after_tax_cash_flow = EconomicsSamTestCase._get_cash_flow_row(
            r.result['SAM CASH FLOW PROFILE'], 'Total after-tax returns ($)'
        )
        npf_irr = npf.irr(after_tax_cash_flow) * 100.0

        r_irr = _irr(r)
        self.assertFalse(math.isnan(r_irr))
        self.assertAlmostEqual(npf_irr, r_irr, places=2)

    def test_nan_irr_cash_flow_line_items_for_multiple_construction_years(self):
        """
        IRR during construction years is expected to be nan - serialized as 'NaN'
        """

        def _irr(_r: GeophiresXResult) -> float:
            return _r.result['ECONOMIC PARAMETERS']['After-tax IRR']['value']

        construction_years = 2

        rate_params = {
            'Electricity Escalation Rate Per Year': 0.00348993288590604,
            'Starting Electricity Sale Price': 0.13,
            'Construction Years': construction_years,
        }
        r: GeophiresXResult = self._get_result(rate_params)
        after_tax_irr_cash_flow_entries = EconomicsSamTestCase._get_cash_flow_row(
            r.result['SAM CASH FLOW PROFILE'], 'After-tax cumulative IRR (%)'
        )
        self.assertTrue(
            all(it == _SAM_CASH_FLOW_NAN_STR for it in after_tax_irr_cash_flow_entries[:construction_years])
        )
        self.assertTrue(all(is_float(it) for it in after_tax_irr_cash_flow_entries[construction_years:]))

    def test_nan_project_payback_period(self):
        def _payback_period(_r: GeophiresXResult) -> float:
            return _r.result['ECONOMIC PARAMETERS']['Project Payback Period']['value']

        never_pays_back_params = {
            'Starting Electricity Sale Price': 0.00001,
            'Ending Electricity Sale Price': 0.00002,
        }
        r: GeophiresXResult = self._get_result(never_pays_back_params)
        self.assertIsNone(_payback_period(r))

    def test_accrued_financing_during_construction(self):
        def _accrued_financing(_r: GeophiresXResult) -> float:
            econ_params = _r.result['ECONOMIC PARAMETERS']
            acf_key = 'Accrued financing during construction'
            if econ_params[acf_key] is None:
                self.skipTest(f'Economic parameters do not contain {acf_key}. (This is expected/OK.)')

            return econ_params[acf_key]['value']

        params1 = {
            'Construction Years': 1,
            'Inflation Rate': 0.04769,
        }
        r1: GeophiresXResult = self._get_result(
            params1, file_path=self._get_test_file_path('generic-egs-case-3_no-inflation-rate-during-construction.txt')
        )
        self.assertAlmostEqual(0, _accrued_financing(r1), places=1)

        params2 = {
            'Construction Years': 1,
            'Inflation Rate During Construction': 0.15,
        }
        r2: GeophiresXResult = self._get_result(
            params2, file_path=self._get_test_file_path('generic-egs-case-3_no-inflation-rate-during-construction.txt')
        )
        self.assertEqual(0, _accrued_financing(r2))

    def test_add_ons(self):
        no_add_ons_result = self._get_result(
            {'Do AddOn Calculations': False}, file_path=self._get_test_file_path('egs-sam-em-add-ons.txt')
        )
        self._assert_capex_line_items_sum_to_total(no_add_ons_result)

        add_ons_result = self._get_result(
            {'Do AddOn Calculations': True}, file_path=self._get_test_file_path('egs-sam-em-add-ons.txt')
        )
        self.assertIsNotNone(add_ons_result)
        self._assert_capex_line_items_sum_to_total(add_ons_result)

        self.assertGreater(
            add_ons_result.result['SUMMARY OF RESULTS']['Total CAPEX']['value'],
            no_add_ons_result.result['SUMMARY OF RESULTS']['Total CAPEX']['value'],
        )

        self.assertGreater(add_ons_result.result['CAPITAL COSTS (M$)']['Total Add-on CAPEX']['value'], 0)

        self.assertGreater(
            add_ons_result.result['OPERATING AND MAINTENANCE COSTS (M$/yr)']['Total operating and maintenance costs'][
                'value'
            ],
            no_add_ons_result.result['OPERATING AND MAINTENANCE COSTS (M$/yr)'][
                'Total operating and maintenance costs'
            ]['value'],
        )

        self.assertGreater(
            add_ons_result.result['OPERATING AND MAINTENANCE COSTS (M$/yr)']['Total Add-on OPEX']['value'], 0
        )

        with self.assertRaises(RuntimeError, msg='AddOn Electricity is not supported for SAM Economic Models'):
            self._get_result(
                {'Do AddOn Calculations': True, 'AddOn Electricity Gained 1': 100},
                file_path=self._get_test_file_path('egs-sam-em-add-ons.txt'),
            )

        with self.assertRaises(RuntimeError, msg='AddOn Heat is not supported for SAM Economic Models'):
            self._get_result(
                {'Do AddOn Calculations': True, 'AddOn Heat Gained 1': 100},
                file_path=self._get_test_file_path('egs-sam-em-add-ons.txt'),
            )

        add_ons_multiple_construction_years_result = self._get_result(
            {'Do AddOn Calculations': True, 'Construction Years': 3},
            file_path=self._get_test_file_path('egs-sam-em-add-ons.txt'),
        )
        self.assertGreater(
            add_ons_multiple_construction_years_result.result['SUMMARY OF RESULTS']['Total CAPEX']['value'],
            add_ons_result.result['SUMMARY OF RESULTS']['Total CAPEX']['value'],
        )
        self.assertEqual(
            add_ons_multiple_construction_years_result.result['CAPITAL COSTS (M$)']['Total Add-on CAPEX']['value'],
            add_ons_result.result['CAPITAL COSTS (M$)']['Total Add-on CAPEX']['value'],
        )

    def _assert_capex_line_items_sum_to_total(self, r: GeophiresXResult):
        capex_line_items = {key: value for key, value in r.result['CAPITAL COSTS (M$)'].items() if value is not None}

        total_capex_unit = capex_line_items['Total CAPEX']['unit']
        total_capex = quantity(capex_line_items['Total CAPEX']['value'], total_capex_unit)

        capex_line_item_sum = 0
        for line_item_name, capex_line_item in capex_line_items.items():
            if line_item_name not in [
                'Overnight Capital Cost',
                'Total CAPEX',
                'Total surface equipment costs',
                'Drilling and completion costs per well',
                'Drilling and completion costs per vertical production well',
                'Drilling and completion costs per vertical injection well',
                'Drilling and completion costs per non-vertical section',
            ]:
                capex_line_item_sum += quantity(capex_line_item['value'], capex_line_item['unit']).to(total_capex_unit)

        self.assertEqual(total_capex, capex_line_item_sum)

    def test_royalty_rate(self):
        royalty_rate = 0.1
        m: Model = EconomicsSamTestCase._new_model(
            self._egs_test_file_path(), additional_params={'Royalty Rate': royalty_rate}
        )

        sam_econ: SamEconomicsCalculations = calculate_sam_economics(m)
        cash_flow = sam_econ.sam_cash_flow_profile

        def get_row(name: str):
            return EconomicsSamTestCase._get_cash_flow_row(cash_flow, name)

        ppa_revenue_row_USD = get_row('PPA revenue ($)')
        expected_royalties_USD = [x * royalty_rate for x in ppa_revenue_row_USD]
        self.assertListAlmostEqual(expected_royalties_USD, sam_econ.royalties_opex.value, places=0)

        om_prod_based_expense_row = get_row('O&M production-based expense ($)')
        self.assertListAlmostEqual(expected_royalties_USD, om_prod_based_expense_row, places=0)
        # Note the above assertion assumes royalties are the only production-based O&M expenses. If this changes,
        # the assertion will need to be updated.

    def test_royalty_rate_schedule(self):
        royalty_rate = 0.1
        escalation_rate = 0.01
        max_rate = royalty_rate + 5 * escalation_rate
        m: Model = EconomicsSamTestCase._new_model(
            self._egs_test_file_path(),
            additional_params={
                'Royalty Rate': royalty_rate,
                'Royalty Rate Escalation': escalation_rate,
                'Royalty Rate Maximum': max_rate,
            },
        )

        schedule: list[float] = _get_royalty_rate_schedule(m)

        self.assertListAlmostEqual(
            [0.1, 0.11, 0.12, 0.13, 0.14, *[0.15] * 15],
            schedule,
            places=3,
        )

    def test_royalty_rate_escalation_start_year(self) -> None:
        construction_years: int = 5
        plant_lifetime: int = 20

        def _get_result(start_year: int) -> tuple[str, dict[str, Any], GeophiresXResult]:
            _input_file_path = self._get_test_file_path('generic-egs-case.txt')
            _additional_params = {
                'Economic Model': 5,
                'Construction Years': construction_years,
                'Plant Lifetime': plant_lifetime,
                'Royalty Rate': 0.04,
                'Royalty Rate Maximum': 0.06,
                'Royalty Rate Escalation': 0.02,
                'Royalty Rate Escalation Start Year': start_year,
                'Print Output to Console': 1,
            }
            input_params: GeophiresInputParameters = GeophiresInputParameters(
                from_file_path=_input_file_path,
                params=_additional_params,
            )
            return _input_file_path, _additional_params, GeophiresXClient().get_geophires_result(input_params)

        def __cash_flow_row(r: GeophiresXResult, row_name: str) -> str:
            from geophires_x.EconomicsSam import _cash_flow_profile_row

            return [it for it in _cash_flow_profile_row(r.result['SAM CASH FLOW PROFILE'], row_name) if is_float(it)]

        def _royalty_cash_flow(r: GeophiresXResult) -> list[float]:
            return __cash_flow_row(r, 'O&M production-based expense ($)')[1:]  # Drop year 0 ($0 revenue)

        def _royalty_rates_from_cash_flow(r: GeophiresXResult) -> list[float]:
            return __cash_flow_row(r, 'Royalty rate (%)')

        input_file_path, additional_params, result_4 = _get_result(4)

        expected_royalty_rate_schedule_4 = [*([0.04] * 3), *([0.06] * (plant_lifetime - 3))]
        model = EconomicsSamTestCase._new_model(input_file_path, additional_params=additional_params)
        econ_royalty_rate_schedule_4 = model.economics.get_royalty_rate_schedule(model)
        self.assertListEqual(expected_royalty_rate_schedule_4, econ_royalty_rate_schedule_4)

        result_4_royalty_cash_flow_usd = _royalty_cash_flow(result_4)
        self.assertEqual(len(expected_royalty_rate_schedule_4), len(result_4_royalty_cash_flow_usd))

        econ_royalty_rate_schedule_4_percent = [
            quantity(it, 'dimensionless').to(convertible_unit('percent')).magnitude
            for it in econ_royalty_rate_schedule_4
        ]
        royalty_rates_from_cash_flow_4 = _royalty_rates_from_cash_flow(result_4)
        self.assertListEqual(econ_royalty_rate_schedule_4_percent, royalty_rates_from_cash_flow_4)

        expected_royalties_based_on_cash_flow_ppa_revenue = []
        cash_flow_ppa_revenue = __cash_flow_row(result_4, 'PPA revenue ($)')[1:]
        for i, _rev_usd in enumerate(econ_royalty_rate_schedule_4_percent):
            expected_royalties_based_on_cash_flow_ppa_revenue.append(
                cash_flow_ppa_revenue[i] * econ_royalty_rate_schedule_4[i]
            )

        self.assertListAlmostEqual(
            expected_royalties_based_on_cash_flow_ppa_revenue, result_4_royalty_cash_flow_usd, percent=0.0001
        )

    def test_sam_cash_flow_total_after_tax_returns_all_years(self):
        input_file = self._egs_test_file_path()
        additional_params = {'Construction Years': 2}
        m: Model = EconomicsSamTestCase._new_model(input_file, additional_params=additional_params)

        input_params = ImmutableGeophiresInputParameters(additional_params, from_file_path=Path(input_file))

        sam_econ: SamEconomicsCalculations = calculate_sam_economics(m)
        after_tax_returns_cash_flow = sam_econ.sam_after_tax_net_cash_flow_all_years
        construction_years = EconomicsSamTestCase.get_input_parameter(input_params, 'Construction Years')
        plant_lifetime = EconomicsSamTestCase.get_input_parameter(input_params, 'Plant Lifetime')

        self.assertEqual(construction_years + plant_lifetime, len(after_tax_returns_cash_flow))

        self.assertListEqual(
            EconomicsSamTestCase._get_cash_flow_row(sam_econ.sam_cash_flow_profile, 'After-tax net cash flow ($)'),
            sam_econ.sam_after_tax_net_cash_flow_all_years,
        )

    @staticmethod
    def _new_model(input_file: Path, additional_params: dict[str, Any] | None = None, read_and_calculate=True) -> Model:
        if additional_params is not None:
            params = GeophiresInputParameters(from_file_path=input_file, params=additional_params)
            input_file = params.as_file_path()

        stash_cwd = Path.cwd()
        stash_sys_argv = sys.argv

        sys.argv = ['']

        m = Model(enable_geophires_logging_config=False, input_file=input_file)

        sys.argv = stash_sys_argv
        os.chdir(stash_cwd)

        if read_and_calculate:
            m.read_parameters()
            m.Calculate()

        return m

    def _handle_assert_logs_failure(self, ae: AssertionError):
        if sys.version_info[:2] == (3, 8) and self._is_github_actions():
            # FIXME - see
            #  https://github.com/softwareengineerprogrammer/GEOPHIRES/actions/runs/19646240874/job/56262028512#step:5:344
            _log.warning(
                f'WARNING: Skipping logs assertion in GitHub Actions '
                f'for Python {sys.version_info.major}.{sys.version_info.minor}'
            )
        else:
            raise ae
