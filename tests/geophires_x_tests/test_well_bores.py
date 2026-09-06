from __future__ import annotations

from base_test_case import BaseTestCase

# ruff: noqa: I001  # Successful module initialization is dependent on this specific import order.

# noinspection PyProtectedMember
from geophires_x_client import GeophiresInputParameters
from geophires_x_client import GeophiresXClient
from geophires_x_client import GeophiresXResult


class WellBoresTestCase(BaseTestCase):

    def test_number_of_doublets(self):
        r_prod_inj: GeophiresXResult = self._get_result(
            {
                'Number of Production Wells': 10,
                'Number of Injection Wells': 10,
            }
        )

        r_doublets: GeophiresXResult = self._get_result(
            {
                'Number of Doublets': 10,
            }
        )

        self.assertEqual(self._prod_inj_lcoe_production(r_doublets), self._prod_inj_lcoe_production(r_prod_inj))

    def test_number_of_doublets_validation(self):
        with self.assertRaises(RuntimeError):
            self._get_result(
                {
                    'Number of Production Wells': 10,
                    'Number of Injection Wells': 10,
                    'Number of Doublets': 10,
                }
            )

        with self.assertRaises(RuntimeError):
            self._get_result(
                {
                    'Number of Production Wells': 10,
                    'Number of Doublets': 10,
                }
            )

        with self.assertRaises(RuntimeError):
            self._get_result(
                {
                    'Number of Injection Wells': 10,
                    'Number of Doublets': 10,
                }
            )

    def test_number_of_doublets_non_integer(self):
        """
        Non-integer values are relevant for MC simulations, since distributions produce floats, and we want
        Number of Doublets to be compatible with MC.
        """

        prod_inj_lcoe = self._prod_inj_lcoe_production(
            self._get_result(
                {
                    'Number of Doublets': 40.7381,
                }
            )
        )

        self.assertEqual(prod_inj_lcoe[0], 40)
        self.assertEqual(prod_inj_lcoe[1], 40)

        prod_inj_lcoe_2 = self._prod_inj_lcoe_production(
            self._get_result(
                {
                    'Number of Doublets': 199.2,
                }
            )
        )

        self.assertEqual(prod_inj_lcoe_2[0], 199)
        self.assertEqual(prod_inj_lcoe_2[1], 199)

    def test_number_of_injection_wells_per_production_well(self):
        r_ratio: GeophiresXResult = self._get_result(
            {
                'Number of Production Wells': 63,
                'Number of Injection Wells per Production Well': 0.666,  # 3:2 ratio
            }
        )

        r_explicit_counts: GeophiresXResult = self._get_result(
            {'Number of Production Wells': 63, 'Number of Injection Wells': 42}
        )

        self.assertEqual(self._prod_inj_lcoe_production(r_explicit_counts), self._prod_inj_lcoe_production(r_ratio))

        self.assertEqual(
            self._prod_inj_lcoe_production(
                self._get_result(
                    {
                        'Number of Production Wells': 2,  # default value
                        'Number of Injection Wells per Production Well': 3,
                    }
                )
            ),
            self._prod_inj_lcoe_production(self._get_result({'Number of Injection Wells per Production Well': 3})),
        )

        with self.assertRaises(RuntimeError):
            self._get_result(
                {
                    'Number of Production Wells': 63,
                    'Number of Injection Wells per Production Well': 0.6666,  # 3:2 ratio
                    'Number of Injection Wells': 42,
                }
            )

        with self.assertRaises(RuntimeError):
            self._get_result(
                {
                    'Number of Production Wells': 63,
                    'Number of Injection Wells per Production Well': 0.6666,  # 3:2 ratio
                    'Number of Doublets': 52,
                }
            )

    def test_multilateral_sections_per_vertical_section(self):
        laterals_params = {
            'Well Geometry Configuration': 4,
            'Number of Production Wells': 2,
            'Number of Injection Wells': 2,
        }

        r_per_vertical_section: GeophiresXResult = self._get_result(
            {**laterals_params, 'Number of Multilateral Sections per Vertical Section': 3}
        )

        # 2 producers + 2 injectors with 3 laterals per well is equivalent to 2 * 2 * 3 = 12 total sections.
        r_total_sections: GeophiresXResult = self._get_result(
            {**laterals_params, 'Number of Multilateral Sections': 12}
        )

        self.assertEqual(self._lateral_costs(r_total_sections), self._lateral_costs(r_per_vertical_section))

        # Total sections (and therefore total lateral cost) scale with the number of vertical sections, whereas the
        # cost per section does not.
        r_double_wells: GeophiresXResult = self._get_result(
            {
                'Well Geometry Configuration': 4,
                'Number of Production Wells': 4,
                'Number of Injection Wells': 4,
                'Number of Multilateral Sections per Vertical Section': 3,
            }
        )

        self.assertEqual(self._lateral_costs(r_double_wells)[1], self._lateral_costs(r_per_vertical_section)[1])
        self.assertGreater(self._lateral_costs(r_double_wells)[0], self._lateral_costs(r_per_vertical_section)[0])

    def test_multilateral_sections_per_vertical_section_validation(self):
        with self.assertRaises(RuntimeError):
            self._get_result(
                {
                    'Well Geometry Configuration': 4,
                    'Number of Multilateral Sections': 12,
                    'Number of Multilateral Sections per Vertical Section': 3,
                }
            )

    def test_multilateral_sections_per_vertical_section_unsupported_by_ags(self):
        """
        AGS/CLGS models do not support deriving the total number of multilateral sections from a
        per-vertical-section value.
        """

        with self.assertRaises(RuntimeError):
            GeophiresXClient().get_geophires_result(
                GeophiresInputParameters(
                    from_file_path=self._get_test_file_path(
                        '../examples/Wanju_Yuan_Closed-Loop_Geothermal_Energy_Recovery.txt'
                    ),
                    params={'Number of Multilateral Sections per Vertical Section': 1},
                )
            )

    def test_redrilling_thermal_drawdown_dominates(self):
        """
        Verify that if thermal drawdown triggers before well integrity failure,
        the redrilling count reflects the thermal limit.
        """
        max_drawdown = 0.02
        result = self._get_result(
            {
                'Reservoir Model': 4,
                'Drawdown Parameter': 0.01,
                'Plant Lifetime': 30,
                'Maximum Drawdown': max_drawdown,
                'Well Integrity Maximum Lifetime': 50.0,
            }
        )

        redrill_events = int(result.result['ENGINEERING PARAMETERS']['Number of times redrilling']['value'])
        self.assertGreater(redrill_events, 2)

        profile = result.power_generation_profile
        header = profile[0]
        drawdown_idx = next(i for i, h in enumerate(header) if 'THERMAL DRAWDOWN' in str(h).upper())
        drawdowns = [float(row[drawdown_idx]) for row in profile[1:]]

        # Verify that drawdown hits the minimum defined by max drawdown param the same number of times as redrilling.
        # Each reset (value jumps back up to ~1.0) indicates a redrill event triggered by hitting the threshold.
        # We use a difference > 0.005 to filter out minor natural year-over-year increases (~0.001) that can occur
        # early in analytical thermal profiles.
        resets = sum(1 for i in range(len(drawdowns) - 1) if drawdowns[i + 1] - drawdowns[i] > 0.005)
        self.assertEqual(redrill_events, resets)

    def test_redrilling_well_integrity_dominates(self):
        """
        Verify that if well integrity failure triggers before thermal drawdown,
        the redrilling count reflects the chronological integrity limit.
        """
        max_drawdown = 0.90
        result = self._get_result(
            {
                'Reservoir Model': 4,
                'Drawdown Parameter': 0.01,
                'Plant Lifetime': 30,
                'Maximum Drawdown': max_drawdown,
                'Well Integrity Maximum Lifetime': 7.0,
            }
        )

        redrill_events = int(result.result['ENGINEERING PARAMETERS']['Number of times redrilling']['value'])
        self.assertEqual(redrill_events, 4)

        profile = result.power_generation_profile
        header = profile[0]
        drawdown_idx = next(i for i, h in enumerate(header) if 'THERMAL DRAWDOWN' in str(h).upper())
        drawdowns = [float(row[drawdown_idx]) for row in profile[1:]]

        # Verify that drawdown stays above the maximum drawdown value throughout project lifetime
        threshold = 1.0 - max_drawdown
        min_drawdown = min(drawdowns)
        self.assertGreater(min_drawdown, threshold)

        # Verify the chronological resets occurred the correct number of times.
        # We use a difference > 0.005 to filter out minor natural year-over-year increases.
        resets = sum(1 for i in range(len(drawdowns) - 1) if drawdowns[i + 1] - drawdowns[i] > 0.005)
        self.assertEqual(redrill_events, resets)

    def test_redrilling_no_triggers(self):
        """
        Verify that if neither threshold is reached before project end,
        redrilling is 0 (or not triggered).
        """
        result = self._get_result(
            {
                'Reservoir Model': 4,
                'Drawdown Parameter': 0.01,
                'Plant Lifetime': 30,
                'Maximum Drawdown': 0.90,
                'Well Integrity Maximum Lifetime': 40.0,
            }
        )

        summary = result.result.get('ENGINEERING PARAMETERS', {})
        if 'Number of times redrilling' in summary:
            redrill_events = int(summary['Number of times redrilling']['value'])
            self.assertEqual(0, redrill_events)

    def test_redrilling_examples_equivalence(self) -> None:
        """
        example13 and example13b_well-integrity are expected to have identical results
        with the only difference being whether redrilling is triggered by drawdown or well integrity.
        """

        def _san(r: GeophiresXResult) -> tuple[int, int, float, float]:
            return self._sanitize_nan(self._strip_metadata(r))

        drawdown_example: GeophiresXResult = _san(
            GeophiresXResult(self._get_test_file_path('../examples/example13.out'))
        )
        well_integrity_example: GeophiresXResult = _san(
            GeophiresXResult(self._get_test_file_path('../examples/example13b_well-integrity.out'))
        )
        self.assertDictEqual(
            drawdown_example.result,
            well_integrity_example.result,
        )

    # noinspection PyMethodMayBeStatic
    def _get_result(self, _params) -> GeophiresXResult:
        params = GeophiresInputParameters(
            {'Reservoir Depth': 5, 'Gradient 1': 74, 'Power Plant Type': 2, 'Maximum Temperature': 600, **_params}
        )
        return GeophiresXClient().get_geophires_result(params)

    # noinspection PyMethodMayBeStatic
    def _lateral_costs(self, _r: GeophiresXResult) -> tuple[float, float]:
        capital_costs = _r.result['CAPITAL COSTS (M$)']
        return (
            capital_costs['Drilling and completion costs']['value'],
            capital_costs['Drilling and completion costs per non-vertical section']['value'],
        )

    # noinspection PyMethodMayBeStatic
    def _prod_inj_lcoe_production(self, _r: GeophiresXResult) -> tuple[int, int, float, float]:
        return (
            _r.result['ENGINEERING PARAMETERS']['Number of Production Wells']['value'],
            _r.result['ENGINEERING PARAMETERS']['Number of Injection Wells']['value'],
            _r.result['SUMMARY OF RESULTS']['Electricity breakeven price']['value'],
            _r.result['SURFACE EQUIPMENT SIMULATION RESULTS']['Average Net Electricity Generation']['value'],
        )
