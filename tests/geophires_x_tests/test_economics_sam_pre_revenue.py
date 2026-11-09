from __future__ import annotations

from base_test_case import BaseTestCase

# noinspection PyProtectedMember
from geophires_x.EconomicsSamCashFlow import _get_logger
from geophires_x.EconomicsSamPreRevenue import PreRevenueCostsAndCashflow

# noinspection PyProtectedMember
from geophires_x.EconomicsSamPreRevenue import _calculate_pre_revenue_costs_and_cashflow
from geophires_x.EconomicsSamPreRevenue import adjust_phased_schedule_to_new_length


class EconomicsSamPreRevenueTestCase(BaseTestCase):

    def test_adjust_phased_schedule_to_new_length(self) -> None:
        def asrt(original_schedule: list[float], new_length: int, expected_schedule: list[float]) -> None:
            adjusted_schedule = adjust_phased_schedule_to_new_length(original_schedule, new_length)
            self.assertListAlmostEqual(expected_schedule, adjusted_schedule, percent=3)

        # fmt:off
        asrt(
            [1.],
            2,
            [0.5, 0.5]
        )

        asrt(
            [0.5, 0.5],
            4,
            [0.25, 0.25, 0.25, 0.25]
        )

        asrt(
            [0.25, 0.25, 0.25, 0.25],
            2,
            [0.5, 0.5],
        )

        asrt(
            [0.5, 0.25, 0.25],
            6,
            [0.25] * 2 + [0.1278] * 4
        )
        # fmt:on

    def test_calculate_pre_revenue_costs_and_cashflow(self) -> None:
        _log = _get_logger()
        pre_rev: PreRevenueCostsAndCashflow = _calculate_pre_revenue_costs_and_cashflow(
            100_000_000, 3, [0.25, 0.25, 0.5], 0.1, 0.05, 0.5, 1, _log
        )

        def _get_row(row_name: str) -> list[float]:
            cf_line_item = next(row for row in pre_rev.pre_revenue_cash_flow_profile if row[0] == row_name)[1:]

            # Ensure dict property consistency
            self.assertListEqual(
                cf_line_item, pre_rev.pre_revenue_cash_flow_profile_dict[row_name.replace('[construction] ', '')]
            )

            return cf_line_item

        self.assertListEqual([-25e6, -25e6, -50e6], _get_row('Overnight capital expenditure [construction] ($)'))

    def test_construction_loan_upfront_fee(self) -> None:
        _log = _get_logger()
        total_capex = 100_000_000.0
        upfront_fee_rate = 0.02  # 2%

        # 3 years construction, capex [25M, 25M, 50M], debt_fraction=0.5, debt starts year 1 (index 1)
        pre_rev_base: PreRevenueCostsAndCashflow = _calculate_pre_revenue_costs_and_cashflow(
            total_capex, 3, [0.25, 0.25, 0.5], 0.1, 0.05, 0.5, 1, _log, construction_loan_upfront_fee=0.0
        )
        pre_rev_with_fee: PreRevenueCostsAndCashflow = _calculate_pre_revenue_costs_and_cashflow(
            total_capex, 3, [0.25, 0.25, 0.5], 0.1, 0.05, 0.5, 1, _log, construction_loan_upfront_fee=upfront_fee_rate
        )

        self.assertEqual(pre_rev_base.upfront_fee_usd, 0.0)
        self.assertGreater(pre_rev_with_fee.upfront_fee_usd, 0.0)

        # Total debt drawn is 50% of nominal capex across the debt financing period
        expected_diff = pre_rev_with_fee.upfront_fee_usd
        self.assertAlmostEqual(
            pre_rev_with_fee.construction_financing_cost_usd,
            pre_rev_base.construction_financing_cost_usd + expected_diff,
            places=2,
        )
        self.assertAlmostEqual(
            pre_rev_with_fee.total_installed_cost_usd,
            pre_rev_base.total_installed_cost_usd + expected_diff,
            places=2,
        )

        def _get_row(profile: list[list[float | str]], row_name: str) -> list[float]:
            return next(row for row in profile if row[0] == row_name)[1:]

        upfront_fee_row = _get_row(
            pre_rev_with_fee.pre_revenue_cash_flow_profile, 'Debt up-front fee [construction] ($)'
        )
        # Year 0 has 0 debt draw, Year 1 and 2 draw debt and incur fee
        self.assertEqual(upfront_fee_row[0], 0.0)
        self.assertLess(upfront_fee_row[1], 0.0)
        self.assertLess(upfront_fee_row[2], 0.0)
        self.assertAlmostEqual(sum([-x for x in upfront_fee_row]), pre_rev_with_fee.upfront_fee_usd, delta=1.0)
