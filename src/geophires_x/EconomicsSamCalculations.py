from __future__ import annotations

import logging
from dataclasses import dataclass, field
from math import isnan
from typing import Any

import numpy_financial as npf

from geophires_x.EconomicsSamCashFlow import _SAM_CASH_FLOW_NAN_STR
from geophires_x.EconomicsSamPreRevenue import PreRevenueCostsAndCashflow, _AFTER_TAX_NET_CASH_FLOW_ROW_NAME
from geophires_x.EconomicsUtils import (
    overnight_capital_cost_output_parameter,
    total_capex_parameter_output_parameter,
    royalty_cost_output_parameter,
    after_tax_irr_parameter,
    nominal_discount_rate_parameter,
    wacc_output_parameter,
    moic_parameter,
    project_vir_parameter,
    project_payback_period_parameter,
    investment_tax_credit_output_parameter,
    lcoh_output_parameter,
    lcoc_output_parameter,
)
from geophires_x.GeoPHIRESUtils import is_float, quantity, is_int
from geophires_x.Parameter import OutputParameter
from geophires_x.Units import Units, EnergyCostUnit, CurrencyUnit, convertible_unit

_log = logging.getLogger(__name__)


ROYALTIES_OPEX_CASH_FLOW_LINE_ITEM_KEY = 'O&M production-based expense ($)'


@dataclass
class SamEconomicsCalculations:

    _sam_cash_flow_profile_operational_years: list[list[Any]]
    """
    Operational cash flow profile from SAM financial engine
    """

    pre_revenue_costs_and_cash_flow: PreRevenueCostsAndCashflow

    electricity_plant_frac_of_capex: float = 1.0
    """
    Derived from model.economics.CAPEX_heat_electricity_plant_ratio
    """

    lcoe_nominal: OutputParameter = field(
        default_factory=lambda: OutputParameter(
            UnitType=Units.ENERGYCOST,
            CurrentUnits=EnergyCostUnit.CENTSSPERKWH,
        )
    )

    lcoh_nominal: OutputParameter = field(default_factory=lcoh_output_parameter)
    lcoc_nominal: OutputParameter = field(default_factory=lcoc_output_parameter)

    overnight_capital_cost: OutputParameter = field(default_factory=overnight_capital_cost_output_parameter)

    capex: OutputParameter = field(default_factory=total_capex_parameter_output_parameter)

    _royalties_rate_schedule: list[float] | None = None
    royalties_opex: OutputParameter = field(default_factory=royalty_cost_output_parameter)

    project_npv: OutputParameter = field(
        default_factory=lambda: OutputParameter(
            UnitType=Units.CURRENCY,
            CurrentUnits=CurrencyUnit.MDOLLARS,
        )
    )

    after_tax_irr: OutputParameter = field(default_factory=after_tax_irr_parameter)
    nominal_discount_rate: OutputParameter = field(default_factory=nominal_discount_rate_parameter)
    wacc: OutputParameter = field(default_factory=wacc_output_parameter)
    moic: OutputParameter = field(default_factory=moic_parameter)
    project_vir: OutputParameter = field(default_factory=project_vir_parameter)

    project_payback_period: OutputParameter = field(default_factory=project_payback_period_parameter)

    investment_tax_credit: OutputParameter = field(default_factory=investment_tax_credit_output_parameter)

    capacity_payment_revenue_sources: list[CapacityPaymentRevenueSource] = field(default_factory=list)

    construction_start_calendar_year: int | None = None

    @property
    def _pre_revenue_years_count(self) -> int:
        return len(
            self.pre_revenue_costs_and_cash_flow.pre_revenue_cash_flow_profile_dict[_AFTER_TAX_NET_CASH_FLOW_ROW_NAME]
        )

    @property
    def sam_cash_flow_profile(self) -> list[list[Any]]:
        ret: list[list[Any]] = self._sam_cash_flow_profile_operational_years.copy()
        col_count = len(self._sam_cash_flow_profile_operational_years[0])

        pre_revenue_years_to_insert = self._pre_revenue_years_count - 1

        construction_rows: list[list[Any]] = [
            ['CONSTRUCTION'] + [''] * (len(self._sam_cash_flow_profile_operational_years[0]) - 1)
        ]

        for row_index in range(len(self._sam_cash_flow_profile_operational_years)):
            pre_revenue_row_content = [''] * pre_revenue_years_to_insert
            insert_index = 1

            if row_index == 0:
                for pre_revenue_year in range(pre_revenue_years_to_insert):
                    negative_year_index: int = self._pre_revenue_years_count - 1 - pre_revenue_year
                    pre_revenue_row_content[pre_revenue_year] = f'Year -{negative_year_index}'

                for _, row_ in enumerate(self.pre_revenue_costs_and_cash_flow.pre_revenue_cash_flow_profile):
                    pre_revenue_row = row_.copy()
                    pre_revenue_row.extend([''] * (col_count - len(pre_revenue_row)))
                    construction_rows.append(pre_revenue_row)

            #  TODO zero-vectors for non-construction years e.g. Debt principal payment ($)

            adjusted_row = [ret[row_index][0]] + pre_revenue_row_content + ret[row_index][insert_index:]
            ret[row_index] = adjusted_row

        construction_rows.append([''] * len(self._sam_cash_flow_profile_operational_years[0]))
        for construction_row in reversed(construction_rows):
            ret.insert(1, construction_row)

        if self.construction_start_calendar_year is not None:
            calendar_years = [str(self.construction_start_calendar_year + i) for i in range(len(ret[0]) - 1)]
            ret.insert(1, ['Calendar year', *calendar_years])

        def _get_row_index(row_name_: str) -> int:
            return [it[0] for it in ret].index(row_name_)

        def _get_row(row_name__: str) -> list[Any]:
            for r in ret:
                if r[0] == row_name__:
                    return r[1:]

            raise ValueError(f'Could not find row with name {row_name__}')

        after_tax_cash_flow: list[float] = (
            self.pre_revenue_costs_and_cash_flow.pre_revenue_cash_flow_profile_dict[_AFTER_TAX_NET_CASH_FLOW_ROW_NAME]
            + _get_row('Total after-tax returns ($)')[self._pre_revenue_years_count :]
        )
        after_tax_cash_flow = [float(it) for it in after_tax_cash_flow if is_float(it)]
        irr_row_name = 'After-tax cumulative IRR (%)'
        ret.insert(
            _get_row_index(irr_row_name), ['After-tax net cash flow ($)', *[int(it) for it in after_tax_cash_flow]]
        )

        npv_usd = []
        irr_pct = []
        for year in range(len(after_tax_cash_flow)):
            npv_usd.append(
                round(
                    npf.npv(
                        self.nominal_discount_rate.quantity().to('dimensionless').magnitude,
                        after_tax_cash_flow[: year + 1],
                    )
                )
            )

            year_irr = npf.irr(after_tax_cash_flow[: year + 1]) * 100.0
            irr_pct.append(year_irr if not isnan(year_irr) else _SAM_CASH_FLOW_NAN_STR)

        ret[_get_row_index('After-tax cumulative NPV ($)')] = ['After-tax cumulative NPV ($)'] + npv_usd
        ret[_get_row_index('After-tax cumulative IRR (%)')] = [irr_row_name] + irr_pct

        if self._royalties_rate_schedule is not None:
            ret = self._insert_royalties_rate_schedule(ret)

        ret = self._insert_capacity_payment_line_items(ret)

        ret = self._insert_calculated_levelized_metrics_line_items(ret)

        if self._may_consume_grid_electricity:
            ret = self._adjust_electricity_line_items_for_possible_grid_electricity_consumption(ret)

        return ret

    def _insert_royalties_rate_schedule(self, cf_ret: list[list[Any]]) -> list[list[Any]]:
        ret = cf_ret.copy()

        def _get_row_index(row_name_: str) -> int:
            return [it[0] for it in ret].index(row_name_)

        ret.insert(
            _get_row_index(ROYALTIES_OPEX_CASH_FLOW_LINE_ITEM_KEY),
            [
                *['Royalty rate (%)'],
                *([''] * (self._pre_revenue_years_count)),
                *[
                    quantity(it, 'dimensionless').to(convertible_unit('percent')).magnitude
                    for it in self._royalties_rate_schedule
                ],
            ],
        )

        return ret

    # noinspection PyMethodMayBeStatic
    def _insert_capacity_payment_line_items(self, cf_ret: list[list[Any]]) -> list[list[Any]]:
        if len(self.capacity_payment_revenue_sources) == 0:
            return cf_ret

        ret: list[list[Any]] = cf_ret.copy()

        def _get_row_index(row_name_: str) -> int:
            return [it[0] for it in ret].index(row_name_)

        def _insert_row_before(before_row_name: str, row_name: str, row_content: list[Any]) -> None:
            ret.insert(
                _get_row_index(before_row_name),
                [row_name, *row_content],
            )

        def _insert_blank_line_before(before_row_name: str) -> None:
            _insert_row_before(before_row_name, '', ['' for _it in ret[_get_row_index(before_row_name)]][1:])

        REVENUE_CATEGORY_ROW_NAME = 'REVENUE'
        CAPACITY_PAYMENT_REVENUE_ROW_NAME = 'Capacity payment revenue ($)'

        _insert_blank_line_before('Salvage value ($)')
        _insert_blank_line_before(CAPACITY_PAYMENT_REVENUE_ROW_NAME)

        def _for_operational_years(_row: list[Any]) -> list[Any]:
            return [*([''] * (self._pre_revenue_years_count - 1)), 0, *_row]

        for i, capacity_payment_revenue_source in enumerate(self.capacity_payment_revenue_sources):
            if capacity_payment_revenue_source.amount_provided_label is not None:
                _insert_row_before(
                    REVENUE_CATEGORY_ROW_NAME,
                    capacity_payment_revenue_source.amount_provided_label,
                    _for_operational_years(capacity_payment_revenue_source.amount_provided),
                )
                _insert_blank_line_before(REVENUE_CATEGORY_ROW_NAME)

            revenue_row_name = f'{capacity_payment_revenue_source.name} revenue ($)'
            _insert_row_before(
                CAPACITY_PAYMENT_REVENUE_ROW_NAME,
                revenue_row_name,
                _for_operational_years(capacity_payment_revenue_source.revenue_usd),
            )

            if capacity_payment_revenue_source.price_label is not None:
                _insert_row_before(
                    revenue_row_name,
                    capacity_payment_revenue_source.price_label.replace('USD', '$'),
                    capacity_payment_revenue_source.price,
                )

            if len(self.capacity_payment_revenue_sources) > 1 and i < len(self.capacity_payment_revenue_sources) - 1:
                _insert_row_before(
                    CAPACITY_PAYMENT_REVENUE_ROW_NAME,
                    'plus:',
                    ['' for _it in ret[_get_row_index(revenue_row_name)]][1:],
                )

        if len(self.capacity_payment_revenue_sources) > 0:
            _insert_row_before(
                CAPACITY_PAYMENT_REVENUE_ROW_NAME, 'equals:', ['' for _it in ret[_get_row_index(revenue_row_name)]][1:]
            )

        return ret

    def _insert_calculated_levelized_metrics_line_items(self, cf_ret: list[list[Any]]) -> list[list[Any]]:
        ret = cf_ret.copy()

        def _get_row_index(row_name_: str, raise_exception_if_not_present: bool = True) -> int:
            try:
                return [it[0] for it in ret].index(row_name_)
            except ValueError as ve:
                if raise_exception_if_not_present:
                    raise ve
                else:
                    return -1

        def _get_row_indexes(row_name_: str, after_row_name: str | None = None) -> list[int]:
            after_criteria_met: bool = True if after_row_name is None else False
            indexes = []
            for idx, _row_name_ in enumerate([it[0] for it in ret]):
                if _row_name_ == after_row_name:
                    after_criteria_met = True

                if _row_name_ == row_name_ and after_criteria_met:
                    indexes.append(idx)

            return indexes

        def _get_row_index_after(row_name_: str, after_row_name: str) -> int:
            return _get_row_indexes(row_name_, after_row_name=after_row_name)[0]

        def _insert_row_before(before_row_name: str, row_name: str, row_content: list[Any] | None) -> None:
            if row_content is None:
                row_content = ['' for _it in ret[_get_row_index(before_row_name)]][1:]

            ret.insert(
                _get_row_index(before_row_name),
                [row_name, *row_content],
            )

        def _insert_blank_line_before(before_row_name: str) -> None:
            _insert_row_before(before_row_name, '', ['' for _it in ret[_get_row_index(before_row_name)]][1:])

        def _calculate_pv_year_0(cash_flow_array: list) -> int:
            """Calculate the absolute present value at Year 0 for a cash flow array using npf.npv."""
            return abs(
                round(
                    npf.npv(
                        self.nominal_discount_rate.quantity().to('dimensionless').magnitude,
                        cash_flow_array,
                    )
                )
            )

        after_tax_lcoe_and_ppa_price_header_row_title = 'AFTER-TAX LCOE AND PPA PRICE'

        # --- Backfill annual costs ---
        # Pre-revenue years use after-tax net cash flow; operational years use SAM's annual costs.
        annual_costs_usd_row_name = 'Annual costs ($)'
        annual_costs = cf_ret[_get_row_index(annual_costs_usd_row_name)].copy()
        after_tax_net_cash_flow_usd = cf_ret[_get_row_index('After-tax net cash flow ($)')]

        annual_costs_backfilled = [
            *after_tax_net_cash_flow_usd[1 : (self._pre_revenue_years_count + 1)],
            *annual_costs[(self._pre_revenue_years_count + 1) :],
        ]

        ret[_get_row_index(annual_costs_usd_row_name)][1:] = annual_costs_backfilled

        ppa_revenue_row_name = 'PPA revenue ($)'
        ppa_revenue_row_index = _get_row_index_after(
            ppa_revenue_row_name, after_tax_lcoe_and_ppa_price_header_row_title
        )
        year_0_ppa_revenue: float = ret[ppa_revenue_row_index][self._pre_revenue_years_count]
        if year_0_ppa_revenue != 0.0:
            # Shouldn't happen
            _log.warning(f'PPA revenue in Year 0 ({year_0_ppa_revenue}) is not zero, this is unexpected.')

        ret[ppa_revenue_row_index][1 : self._pre_revenue_years_count] = [year_0_ppa_revenue] * (
            self._pre_revenue_years_count - 1
        )

        electricity_to_grid_kwh_row_name = 'Electricity to grid (kWh)'
        electricity_to_grid = cf_ret[_get_row_index(electricity_to_grid_kwh_row_name)].copy()
        electricity_to_grid_backfilled = [
            0 if it == '' else (int(it) if is_int(it) else it) for it in electricity_to_grid[1:]
        ]

        electricity_to_grid_kwh_row_index = _get_row_index_after(
            electricity_to_grid_kwh_row_name, after_tax_lcoe_and_ppa_price_header_row_title
        )
        ret[electricity_to_grid_kwh_row_index][1:] = electricity_to_grid_backfilled

        # --- PV of annual costs at Year 0 ---
        pv_costs_year_0 = _calculate_pv_year_0(annual_costs_backfilled)

        pv_of_annual_costs_row_name = 'Present value of annual costs ($)'
        pv_of_annual_costs_row_index = _get_row_index(pv_of_annual_costs_row_name)
        ret[pv_of_annual_costs_row_index][1:] = [
            pv_costs_year_0,
            *([''] * (self._pre_revenue_years_count - 1)),
        ]

        # --- PV of annual energy costs (electrical portion) ---
        pv_of_annual_energy_costs_row_name = 'Present value of annual energy costs ($)'
        pv_of_annual_energy_costs_at_year_0_usd = int(round(pv_costs_year_0 * self.electricity_plant_frac_of_capex))
        _insert_row_before(
            'Present value of annual energy nominal (kWh)',
            pv_of_annual_energy_costs_row_name,
            [
                pv_of_annual_energy_costs_at_year_0_usd,
            ],
        )
        _insert_blank_line_before(pv_of_annual_energy_costs_row_name)

        # --- PV of electricity to grid at Year 0 ---
        pv_electricity_to_grid_year_0_kwh = _calculate_pv_year_0(electricity_to_grid_backfilled)

        pv_of_annual_energy_row_name = 'Present value of annual energy nominal (kWh)'
        for pv_of_annual_energy_row_index in _get_row_indexes(pv_of_annual_energy_row_name):
            ret[pv_of_annual_energy_row_index][1:] = [
                pv_electricity_to_grid_year_0_kwh,
                *([''] * (self._pre_revenue_years_count - 1)),
            ]

        # --- LCOE nominal ---
        def backfill_lcoe_nominal() -> None:
            pv_energy_costs_year_0_usd = pv_costs_year_0 * self.electricity_plant_frac_of_capex

            lcoe_nominal_entry: float | str = 'NaN'
            if pv_electricity_to_grid_year_0_kwh != 0:
                lcoe_nominal_entry = pv_energy_costs_year_0_usd * 100 / pv_electricity_to_grid_year_0_kwh

            lcoe_nominal_row_name = 'LCOE Levelized cost of energy nominal (cents/kWh)'
            lcoe_nominal_row_index = _get_row_index(lcoe_nominal_row_name)

            if isinstance(lcoe_nominal_entry, float):
                lcoe_nominal_entry = round(lcoe_nominal_entry, 2)

            ret[lcoe_nominal_row_index][1:] = [
                lcoe_nominal_entry,
                *([None] * (self._pre_revenue_years_count - 1)),
            ]

        backfill_lcoe_nominal()

        # --- LPPA metrics ---
        def backfill_lppa_metrics() -> None:
            pv_of_ppa_revenue_row_index = _get_row_index_after(
                'Present value of PPA revenue ($)', after_tax_lcoe_and_ppa_price_header_row_title
            )
            first_year_pv_of_ppa_revenue_usd = round(
                npf.npv(
                    self.nominal_discount_rate.quantity().to('dimensionless').magnitude,
                    ret[ppa_revenue_row_index][1:],
                )
            )
            ret[pv_of_ppa_revenue_row_index][1:] = [
                first_year_pv_of_ppa_revenue_usd,
                *([None] * (self._pre_revenue_years_count - 1)),
            ]

            ppa_price_row_index = _get_row_index('PPA price (cents/kWh)')
            year_0_ppa_price: float = ret[ppa_price_row_index][self._pre_revenue_years_count]
            if year_0_ppa_price != 0.0:
                # Shouldn't happen
                _log.warning(f'PPA price in Year 0 ({year_0_ppa_price}) is not zero, this is unexpected.')

            # TODO (maybe)
            # ppa_revenue_all_years = [
            #     *([year_0_ppa_price] * (self._pre_revenue_years_count - 1)),
            #     *ret[ppa_price_row_index][self._pre_revenue_years_count :],
            # ]
            # ret[_get_row_index('PPA price (cents/kWh)')][1:] = ppa_revenue_all_years

            first_year_lppa_cents_per_kwh: float | str = 'NaN'
            first_year_pv_annual_energy = ret[_get_row_index(pv_of_annual_energy_row_name)][1]

            if (
                isinstance(first_year_pv_annual_energy, int) or isinstance(first_year_pv_annual_energy, float)
            ) and first_year_pv_annual_energy != 0.0:
                # Note: expected to be same in all pre-revenue years since both price and revenue are zero until COD
                first_year_lppa_cents_per_kwh = round(
                    first_year_pv_of_ppa_revenue_usd * 100.0 / first_year_pv_annual_energy, 2
                )

            lppa_row_name = 'LPPA Levelized PPA price nominal (cents/kWh)'
            ret[_get_row_index(lppa_row_name)][1:] = [
                first_year_lppa_cents_per_kwh,
                *([None] * self._pre_revenue_years_count),
            ]

        backfill_lppa_metrics()

        # --- Non-electricity levelized metrics (LCOH, LCOC) ---
        def insert_non_electricity_levelized_metrics(
            amount_provided_kwh_row_name: str,  # e.g. 'Heat provided (kWh)'
            amount_provided_unit: str,  # e.g. 'MMBTU'
            levelized_cost_nominal_row_base_name: str,  # e.g. 'LCOH Levelized cost of heating nominal'
            pv_annual_non_elec_type_costs_row_name: str,  # e.g. 'Present value of annual heat costs ($)'
            pv_of_annual_amount_provided_row_base_name: str,  # e.g. 'Present value of annual heat provided'
        ) -> None:

            levelized_cost_nominal_row_name = f'{levelized_cost_nominal_row_base_name} ($/{amount_provided_unit})'

            amount_provided_kwh_row_index = _get_row_index(
                amount_provided_kwh_row_name, raise_exception_if_not_present=False
            )
            if amount_provided_kwh_row_index == -1:
                return  # No heat provided row, nothing to do

            # TODO maybe duplicate amount provided row after after_tax_lcoe_and_ppa_price_header_row_title to mirror
            #   electricity convention
            # amount_provided_kwh_row_index = _get_row_index_after(
            #     amount_provided_kwh_row_name, after_tax_lcoe_and_ppa_price_header_row_title
            # )

            amount_provided = cf_ret[amount_provided_kwh_row_index].copy()
            amount_provided_backfilled = [
                0 if it == '' else (int(it) if is_int(it) else it) for it in amount_provided[1:]
            ]
            # PV of amount provided (e.g. heat) at Year 0
            pv_amount_provided_year_0_kwh = _calculate_pv_year_0(amount_provided_backfilled)

            # Thermal portion of PV of annual costs at Year 0
            pv_non_elec_costs_year_0_usd = pv_costs_year_0 * (1.0 - self.electricity_plant_frac_of_capex)

            # Levelized cost = thermal costs / amount provided (converted to target unit)
            levelized_cost_nominal_entry: float | str = 'NaN'
            if pv_amount_provided_year_0_kwh != 0:
                levelized_cost_nominal_entry = (
                    pv_non_elec_costs_year_0_usd
                    / quantity(pv_amount_provided_year_0_kwh, 'kWh').to(amount_provided_unit).magnitude
                )

            # Insert new row if levelized cost row does not exist (yet)
            levelized_cost_nominal_row_index = _get_row_index(
                levelized_cost_nominal_row_name, raise_exception_if_not_present=False
            )

            if levelized_cost_nominal_row_index == -1:
                _insert_row_before('PROJECT STATE INCOME TAXES', levelized_cost_nominal_row_name, None)
                _insert_blank_line_before('PROJECT STATE INCOME TAXES')
                levelized_cost_nominal_row_index = _get_row_index(levelized_cost_nominal_row_name)

            if isinstance(levelized_cost_nominal_entry, float):
                levelized_cost_nominal_entry = round(levelized_cost_nominal_entry, 2)

            ret[levelized_cost_nominal_row_index][1:] = [
                levelized_cost_nominal_entry,
                *([None] * (self._pre_revenue_years_count - 1)),
            ]

            # Insert new row if PV of non-electricity costs row does not exist (yet)
            pv_annual_non_elec_type_costs_row_index = _get_row_index(
                pv_annual_non_elec_type_costs_row_name, raise_exception_if_not_present=False
            )

            if pv_annual_non_elec_type_costs_row_index == -1:
                _insert_row_before(levelized_cost_nominal_row_name, pv_annual_non_elec_type_costs_row_name, None)
                pv_annual_non_elec_type_costs_row_index = _get_row_index(pv_annual_non_elec_type_costs_row_name)

            pv_annual_non_elec_type_costs_entry = pv_non_elec_costs_year_0_usd
            if isinstance(pv_annual_non_elec_type_costs_entry, float):
                pv_annual_non_elec_type_costs_entry = int(round(pv_annual_non_elec_type_costs_entry, 2))

            ret[pv_annual_non_elec_type_costs_row_index][1:] = [
                pv_annual_non_elec_type_costs_entry,
                *([None] * (self._pre_revenue_years_count - 1)),
            ]

            pv_of_annual_amount_provided_unit: str = amount_provided_unit
            pv_of_annual_amount_provided_row_name = (
                f'{pv_of_annual_amount_provided_row_base_name} ({pv_of_annual_amount_provided_unit})'
            )
            # Insert new row if PV of amount provided row does not exist (yet)
            pv_of_annual_amount_provided_row_index = _get_row_index(
                pv_of_annual_amount_provided_row_name, raise_exception_if_not_present=False
            )

            if pv_of_annual_amount_provided_row_index == -1:
                _insert_row_before(levelized_cost_nominal_row_name, pv_of_annual_amount_provided_row_name, None)
                pv_of_annual_amount_provided_row_index = _get_row_index(pv_of_annual_amount_provided_row_name)

            pv_annual_amount_provided_entry = pv_amount_provided_year_0_kwh
            if any(isinstance(pv_annual_amount_provided_entry, it) for it in [int, float]):
                pv_annual_amount_provided_entry = int(
                    round(
                        quantity(pv_annual_amount_provided_entry, 'kWh')
                        .to(pv_of_annual_amount_provided_unit)
                        .magnitude,
                        2,
                    )
                )

            ret[pv_of_annual_amount_provided_row_index][1:] = [
                pv_annual_amount_provided_entry,
                *([None] * (self._pre_revenue_years_count - 1)),
            ]

        def insert_lcoh_metrics():
            insert_non_electricity_levelized_metrics(
                amount_provided_kwh_row_name='Heat provided (kWh)',
                amount_provided_unit='MMBTU',  # TODO maybe should be derived from LCOH preferred units
                levelized_cost_nominal_row_base_name=f'LCOH Levelized cost of heating nominal',
                pv_annual_non_elec_type_costs_row_name='Present value of annual heat costs ($)',
                pv_of_annual_amount_provided_row_base_name=f'Present value of annual heat provided',
            )

        insert_lcoh_metrics()

        def insert_lcoc_metrics():
            insert_non_electricity_levelized_metrics(
                # See relevant TODO in geophires_x.EconomicsSam._get_capacity_payment_revenue_sources re: unit
                amount_provided_kwh_row_name='Cooling provided (kWh)',
                amount_provided_unit='MMBTU',  # TODO maybe should be derived from LCOC preferred units
                levelized_cost_nominal_row_base_name=f'LCOC Levelized cost of cooling nominal',
                pv_annual_non_elec_type_costs_row_name='Present value of annual cooling costs ($)',
                pv_of_annual_amount_provided_row_base_name=f'Present value of annual cooling provided',
            )

        insert_lcoc_metrics()

        return ret

    @property
    def _may_consume_grid_electricity(self) -> bool:
        """
        TODO maybe should be passed in explicitly instead of this potentially fragile derivation/assumption
        """

        try:
            elec_to_grid_kwh_index = [it[0] for it in self._sam_cash_flow_profile_operational_years].index(
                'Electricity to grid (kWh)'
            )
        except ValueError:
            # Shouldn't happen (unless SAM financial engine stops including the line item, which would be
            # backwards-incompatible)
            return False

        return all(
            float(it) == 0.0 if is_float(it) else it == ''
            for it in self._sam_cash_flow_profile_operational_years[elec_to_grid_kwh_index][1:]
        )

    # noinspection PyMethodMayBeStatic
    def _adjust_electricity_line_items_for_possible_grid_electricity_consumption(
        self, cf_ret: list[list[Any]]
    ) -> list[list[Any]]:
        """
        Remove electricity line items that are not parameterized into SAM, to avoid inaccurately displaying the
        default 0 values. For example, direct-use heat end-use requires pumping power that comes from grid electricity.
        The cost of this electricity is accounted for in GEOPHIRES OPEX calculations, prior to SAM calculations.

        TODO to parameterize relevant factors into SAM and don't remove their line items
        """

        ret = cf_ret.copy()

        def _get_row_index(row_name_: str) -> int:
            return [it[0] for it in ret].index(row_name_)

        def _remove_line_item(row_name_: str) -> None:
            idx = _get_row_index(row_name_)
            row = ret[idx]
            if any(it != '' and (is_float(it) and float(it) != 0.0) for it in row[1:]):
                raise RuntimeError(
                    f'Line item "{row[0]}" has non-zero values. '
                    f'This is unexpected and probably indicates an internal error or bug.'
                )

            ret.pop(idx)

        for line_item in ['Electricity from grid (kWh)', 'Electricity to grid net (kWh)', 'Electricity purchase ($)']:
            _remove_line_item(line_item)

        return ret

    @property
    def sam_after_tax_net_cash_flow_all_years(self) -> list[float]:
        return _after_tax_net_cash_flow_all_years(self.sam_cash_flow_profile, self._pre_revenue_years_count)


@dataclass
class CapacityPaymentRevenueSource:
    name: str

    revenue_usd: list[float]

    amount_provided_label: str | None = None
    amount_provided: list[float] | None = None

    price_label: str | None = None
    price: list[float] | None = None


def _after_tax_net_cash_flow_all_years(cash_flow: list[list[Any]], pre_revenue_years_count: int) -> list[float]:
    return _net_cash_flow_all_years(cash_flow, pre_revenue_years_count, tax_qualifier='after-tax')


def _net_cash_flow_all_years(
    cash_flow: list[list[Any]], pre_revenue_years_count: int, tax_qualifier='after-tax'
) -> list[float]:
    if tax_qualifier not in ['after-tax', 'pre-tax']:
        raise ValueError(f'Invalid tax qualifier: {tax_qualifier}')

    def _get_row(row_name__: str) -> list[Any]:
        for r in cash_flow:
            if r[0] == row_name__:
                return r[1:]

        raise ValueError(f'Could not find row with name {row_name__}')

    def _construction_returns_row(_construction_tax_qualifier: str) -> list[Any]:
        returns_row_name = (
            f'Total {_construction_tax_qualifier} returns [construction] ($)'
            if tax_qualifier == 'pre-tax'
            else f'After-tax net cash flow [construction] ($)'
        )
        return _get_row(returns_row_name)

    try:
        construction_returns_row = _construction_returns_row(tax_qualifier)
    except ValueError as ve:
        if tax_qualifier == 'pre-tax':
            # TODO log warning
            construction_returns_row = _construction_returns_row('after-tax')
        else:
            raise ve

    return [
        *[float(it) for it in construction_returns_row if is_float(it)],
        *[float(it) for it in _get_row(f'Total {tax_qualifier} returns ($)')[pre_revenue_years_count:] if is_float(it)],
    ]
