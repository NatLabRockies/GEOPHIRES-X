from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import numpy_financial as npf

# ruff: noqa: I001  # Successful module initialization is dependent on this specific import order.
from geophires_x.Model import Model
from geophires_x.Economics import CalculateFinancialPerformance
from geophires_x.EconomicsUtils import redrilling_cost_multipliers
from geophires_x_client import (
    GeophiresXResult,
    GeophiresXClient,
    GeophiresInputParameters,
    ImmutableGeophiresInputParameters,
)
from tests.base_test_case import BaseTestCase


class EconomicsTestCase(BaseTestCase):
    @staticmethod
    def cumm_revenue(total_revenue):
        cumm_revenue = [total_revenue[0]] * len(total_revenue)
        cumm_revenue[1] = total_revenue[1]
        for i in range(2, len(total_revenue)):
            cumm_revenue[i] = cumm_revenue[i - 1] + total_revenue[i]
        return cumm_revenue

    def test_irr(self):
        """
        Test cases adapted from https://numpy.org/numpy-financial/latest/irr.html
        """

        def calc_irr(total_revenue):
            NPV, IRR, VIR, MOIC = CalculateFinancialPerformance(
                30, 5, total_revenue, EconomicsTestCase.cumm_revenue(total_revenue), 1000, 10
            )

            return IRR

        self.assertAlmostEqual(28.095, calc_irr([-100, 39, 59, 55, 20]), places=3)
        self.assertAlmostEqual(-9.55, calc_irr([-100, 0, 0, 74]), places=2)
        self.assertAlmostEqual(-8.33, calc_irr([-100, 100, 0, -7]), places=2)
        self.assertAlmostEqual(6.21, calc_irr([-100, 100, 0, 7]), places=2)
        self.assertAlmostEqual(8.86, calc_irr([-5, 10.5, 1, -8, 1]), places=2)

    def test_npv(self):
        """
        Includes sanity checks that numpy-financial.npv used by CalculateFinancialPerformance
        matches reference calculations
        """

        rate = 0.12

        def calc_npv(total_revenue, discount_initial_year_cashflow=False):
            NPV, IRR, VIR, MOIC = CalculateFinancialPerformance(
                len(total_revenue) + 1,
                rate * 100,
                total_revenue,
                EconomicsTestCase.cumm_revenue(total_revenue),
                total_revenue[0],
                10,
                discount_initial_year_cashflow=discount_initial_year_cashflow,
            )

            return NPV

        # https://www.nrel.gov/docs/legosti/old/5173.pdf, p. 41
        cashflow_series = [-10000, 7274, 6558, 6223, 6087, 6259]

        npf_npv = npf.npv(rate, cashflow_series)
        self.assertEqual(13572, round(npf_npv))

        geophires_npv = calc_npv(cashflow_series)
        self.assertEqual(13572, round(geophires_npv))

        # https://support.microsoft.com/en-us/office/npv-function-8672cb67-2576-4d07-b67b-ac28acf2a568
        rate = 0.1
        cashflow_series = [-10000, 3000, 4200, 6800]
        excel_npv = npf.npv(rate, [0, *cashflow_series])
        self.assertEqual(1188.44, round(excel_npv, 2))

        geophires_npv = calc_npv(cashflow_series, discount_initial_year_cashflow=True)
        self.assertEqual(1188.44, round(geophires_npv, 2))

    def test_well_drilling_cost_correlation_tooltip_text(self):
        ec = self._new_model().economics
        self.assertEqual(
            ec.wellcorrelation.ToolTipText,
            # noinspection SqlNoDataSourceInspection
            'Select the built-in well drilling and completion cost correlation: '
            '1: vertical small diameter, baseline; '
            '2: deviated small diameter, baseline; '
            '3: vertical large diameter, baseline; '
            '4: deviated large diameter, baseline; '
            '5: Simple (per-meter cost); '
            '6: vertical small diameter, intermediate1; '
            '7: vertical small diameter, intermediate2; '
            '8: deviated small diameter, intermediate1; '
            '9: deviated small diameter, intermediate2; '
            '10: vertical large diameter, intermediate1; '
            '11: vertical large diameter, intermediate2; '
            '12: deviated large diameter, intermediate1; '
            '13: deviated large diameter, intermediate2; '
            '14: vertical open-hole, small diameter, ideal; '
            '15: deviated liner, small diameter, ideal; '
            '16: vertical open-hole, large diameter, ideal; '
            '17: deviated liner, large diameter, ideal. '
            "Baseline correlations (1-4) are from NREL's 2025 cost curve update. "
            'Intermediate and ideal correlations (6-17) are from GeoVision.',
        )

    def test_indirect_cost_factor(self) -> None:
        self.assertEqual(1.12, self._new_model().economics._indirect_cost_factor)

    def test_redrilling_cost_multipliers(self) -> None:
        self.assertEqual([1.0, 1.0, 1.0], redrilling_cost_multipliers(3, 0))
        self.assertEqual([], redrilling_cost_multipliers(0, 0.15))

        multipliers = redrilling_cost_multipliers(3, 0.2)
        self.assertAlmostEqual(0.8, multipliers[0])  # the site's second wellfield: one doubling
        self.assertAlmostEqual(0.8 * 0.8, multipliers[2])  # its fourth: two doublings
        self.assertTrue(multipliers[0] > multipliers[1] > multipliers[2])

        with self.assertRaises(ValueError):
            redrilling_cost_multipliers(1, 1.0)

    def test_peaking_boiler_cost(self):
        def _get_result(peaking_boiler_cost_: int) -> GeophiresXResult:
            return GeophiresXClient().get_geophires_result(
                GeophiresInputParameters(
                    from_file_path=self._get_test_file_path('../examples/example12_DH.txt'),
                    params={
                        'Peaking Boiler Cost per kW': peaking_boiler_cost_,
                    },
                )
            )

        def _lcoh_pbc(r: GeophiresXResult) -> tuple[float, float]:
            return (
                r.result['SUMMARY OF RESULTS']['Direct-Use heat breakeven price (LCOH)']['value'],
                r.result['CAPITAL COSTS (M$)']['of which Peaking Boiler Cost']['value'],
            )

        lcoh, peaking_boiler_cost = _lcoh_pbc(_get_result(0))
        self.assertLess(lcoh, 13.19)
        self.assertEqual(0, peaking_boiler_cost)

    def test_stimulation_cost_per_fracture_surface_area(self):
        def _get_result() -> GeophiresXResult:
            return GeophiresXClient().get_geophires_result(
                ImmutableGeophiresInputParameters(
                    from_file_path=self._get_test_file_path('generic-egs-case-5_no-stim-costs-specified.txt'),
                    params={
                        'Reservoir Stimulation Capital Cost per Production Well': -1,
                        'Reservoir Stimulation Capital Cost per Fracture Surface Area': 0.87431693989,
                        'Print Output to Console': True,
                    },
                )
            )

        r: GeophiresXResult = _get_result()

        cap_costs = r.result['CAPITAL COSTS (M$)']
        self.assertAlmostEqual(454.02, cap_costs['Stimulation costs']['value'], delta=0)

        self.assertAlmostEqual(4.83, cap_costs['Stimulation costs per well']['value'], delta=0)

    def test_stimulation_cost_per_fracture_surface_area_injection_only(self):
        r: GeophiresXResult = GeophiresXClient().get_geophires_result(
            ImmutableGeophiresInputParameters(
                from_file_path=self._get_test_file_path('generic-egs-case-5_no-stim-costs-specified.txt'),
                params={
                    'Reservoir Stimulation Capital Cost per Fracture Surface Area': 0.87431693989,
                    'Print Output to Console': True,
                },
            )
        )

        cap_costs = r.result['CAPITAL COSTS (M$)']

        # Total cost should remain identical, but injection wells absorb 100% of the cost.
        self.assertAlmostEqual(184, cap_costs['Stimulation costs']['value'], places=0)
        self.assertIsNone(cap_costs['Stimulation costs per well'])

    def test_stimulation_cost_mutually_exclusive_validation(self):
        with self.assertRaises(RuntimeError) as context:
            GeophiresXClient().get_geophires_result(
                ImmutableGeophiresInputParameters(
                    from_file_path=self._get_test_file_path('generic-egs-case-5_no-stim-costs-specified.txt'),
                    params={
                        'Reservoir Stimulation Capital Cost per Fracture Surface Area': 0.87431693989,
                        'Reservoir Stimulation Capital Cost per Injection Well': 5,
                    },
                )
            )
        self.assertIn('Cannot provide both', str(context.exception))

    def test_stimulation_cost_invalid_negative_production_cost(self):
        with self.assertRaises(RuntimeError) as context:
            GeophiresXClient().get_geophires_result(
                ImmutableGeophiresInputParameters(
                    from_file_path=self._get_test_file_path('generic-egs-case-5_no-stim-costs-specified.txt'),
                    params={
                        'Reservoir Stimulation Capital Cost per Production Well': -5,
                    },
                )
            )
        self.assertIn(
            ' Reservoir Stimulation Capital Cost per Production Well outside of valid range', str(context.exception)
        )

    # noinspection PyMethodMayBeStatic
    def _new_model(
        self, input_file: Path | None = None, additional_params: dict[str, Any] | None = None, read_and_calculate=False
    ) -> Model:
        model_args = {'enable_geophires_logging_config': False}

        if input_file is not None:
            if additional_params is not None:
                params = GeophiresInputParameters(from_file_path=input_file, params=additional_params)
                input_file = params.as_file_path()

            model_args['input_file'] = input_file

        stash_cwd = Path.cwd()
        stash_sys_argv = sys.argv

        sys.argv = ['']

        m = Model(**model_args)

        sys.argv = stash_sys_argv
        os.chdir(stash_cwd)

        if read_and_calculate:
            m.read_parameters()
            m.Calculate()

        return m

    def test_surface_plant_capital_cost_adjustment_factor_applies_to_provided_per_kwe_cost(self):
        """https://github.com/NatLabRockies/GEOPHIRES-X/issues/435"""

        def _get_result(adjustment_factor: float) -> GeophiresXResult:
            return GeophiresXClient().get_geophires_result(
                ImmutableGeophiresInputParameters(
                    from_file_path=self._get_test_file_path('generic-egs-case.txt'),
                    params={
                        'Capital Cost for Power Plant for Electricity Generation': 1900,
                        'Surface Plant Capital Cost Adjustment Factor': adjustment_factor,
                    },
                )
            )

        def _plant_cost(r: GeophiresXResult) -> float:
            return r.result['CAPITAL COSTS (M$)']['Surface power plant costs']['value']

        cost_half = _plant_cost(_get_result(0.5))
        cost_default = _plant_cost(_get_result(1.0))
        cost_one_and_half = _plant_cost(_get_result(1.5))

        # Adjustment factor scales cost derived from the provided per-kWe cost
        self.assertAlmostEqual(cost_default * 0.5, cost_half, places=1)
        self.assertAlmostEqual(cost_default * 1.5, cost_one_and_half, places=1)

        self.assertLess(cost_half, cost_default)
        self.assertGreater(cost_one_and_half, cost_default)

    def test_unprovided_ending_sale_price_does_not_cap_escalation(self):
        def input_for_elec_prices(params) -> GeophiresInputParameters:
            return GeophiresInputParameters(
                from_file_path=self._get_test_file_path('../examples/example1.txt'),
                params=dict(
                    {
                        'Starting Electricity Sale Price': 0.10,
                        'Electricity Escalation Rate Per Year': 0.01,
                        'Electricity Escalation Start Year': 0,
                        'Plant Lifetime': 10,
                    },
                    **params,
                ),
            )

        def elec_prices(params) -> list:
            cashflow = (
                GeophiresXClient()
                .get_geophires_result(input_for_elec_prices(params))
                .result['REVENUE & CASHFLOW PROFILE']
            )
            return [row[1] for row in cashflow[2:]]

        prices_unprovided = elec_prices({})
        prices_explicit_max = elec_prices({'Ending Electricity Sale Price': 1.0})

        self.assertEqual(prices_explicit_max, prices_unprovided)
        self.assertGreater(prices_unprovided[-1], prices_unprovided[0])
