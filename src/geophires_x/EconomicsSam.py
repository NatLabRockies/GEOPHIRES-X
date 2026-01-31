from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache
from math import isnan
from pathlib import Path
from typing import Any

from decimal import Decimal

import numpy as np
import numpy_financial as npf

# noinspection PyPackageRequirements
from PySAM import CustomGeneration

# noinspection PyPackageRequirements
from PySAM import Grid

# noinspection PyPackageRequirements
from PySAM import Singleowner

# noinspection PyPackageRequirements
import PySAM.Utilityrate5 as UtilityRate
from pint.facets.plain import PlainQuantity
from tabulate import tabulate

from geophires_x import Model as Model
from geophires_x.EconomicsSamCashFlow import (
    _calculate_sam_economics_cash_flow_operational_years,
    _SAM_CASH_FLOW_NAN_STR,
)
from geophires_x.EconomicsUtils import (
    BuildPricingModel,
    wacc_output_parameter,
    nominal_discount_rate_parameter,
    after_tax_irr_parameter,
    moic_parameter,
    project_vir_parameter,
    project_payback_period_parameter,
    total_capex_parameter_output_parameter,
    royalty_cost_output_parameter,
    overnight_capital_cost_output_parameter,
    _SAM_EM_MOIC_RETURNS_TAX_QUALIFIER,
    investment_tax_credit_output_parameter,
)
from geophires_x.EconomicsSamPreRevenue import (
    _AFTER_TAX_NET_CASH_FLOW_ROW_NAME,
    PreRevenueCostsAndCashflow,
    calculate_pre_revenue_costs_and_cashflow,
    adjust_phased_schedule_to_new_length,
)
from geophires_x.GeoPHIRESUtils import is_float, is_int, sig_figs, quantity
from geophires_x.OptionList import EconomicModel, EndUseOptions
from geophires_x.Parameter import Parameter, OutputParameter, floatParameter, listParameter
from geophires_x.Units import convertible_unit, EnergyCostUnit, CurrencyUnit, Units

_log = logging.getLogger(__name__)

ROYALTIES_OPEX_CASH_FLOW_LINE_ITEM_KEY = 'O&M production-based expense ($)'


@dataclass
class SamEconomicsCalculations:
    _sam_cash_flow_profile_operational_years: list[list[Any]]
    """
    Operational cash flow profile from SAM financial engine
    """

    pre_revenue_costs_and_cash_flow: PreRevenueCostsAndCashflow

    lcoe_nominal: OutputParameter = field(
        default_factory=lambda: OutputParameter(
            UnitType=Units.ENERGYCOST,
            CurrentUnits=EnergyCostUnit.CENTSSPERKWH,
        )
    )

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

    @property
    def _pre_revenue_years_count(self) -> int:
        return len(
            self.pre_revenue_costs_and_cash_flow.pre_revenue_cash_flow_profile_dict[_AFTER_TAX_NET_CASH_FLOW_ROW_NAME]
        )

    @property
    def sam_cash_flow_profile(self) -> list[list[Any]]:
        ret: list[list[Any]] = self._sam_cash_flow_profile_operational_years.copy()
        col_count = len(self._sam_cash_flow_profile_operational_years[0])

        # TODO support/insert calendar year line item https://github.com/NREL/GEOPHIRES-X/issues/439

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

        def _get_row_index(row_name_: str) -> list[Any]:
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

        ret = self._insert_calculated_levelized_metrics_line_items(ret)

        return ret

    def _insert_royalties_rate_schedule(self, cf_ret: list[list[Any]]) -> list[list[Any]]:
        ret = cf_ret.copy()

        def _get_row_index(row_name_: str) -> list[Any]:
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

    # noinspection DuplicatedCode
    def _insert_calculated_levelized_metrics_line_items(self, cf_ret: list[list[Any]]) -> list[list[Any]]:
        ret = cf_ret.copy()

        __row_names: list[str] = [it[0] for it in ret]

        def _get_row_index(row_name_: str) -> int:
            return __row_names.index(row_name_)

        def _get_row_indexes(row_name_: str, after_row_name: str | None = None) -> list[int]:
            after_criteria_met: bool = True if after_row_name is None else False
            indexes = []
            for idx, _row_name_ in enumerate(__row_names):
                if _row_name_ == after_row_name:
                    after_criteria_met = True

                if _row_name_ == row_name_ and after_criteria_met:
                    indexes.append(idx)

            return indexes

        def _get_row_index_after(row_name_: str, after_row_name: str) -> int:
            return _get_row_indexes(row_name_, after_row_name=after_row_name)[0]

        after_tax_lcoe_and_ppa_price_header_row_title = 'AFTER-TAX LCOE AND PPA PRICE'

        # Backfill annual costs
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

        pv_of_annual_costs_backfilled_row_name = 'Present value of annual costs ($)'

        # Backfill PV of annual costs
        annual_costs_backfilled_pv_processed = annual_costs_backfilled.copy()
        pv_of_annual_costs_backfilled = []
        for year in range(self._pre_revenue_years_count):
            pv_at_year = abs(
                round(
                    npf.npv(
                        self.nominal_discount_rate.quantity().to('dimensionless').magnitude,
                        annual_costs_backfilled_pv_processed,
                    )
                )
            )

            pv_of_annual_costs_backfilled.append(pv_at_year)

            cost_at_year = annual_costs_backfilled_pv_processed.pop(0)
            annual_costs_backfilled_pv_processed[0] = annual_costs_backfilled_pv_processed[0] + cost_at_year

        pv_of_annual_costs_backfilled_row = [
            *[pv_of_annual_costs_backfilled_row_name],
            *pv_of_annual_costs_backfilled,
        ]

        pv_of_annual_costs_row_name = 'Present value of annual costs ($)'
        pv_of_annual_costs_row_index = _get_row_index(pv_of_annual_costs_row_name)
        ret[pv_of_annual_costs_row_index][1:] = [
            pv_of_annual_costs_backfilled[0],
            *([''] * (self._pre_revenue_years_count - 1)),
        ]

        # Backfill PV of electricity to grid
        electricity_to_grid_backfilled_pv_processed = electricity_to_grid_backfilled.copy()
        pv_of_electricity_to_grid_backfilled_kwh = []
        for year in range(self._pre_revenue_years_count):
            pv_at_year = abs(
                round(
                    npf.npv(
                        self.nominal_discount_rate.quantity().to('dimensionless').magnitude,
                        electricity_to_grid_backfilled_pv_processed,
                    )
                )
            )

            pv_of_electricity_to_grid_backfilled_kwh.append(pv_at_year)

            electricity_to_grid_at_year = electricity_to_grid_backfilled_pv_processed.pop(0)
            electricity_to_grid_backfilled_pv_processed[0] = (
                electricity_to_grid_backfilled_pv_processed[0] + electricity_to_grid_at_year
            )

        pv_of_annual_energy_row_name = 'Present value of annual energy nominal (kWh)'
        for pv_of_annual_energy_row_index in _get_row_indexes(pv_of_annual_energy_row_name):
            ret[pv_of_annual_energy_row_index][1:] = [
                pv_of_electricity_to_grid_backfilled_kwh[0],
                *([''] * (self._pre_revenue_years_count - 1)),
            ]

        def backfill_lcoe_nominal() -> None:
            pv_of_electricity_to_grid_backfilled_row_kwh = pv_of_electricity_to_grid_backfilled_kwh
            pv_of_annual_costs_backfilled_row_values_usd = pv_of_annual_costs_backfilled_row[
                1 if isinstance(pv_of_annual_costs_backfilled_row[0], str) else 0 :
            ]

            lcoe_nominal_backfilled = []
            for _year in range(len(pv_of_annual_costs_backfilled_row_values_usd)):
                lcoe_nominal_backfilled.append(
                    pv_of_annual_costs_backfilled_row_values_usd[_year]
                    * 100
                    / pv_of_electricity_to_grid_backfilled_row_kwh[_year]
                )

            lcoe_nominal_row_name = 'LCOE Levelized cost of energy nominal (cents/kWh)'
            lcoe_nominal_row_index = _get_row_index(lcoe_nominal_row_name)
            ret[lcoe_nominal_row_index][1:] = [
                round(lcoe_nominal_backfilled[0], 2),
                *([None] * (self._pre_revenue_years_count - 1)),
            ]

        backfill_lcoe_nominal()

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

            # Note: expected to be same in all pre-revenue years since both price and revenue are zero until COD
            first_year_lppa_cents_per_kwh = (
                first_year_pv_of_ppa_revenue_usd * 100.0 / ret[_get_row_index(pv_of_annual_energy_row_name)][1]
            )

            lppa_row_name = 'LPPA Levelized PPA price nominal (cents/kWh)'
            ret[_get_row_index(lppa_row_name)][1:] = [
                round(first_year_lppa_cents_per_kwh, 2),
                *([None] * self._pre_revenue_years_count),
            ]

        backfill_lppa_metrics()

        return ret

    @property
    def sam_after_tax_net_cash_flow_all_years(self) -> list[float]:
        return _after_tax_net_cash_flow_all_years(self.sam_cash_flow_profile, self._pre_revenue_years_count)


def validate_read_parameters(model: Model) -> None:
    def _inv_msg(param_name: str, invalid_value: Any, supported_description: str) -> str:
        return (
            f'Invalid {param_name} ({invalid_value}) for '
            f'{EconomicModel.SAM_SINGLE_OWNER_PPA.name} economic model. '
            f'{EconomicModel.SAM_SINGLE_OWNER_PPA.name} only supports '
            f'{supported_description}.'
        )

    if model.surfaceplant.enduse_option.value != EndUseOptions.ELECTRICITY:
        raise ValueError(
            _inv_msg(
                model.surfaceplant.enduse_option.Name,
                model.surfaceplant.enduse_option.value.value,
                f'{EndUseOptions.ELECTRICITY.name} End-Use Option',
            )
        )

    gtr: floatParameter = model.economics.GTR
    if gtr.Provided:
        model.logger.warning(
            f'{gtr.Name} provided value ({gtr.value}) will be ignored. (SAM Economics tax rates '
            f'are determined from {model.economics.CTR.Name} and {model.economics.PTR.Name}.)'
        )

    eir: floatParameter = model.economics.EIR
    if eir.Provided:
        model.logger.warning(
            f'{eir.Name} provided value ({eir.value}) will be ignored. (SAM Economics does not support {eir.Name}.)'
        )

    econ = model.economics

    econ.construction_capex_schedule.value = _validate_construction_capex_schedule(
        econ.construction_capex_schedule,
        model.surfaceplant.construction_years.value,
        model,
    )

    construction_years = model.surfaceplant.construction_years.value
    if abs(econ.bond_financing_start_year.value) >= construction_years:
        model.logger.debug(
            f'{econ.bond_financing_start_year.Name} ({econ.bond_financing_start_year.value}) is earlier than '
            f'first {model.surfaceplant.construction_years.Name[:-1]} ({-1 * (construction_years - 1)}). (OK)'
        )


def _validate_construction_capex_schedule(
    econ_capex_schedule: listParameter, construction_years: int, model: Model
) -> list[float]:
    capex_schedule: list[float] = econ_capex_schedule.value.copy()

    adjust_schedule_reasons: list[str] = []
    if sum(capex_schedule) != 1.0:
        adjust_schedule_reasons.append(f'does not sum to 1.0 (sums to {sum(capex_schedule)})')

    capex_schedule_len = len(capex_schedule)
    if capex_schedule_len != construction_years:
        adjust_schedule_reasons.append(
            f'length ({capex_schedule_len}) does not match ' f'construction years ({construction_years})'
        )

    if len(adjust_schedule_reasons) > 0:
        capex_schedule = adjust_phased_schedule_to_new_length(econ_capex_schedule.value, construction_years)

        if model.outputs.printoutput.value:
            # Use printoutput as a proxy for whether the user has requested logging;
            #  TODO to implement/support logging-specific config

            msg = f'{econ_capex_schedule.Name} ({econ_capex_schedule.value}) '
            msg += ' and '.join(adjust_schedule_reasons)
            msg += f'. It has been adjusted to: {capex_schedule}'

            model.logger.warning(msg)

    return capex_schedule


@lru_cache(maxsize=12)
def calculate_sam_economics(model: Model) -> SamEconomicsCalculations:
    custom_gen = CustomGeneration.new()
    grid = Grid.from_existing(custom_gen)
    utility_rate = UtilityRate.from_existing(custom_gen)
    single_owner: Singleowner = Singleowner.from_existing(custom_gen)

    project_name = 'Generic_400_MWe'
    project_dir = Path(os.path.dirname(model.economics.MyPath), 'sam_economics', project_name)
    # noinspection SpellCheckingInspection
    file_names = [f'{project_name}_{module}' for module in ['custom_generation', 'grid', 'utilityrate5', 'singleowner']]
    modules = [custom_gen, grid, utility_rate, single_owner]

    for module_file, module in zip(file_names, modules):
        with open(Path(project_dir, f'{module_file}.json'), encoding='utf-8') as file:
            data = json.load(file)
            for k, v in data.items():
                if k != 'number_inputs':
                    module.value(k, v)

    module_param_mappings = [
        ('Custom Generation', _get_custom_gen_parameters, custom_gen),
        ('Utility Rate', _get_utility_rate_parameters, utility_rate),
        ('Single Owner', _get_single_owner_parameters, single_owner),
    ]

    mapping_result: list[list[Any]] = [['SAM Module', 'Parameter', 'Value']]
    for mapping in module_param_mappings:
        module_name = mapping[0]
        module_params: dict[str, Any] = mapping[1](model)
        for k, v in module_params.items():
            mapping[2].value(k, v)
            mapping_result.append([module_name, k, v])

    mapping_tabulated = tabulate(mapping_result, **{'floatfmt': ',.2f'})
    mapping_msg = f'SAM Economics Parameter Mapping:\n{mapping_tabulated}'
    model.logger.info(mapping_msg)

    for module in modules:
        module.execute()

    cash_flow_operational_years = _calculate_sam_economics_cash_flow_operational_years(model, single_owner)

    def sf(_v: float, num_sig_figs: int = 5) -> float:
        return sig_figs(_v, num_sig_figs)

    sam_economics: SamEconomicsCalculations = SamEconomicsCalculations(
        _sam_cash_flow_profile_operational_years=cash_flow_operational_years,
        pre_revenue_costs_and_cash_flow=calculate_pre_revenue_costs_and_cashflow(model),
    )

    sam_economics.overnight_capital_cost.value = (
        model.economics.CCap.quantity().to(sam_economics.overnight_capital_cost.CurrentUnits.value).magnitude
    )

    sam_economics.after_tax_irr.value = sf(_get_after_tax_irr_pct(single_owner, cash_flow_operational_years, model))

    sam_economics.project_npv.value = sf(_get_project_npv_musd(single_owner, cash_flow_operational_years, model))
    sam_economics.capex.value = single_owner.Outputs.adjusted_installed_cost * 1e-6

    if model.economics.royalty_rate.Provided:
        # Assumes that royalties opex is the only possible O&M production-based expense - this logic will need to be
        # updated if more O&M production-based expenses are added to SAM-EM
        sam_economics.royalties_opex.value = [
            *_pre_revenue_years_vector(model),
            *[
                quantity(it, 'USD / year').to(sam_economics.royalties_opex.CurrentUnits).magnitude
                for it in _cash_flow_profile_row(cash_flow_operational_years, ROYALTIES_OPEX_CASH_FLOW_LINE_ITEM_KEY)
            ],
        ]

        sam_economics._royalties_rate_schedule = model.economics.get_royalty_rate_schedule(model)

    sam_economics.nominal_discount_rate.value, sam_economics.wacc.value = _calculate_nominal_discount_rate_and_wacc_pct(
        model, single_owner
    )
    sam_economics.moic.value = _calculate_moic(sam_economics.sam_cash_flow_profile, model)
    sam_economics.project_vir.value = _calculate_project_vir(sam_economics.sam_cash_flow_profile, model)
    sam_economics.project_payback_period.value = _calculate_project_payback_period(
        sam_economics.sam_cash_flow_profile, model
    )
    sam_economics.investment_tax_credit.value = (
        _calculate_investment_tax_credit_value(sam_economics.sam_cash_flow_profile)
        .to(sam_economics.investment_tax_credit.CurrentUnits.value)
        .magnitude
    )

    # Note that this calculation is order-dependent on sam_economics.nominal_discount_rate
    sam_economics.lcoe_nominal.value = sf(
        _get_lcoe_nominal_cents_per_kwh(single_owner, sam_economics.sam_cash_flow_profile, model)
    )

    return sam_economics


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


def _get_project_npv_musd(single_owner: Singleowner, cash_flow: list[list[Any]], model: Model) -> float:
    pre_revenue_costs: PreRevenueCostsAndCashflow = calculate_pre_revenue_costs_and_cashflow(model)
    pre_revenue_cash_flow = pre_revenue_costs.after_tax_net_cash_flow_usd
    operational_cash_flow = _cash_flow_profile_row(cash_flow, 'Total after-tax returns ($)')
    combined_cash_flow = pre_revenue_cash_flow + operational_cash_flow[1:]

    true_npv_usd = npf.npv(
        _calculate_nominal_discount_rate_and_wacc_pct(model, single_owner)[0] / 100.0, combined_cash_flow
    )
    return true_npv_usd * 1e-6  # Convert to M$


# noinspection PyUnusedLocal
def _get_lcoe_nominal_cents_per_kwh(
    single_owner: Singleowner, sam_cash_flow_profile: list[list[Any]], model: Model
) -> float:
    lcoe_row_name = 'LCOE Levelized cost of energy nominal (cents/kWh)'
    ret = _cash_flow_profile_row(sam_cash_flow_profile, lcoe_row_name)[0]

    # model.logger.info(f'Single Owner LCOE nominal (cents/kWh): {single_owner.Outputs.lcoe_nom}');

    return ret


# noinspection PyUnusedLocal
def _get_after_tax_irr_pct(single_owner: Singleowner, cash_flow: list[list[Any]], model: Model) -> float:
    pre_revenue_costs: PreRevenueCostsAndCashflow = calculate_pre_revenue_costs_and_cashflow(model)
    pre_revenue_cash_flow = pre_revenue_costs.after_tax_net_cash_flow_usd
    operational_cash_flow = _cash_flow_profile_row(cash_flow, 'Total after-tax returns ($)')
    combined_cash_flow = pre_revenue_cash_flow + operational_cash_flow[1:]
    after_tax_irr_pct = npf.irr(combined_cash_flow) * 100.0

    return after_tax_irr_pct


def _cash_flow_profile_row(cash_flow: list[list[Any]], row_name: str) -> list[Any]:
    return next(row for row in cash_flow if len(row) > 0 and row[0] == row_name)[1:]  # type: ignore[no-any-return]


def _cash_flow_profile_entry(cash_flow: list[list[Any]], row_name: str, year_index: int) -> list[Any]:
    col_index = cash_flow[0].index(f'Year {year_index}')
    return _cash_flow_profile_row(cash_flow, row_name)[col_index - 1]


def _calculate_nominal_discount_rate_pct(model: Model) -> float:
    econ = model.economics
    return _calculate_nominal_discount_rate_from_real_and_inflation_pct(econ.discountrate.value, econ.RINFL.value)


def _calculate_nominal_discount_rate_from_real_and_inflation_pct(discount_rate: float, inflation_rate: float) -> float:
    """
    Calculated per https://samrepo.nrelcloud.org/help/fin_single_owner.html?q=nominal+discount+rate
    """

    return ((1 + discount_rate) * (1 + inflation_rate) - 1) * 100


def _calculate_nominal_discount_rate_and_wacc_pct(model: Model, single_owner: Singleowner) -> tuple[float]:
    """
    Calculation per SAM Help -> Financial Parameters -> Commercial -> Commercial Loan Parameters -> WACC

    :return: tuple of Nominal Discount Rate (%), WACC (%)
    """

    nominal_discount_rate_pct = _calculate_nominal_discount_rate_pct(model)

    econ = model.economics
    fed_tax_rate = max(single_owner.Outputs.cf_federal_tax_frac)
    state_tax_rate = max(single_owner.Outputs.cf_state_tax_frac)
    effective_tax_rate = (fed_tax_rate * (1 - state_tax_rate) + state_tax_rate) * 100
    debt_fraction = single_owner.Outputs.debt_fraction / 100
    wacc_pct = (
        nominal_discount_rate_pct / 100 * (1 - debt_fraction)
        + debt_fraction * econ.BIR.value * (1 - effective_tax_rate / 100)
    ) * 100

    return nominal_discount_rate_pct, wacc_pct


def _calculate_moic(cash_flow: list[list[Any]], model) -> float | None:
    try:
        total_capital_invested_USD: Decimal = Decimal(
            next(it for it in _cash_flow_profile_row(cash_flow, 'Issuance of equity ($)') if is_float(it))
        )

        total_value_received_from_investment_USD: Decimal = sum(
            [
                Decimal(it)
                for it in _net_cash_flow_all_years(
                    cash_flow, _pre_revenue_years_count(model), tax_qualifier=_SAM_EM_MOIC_RETURNS_TAX_QUALIFIER
                )
            ]
        )
        return float(total_value_received_from_investment_USD / total_capital_invested_USD)
    except Exception as e:
        model.logger.error(f'Encountered exception calculating MOIC: {e}')
        return None


def _calculate_project_vir(cash_flow: list[list[Any]], model: Model) -> float:
    nominal_discount_rate = _calculate_nominal_discount_rate_pct(model) / 100

    net_equity_cash_flow = _cash_flow_profile_row(cash_flow, 'After-tax net cash flow ($)')

    pv_inflows = 0.0
    pv_outflows = 0.0

    for t, cf in enumerate(net_equity_cash_flow):
        # Calculate Discount Factor for year t (where t=0 is start of construction)
        discount_factor = 1 / ((1 + nominal_discount_rate) ** t)
        discounted_value = cf * discount_factor

        if cf >= 0:
            pv_inflows += discounted_value
        else:
            # Accumulate negative flows (Investment).
            # Note: We keep this negative here and take abs() at the end.
            pv_outflows += discounted_value

    # Guard against division by zero (unlikely in a construction project)
    if pv_outflows == 0:
        return 0.0

    # VIR = PV(Returns) / abs(PV(Investment)).
    vir = pv_inflows / abs(pv_outflows)
    return vir


def _calculate_project_payback_period(cash_flow: list[list[Any]], model) -> float | None:
    """
    Calculates the Simple Payback Period (SPB).
    SPB is the time required for the cumulative non-discounted after-tax net cash flow to turn positive.

    The calculation assumes annual cash flows. The returned value represents the number of years
    from the start of the provided cash flow list until the investment is recovered.
    """
    try:
        # Get flattened annual after-tax cash flow
        after_tax_cash_flow = _after_tax_net_cash_flow_all_years(cash_flow, _pre_revenue_years_count(model))

        cumulative_cash_flow = np.zeros(len(after_tax_cash_flow))
        cumulative_cash_flow[0] = after_tax_cash_flow[0]

        # Handle edge case where the first year is already positive
        if cumulative_cash_flow[0] >= 0:
            # If the project is profitable immediately (rare for SPB), return 0 or fraction.
            # For standard SPB logic where Index 0 is an investment year, this is an edge case.
            pass

        for year_index in range(1, len(after_tax_cash_flow)):
            cumulative_cash_flow[year_index] = cumulative_cash_flow[year_index - 1] + after_tax_cash_flow[year_index]

            if cumulative_cash_flow[year_index] >= 0:
                # Payback occurred in this year (year_index).
                # We need to calculate how far into this year the break-even point occurred.

                previous_year_index = year_index - 1
                unrecovered_cost_at_start_of_year = abs(cumulative_cash_flow[previous_year_index])
                cash_flow_in_current_year = after_tax_cash_flow[year_index]

                # Fraction of the current year required to recover the remaining cost
                fraction_of_year = unrecovered_cost_at_start_of_year / cash_flow_in_current_year

                # Total years elapsed = Full years prior to this one + fraction of this one.
                # If we are at year_index, the number of full years passed is equal to year_index.
                # Example: If year_index is 5 (6th year), 5 full years (Indices 0..4) have passed.
                payback_period = year_index + fraction_of_year

                return float(payback_period)

        return float('nan')  # never pays back
    except Exception as e:
        model.logger.error(f'Encountered exception calculating Project Payback Period: {e}')
        return None


def _calculate_investment_tax_credit_value(sam_cash_flow_profile) -> PlainQuantity:
    total_itc_sum_q: PlainQuantity = quantity(0, 'USD')

    for itc_line_item in ['Federal ITC total income ($)', 'State ITC total income ($)']:
        itc_numeric_entries = [
            float(it) for it in _cash_flow_profile_row(sam_cash_flow_profile, itc_line_item) if is_float(it)
        ]
        itc_sum_q = quantity(sum(itc_numeric_entries), 'USD')
        total_itc_sum_q += itc_sum_q

    return total_itc_sum_q


def get_sam_cash_flow_profile_tabulated_output(model: Model, **tabulate_kw_args) -> str:
    """
    Note model must have already calculated economics for this to work (used in Outputs)
    """

    # fmt:off
    _tabulate_kw_args = {
        'tablefmt': 'tsv',
        'floatfmt': ',.2f',
        **tabulate_kw_args
    }
    # fmt:on

    def get_entry_display(entry: Any) -> str:
        if is_float(entry):
            if not isnan(float(entry)):
                if not is_int(entry):
                    # skip decimals for large numbers like SAM does
                    entry_display = f'{entry:,.2f}' if entry < 1e6 else f'{entry:,.0f}'
                else:
                    entry_display = f'{entry:,}'
                return entry_display
        return entry

    profile_display = model.economics.sam_economics_calculations.sam_cash_flow_profile.copy()
    for i in range(len(profile_display)):
        for j in range(len(profile_display[i])):
            profile_display[i][j] = get_entry_display(profile_display[i][j])

    return tabulate(profile_display, **_tabulate_kw_args)


def _analysis_period(model: Model) -> int:
    return model.surfaceplant.plant_lifetime.value  # + _pre_revenue_years_count(model) - 1


def _get_custom_gen_parameters(model: Model) -> dict[str, Any]:
    # fmt:off
    ret: dict[str, Any] = {
        # Project lifetime
        'analysis_period': _analysis_period(model),
        'user_capacity_factor': _pct(model.surfaceplant.utilization_factor),
    }
    # fmt:on

    return ret


def _pre_revenue_years_count(model: Model) -> int:
    return model.surfaceplant.construction_years.value


def _pre_revenue_years_vector(model: Model, v: float = 0.0) -> list[float]:
    return [v] * (_pre_revenue_years_count(model) - 1)


def _get_utility_rate_parameters(m: Model) -> dict[str, Any]:
    econ = m.economics

    # noinspection PyDictCreation
    ret: dict[str, Any] = {}

    ret['inflation_rate'] = econ.RINFL.quantity().to(convertible_unit('%')).magnitude

    max_total_kWh_produced = np.max(m.surfaceplant.TotalkWhProduced.value)
    degradation_total = [
        (max_total_kWh_produced - it) / max_total_kWh_produced * 100 for it in m.surfaceplant.NetkWhProduced.value
    ]

    ret['degradation'] = degradation_total

    return ret


def _get_single_owner_parameters(model: Model) -> dict[str, Any]:
    """
    TODO:
        - Break out indirect costs (instead of lumping all into direct cost):
            https://github.com/NREL/GEOPHIRES-X/issues/383
    """
    econ = model.economics

    # noinspection PyDictCreation
    ret: dict[str, Any] = {}

    ret['analysis_period'] = _analysis_period(model)

    # SAM docs claim that specifying flip target year, aka "year in which you want the IRR to be achieved" influences
    # how after-tax cumulative IRR is reported (https://samrepo.nrelcloud.org/help/mtf_irr.html). This claim seems to
    # be erroneous, however, as setting this value appears to have no effect in either the SAM desktop app nor when
    # calling with PySAM. But, we set it here anyway for the sake of technical compliance.
    ret['flip_target_year'] = _analysis_period(model)

    total_overnight_capex_usd = econ.CCap.quantity().to('USD').magnitude

    total_installed_cost_usd: float
    construction_financing_cost_usd: float
    pre_revenue_costs: PreRevenueCostsAndCashflow = calculate_pre_revenue_costs_and_cashflow(model)
    total_installed_cost_usd: float = pre_revenue_costs.total_installed_cost_usd
    construction_financing_cost_usd: float = pre_revenue_costs.construction_financing_cost_usd

    econ.accrued_financing_during_construction_percentage.value = (
        quantity(construction_financing_cost_usd / total_overnight_capex_usd, 'dimensionless')
        .to(convertible_unit(econ.accrued_financing_during_construction_percentage.CurrentUnits))
        .magnitude
    )

    econ.inflation_cost_during_construction.value = (
        quantity(pre_revenue_costs.inflation_cost_usd, 'USD')
        .to(econ.inflation_cost_during_construction.CurrentUnits)
        .magnitude
    )

    # Pass the final, correct values to SAM
    ret['total_installed_cost'] = total_installed_cost_usd

    opex_musd = econ.Coam.value
    ret['om_fixed'] = [opex_musd * 1e6] * model.surfaceplant.plant_lifetime.value

    # GEOPHIRES assumes O&M fixed costs are not affected by inflation
    ret['om_fixed_escal'] = -1.0 * _pct(econ.RINFL)

    # Note generation profile is generated relative to the max in _get_utility_rate_parameters
    ret['system_capacity'] = _get_max_total_generation_kW(model)

    ret['federal_tax_rate'], ret['state_tax_rate'] = _get_fed_and_state_tax_rates(econ.CTR.value)

    geophires_itc_tenths = Decimal(econ.RITC.value)
    ret['itc_fed_percent'] = [float(geophires_itc_tenths * Decimal(100))]

    if econ.PTCElec.Provided:
        ret['ptc_fed_amount'] = [econ.PTCElec.quantity().to(convertible_unit('USD/kWh')).magnitude]

        ret['ptc_fed_term'] = econ.PTCDuration.quantity().to(convertible_unit('yr')).magnitude

        if econ.PTCInflationAdjusted.value:
            ret['ptc_fed_escal'] = _pct(econ.RINFL)

    # 'Property Tax Rate'
    geophires_ptr_tenths = Decimal(econ.PTR.value)
    ret['property_tax_rate'] = float(geophires_ptr_tenths * Decimal(100))

    ppa_price_schedule_per_kWh = _get_ppa_price_schedule_per_kWh(model)
    ret['ppa_price_input'] = ppa_price_schedule_per_kWh

    if model.economics.royalty_rate.Provided:
        ret['om_production'] = _get_royalties_variable_om_USD_per_MWh_schedule(model)

    # Debt/equity ratio
    ret['debt_percent'] = pre_revenue_costs.effective_debt_percent

    # Interest rate
    ret['real_discount_rate'] = _pct(econ.discountrate)

    # Project lifetime
    ret['term_tenor'] = model.surfaceplant.plant_lifetime.value
    ret['term_int_rate'] = _pct(econ.BIR)

    ret['ibi_oth_amount'] = (econ.OtherIncentives.quantity() + econ.TotalGrant.quantity()).to('USD').magnitude

    if model.economics.DoAddOnCalculations.value:
        add_on_profit_per_year = np.sum(model.addeconomics.AddOnProfitGainedPerYear.quantity().to('USD/yr').magnitude)
        add_on_profit_series = [add_on_profit_per_year] * model.surfaceplant.plant_lifetime.value
        ret['cp_capacity_payment_amount'] = add_on_profit_series
        ret['cp_capacity_payment_type'] = 1

    return ret


def _get_royalties_variable_om_USD_per_MWh_schedule(model: Model):
    royalty_rate_schedule = _get_royalty_rate_schedule(model)
    ppa_price_schedule_per_kWh = _get_ppa_price_schedule_per_kWh(model)

    # For each year, calculate the royalty as a $/MWh variable cost.
    # The royalty is a percentage of revenue (MWh * $/MWh). By setting the
    # variable O&M rate to (PPA Price * Royalty Rate), SAM's calculation
    # (Rate * MWh) will correctly yield the total royalty payment.
    variable_om_schedule_USD_per_MWh = [
        quantity(price_kWh, model.economics.ElecStartPrice.CurrentUnits).to('USD / megawatt_hour').magnitude
        * royalty_fraction
        for price_kWh, royalty_fraction in zip(ppa_price_schedule_per_kWh, royalty_rate_schedule)
    ]

    return variable_om_schedule_USD_per_MWh


def _get_fed_and_state_tax_rates(geophires_ctr_tenths: float) -> tuple[list[float]]:
    geophires_ctr_tenths = Decimal(geophires_ctr_tenths)
    max_fed_rate_tenths = Decimal(0.21)
    fed_rate_tenths = min(geophires_ctr_tenths, max_fed_rate_tenths)

    state_rate_tenths = max(0, geophires_ctr_tenths - fed_rate_tenths)

    def ret_val(val_tenths: Decimal) -> list[float]:
        return [round(float(val_tenths * Decimal(100)), 2)]

    return ret_val(fed_rate_tenths), ret_val(state_rate_tenths)


def _pct(econ_value: Parameter) -> float:
    return econ_value.quantity().to(convertible_unit('%')).magnitude


def _get_ppa_price_schedule_per_kWh(model: Model) -> list:
    """
    :return: quantity list of PPA price schedule per kWh in econ.ElecStartPrice.CurrentUnits
    """

    econ = model.economics
    pricing_model = _ppa_pricing_model(
        model.surfaceplant.plant_lifetime.value,
        econ.ElecStartPrice.value,
        econ.ElecEndPrice.value,
        econ.ElecEscalationStart.value,
        econ.ElecEscalationRate.value,
    )

    return [quantity(it, econ.ElecStartPrice.CurrentUnits).magnitude for it in pricing_model]


def _ppa_pricing_model(
    plant_lifetime: int, start_price: float, end_price: float, escalation_start_year: int, escalation_rate: float
) -> list[float]:
    # See relevant comment in geophires_x.EconomicsUtils.BuildPricingModel re:
    # https://github.com/NREL/GEOPHIRES-X/issues/340?title=Price+Escalation+Start+Year+seemingly+off+by+1.
    # We use the same utility method here for the sake of consistency despite technical incorrectness.
    return BuildPricingModel(
        plant_lifetime, start_price, end_price, escalation_start_year, escalation_rate, [0] * plant_lifetime
    )


def _get_royalty_rate_schedule(model: Model) -> list[float]:
    return model.economics.get_royalty_rate_schedule(model)


def _get_max_total_generation_kW(model: Model) -> float:
    return np.max(model.surfaceplant.ElectricityProduced.quantity().to(convertible_unit('kW')).magnitude)
