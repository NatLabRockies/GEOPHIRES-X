from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from math import isnan
from pathlib import Path
from typing import Any, Iterable

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
from geophires_x.EconomicsSamCalculations import (
    SamEconomicsCalculations,
    CapacityPaymentRevenueSource,
    ROYALTIES_OPEX_CASH_FLOW_LINE_ITEM_KEY,
    _after_tax_net_cash_flow_all_years,
    _net_cash_flow_all_years,
)
from geophires_x.EconomicsSamCashFlow import (
    _calculate_sam_economics_cash_flow_operational_years,
)
from geophires_x.EconomicsUtils import (
    end_price_or_max,
    BuildPricingModel,
    _SAM_EM_MOIC_RETURNS_TAX_QUALIFIER,
)
from geophires_x.EconomicsSamPreRevenue import (
    PreRevenueCostsAndCashflow,
    calculate_pre_revenue_costs_and_cashflow,
    adjust_phased_schedule_to_new_length,
)
from geophires_x.GeoPHIRESUtils import is_float, is_int, sig_figs, quantity
from geophires_x.OptionList import DepreciationSchedule, EconomicModel, EndUseOptions, PlantType
from geophires_x.Parameter import Parameter, OutputParameter, floatParameter, listParameter
from geophires_x.Units import convertible_unit

_log = logging.getLogger(__name__)


def validate_read_parameters(model: Model) -> None:
    def _inv_msg(param_name: str, invalid_value: Any, supported_description: str) -> str:
        return (
            f'Invalid {param_name} ({invalid_value}) for '
            f'{EconomicModel.SAM_SINGLE_OWNER_PPA.name} economic model. '
            f'{EconomicModel.SAM_SINGLE_OWNER_PPA.name} only supports '
            f'{supported_description}.'
        )

    if (
        model.surfaceplant.enduse_option.value
        not in (
            EndUseOptions.ELECTRICITY,
            EndUseOptions.HEAT,
        )
        and not model.surfaceplant.enduse_option.value.is_cogeneration_end_use_option
    ):
        raise ValueError(
            _inv_msg(
                model.surfaceplant.enduse_option.Name,
                model.surfaceplant.enduse_option.value.value,
                f'{EndUseOptions.ELECTRICITY.value}, {EndUseOptions.HEAT.value}, ' f'and Cogeneration End-Use Options',
            )
        )

    supported_plant_types = [
        PlantType.SUB_CRITICAL_ORC,
        PlantType.SUPER_CRITICAL_ORC,
        PlantType.SINGLE_FLASH,
        PlantType.DOUBLE_FLASH,
        PlantType.ABSORPTION_CHILLER,
        PlantType.INDUSTRIAL,
    ]
    if model.surfaceplant.plant_type.value not in supported_plant_types:
        raise ValueError(
            _inv_msg(
                model.surfaceplant.plant_type.Name,
                model.surfaceplant.plant_type.value.value,
                ', '.join(map(lambda x: x.value, supported_plant_types)),
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

    # noinspection PyUnresolvedReferences
    econ: 'Economics' = model.economics

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

    if econ.royalty_rate.Provided and econ.royalty_rate_schedule.Provided:
        raise ValueError(f'Only one of {econ.royalty_rate.Name} and {econ.royalty_rate_schedule.Name} may be provided.')

    if econ.royalty_rate_schedule.Provided:
        ignored_rate_modifiers = [
            econ.royalty_escalation_rate,
            econ.royalty_escalation_rate_start_year,
            econ.maximum_royalty_rate,
        ]
        for modifier in ignored_rate_modifiers:
            if modifier.Provided:
                model.logger.warning(
                    f'{modifier.Name} provided value ({modifier.value}) will be ignored. '
                    f'This parameter is not currently applied when {econ.royalty_rate_schedule.Name} is used.'
                )
                # Note that logging a warning over raising an exception is an intentional design decision to make
                # temporarily switching/testing and/or migrating between schedule-based and rate-based more user
                # friendly by only requiring enabling/disabling 2 parameters rather than up to 6.

    if econ.DoSDACGTCalculations.value:
        raise NotImplementedError(
            'S-DAC is not currently supported for SAM Economic Models. '
            'See https://github.com/NatLabRockies/GEOPHIRES-X/issues/511.'  # TODO to implement
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
            msg += f'. It has been adjusted to: {[sig_figs(it, 3) for it in capex_schedule]}'

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
        electricity_plant_frac_of_capex=model.economics.CAPEX_heat_electricity_plant_ratio.quantity()
        .to('dimensionless')
        .magnitude,
    )

    sam_economics.overnight_capital_cost.value = (
        model.economics.CCap.quantity().to(sam_economics.overnight_capital_cost.CurrentUnits.value).magnitude
    )

    sam_economics.after_tax_irr.value = sf(_get_after_tax_irr_pct(single_owner, cash_flow_operational_years, model))

    sam_economics.project_npv.value = sf(_get_project_npv_musd(single_owner, cash_flow_operational_years, model))

    # Add back ibi_oth_amount (OtherIncentives + TotalGrant) which SAM subtracts from
    # total_installed_cost to compute adjusted_installed_cost. Incentives are still applied
    # by SAM natively in the cash flow/tax basis calculations; we just don't want them to
    # also reduce the reported Total CAPEX (which would be inconsistent with Overnight Capital
    # Cost, since CCap is not reduced by incentives for SAM Economic Models - see
    # Economics.calculate_total_capital_costs).
    _ibi_oth_usd = (
        (model.economics.OtherIncentives.quantity() + model.economics.TotalGrant.quantity()).to('USD').magnitude
    )
    sam_economics.capex.value = (single_owner.Outputs.adjusted_installed_cost + _ibi_oth_usd) * 1e-6

    if model.economics.has_royalties:
        combined_royalties_usd = [
            *_pre_revenue_years_vector(model),
            *([0] * (model.surfaceplant.plant_lifetime.value + 1)),
        ]

        if model.economics.has_production_based_royalties:
            # Assumes that royalties opex is the only possible O&M production-based expense - this logic will need to be
            # updated if more O&M production-based expenses are added to SAM-EM
            production_based_royalties_usd = [
                *_pre_revenue_years_vector(model),
                *[
                    quantity(it, 'USD / year').to(sam_economics.royalties_opex.CurrentUnits).magnitude
                    for it in _cash_flow_profile_row(
                        cash_flow_operational_years, ROYALTIES_OPEX_CASH_FLOW_LINE_ITEM_KEY
                    )
                ],
            ]

            for i, annual_production_based_royalties_usd in enumerate(production_based_royalties_usd):
                combined_royalties_usd[i] += annual_production_based_royalties_usd

            sam_economics._royalties_rate_schedule = model.economics.get_royalty_rate_schedule(model)

        if model.economics.royalty_supplemental_payments.Provided:
            royalty_supplemental_payments_schedule_usd = model.economics.get_royalty_supplemental_payments_schedule_usd(
                model
            )

            for i, annual_royalty_supplemental_payment_usd in enumerate(royalty_supplemental_payments_schedule_usd):
                combined_royalties_usd[i] += annual_royalty_supplemental_payment_usd

        sam_economics.royalties_opex.value = combined_royalties_usd

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

    if _has_capacity_payment_revenue_sources(model):
        sam_economics.capacity_payment_revenue_sources = _get_capacity_payment_revenue_sources(model)

    # Note that this calculation is order-dependent on sam_economics.nominal_discount_rate
    sam_economics.lcoe_nominal.value = sf(
        _get_lcoe_nominal_cents_per_kwh(single_owner, sam_economics.sam_cash_flow_profile, model)
    )

    # Note that LCOH & LCOC calculations are order-dependent on sam_economics.capacity_payment_revenue_sources
    sam_economics.lcoh_nominal.value = sf(
        _get_levelized_cost_non_electricity_type_nominal_usd_per_mmbtu(
            single_owner,
            sam_economics.sam_cash_flow_profile,
            model,
            levelized_cost_nominal_row_name='LCOH Levelized cost of heating nominal ($/MMBTU)',
        )
    )

    sam_economics.lcoc_nominal.value = sf(
        _get_levelized_cost_non_electricity_type_nominal_usd_per_mmbtu(
            single_owner,
            sam_economics.sam_cash_flow_profile,
            model,
            levelized_cost_nominal_row_name='LCOC Levelized cost of cooling nominal ($/MMBTU)',
        )
    )

    return sam_economics


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

    return ret


# noinspection PyUnusedLocal
def _get_levelized_cost_non_electricity_type_nominal_usd_per_mmbtu(
    single_owner: Singleowner,
    sam_cash_flow_profile: list[list[Any]],
    model: Model,
    levelized_cost_nominal_row_name: str,
) -> float | None:
    try:
        levelized_cost_row = _cash_flow_profile_row(sam_cash_flow_profile, levelized_cost_nominal_row_name)
    except StopIteration:
        return None

    ret = levelized_cost_row[0]

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

    max_total_kWh_produced = np.max(m.surfaceplant.TotalkWhProduced.quantity().to(convertible_unit('kWh')).magnitude)

    net_kwh_produced_series: Iterable | float | int = (
        m.surfaceplant.NetkWhProduced.quantity().to(convertible_unit('kWh')).magnitude
    )

    if isinstance(net_kwh_produced_series, Iterable):
        degradation_total = [
            (max_total_kWh_produced - it) / max_total_kWh_produced * 100 for it in net_kwh_produced_series
        ]
        ret['degradation'] = degradation_total
    else:
        # Occurs for non-electricity end-use options
        ret['degradation'] = [100.0] * m.surfaceplant.plant_lifetime.value

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

    opex_base_usd = econ.Coam.quantity().to('USD/yr').magnitude
    opex_by_year_usd = []
    royalty_supplemental_payments_by_year_usd = econ.get_royalty_supplemental_payments_schedule_usd(model)[
        _pre_revenue_years_count(model) :
    ]
    for year_index in range(model.surfaceplant.plant_lifetime.value):
        opex_by_year_usd.append(opex_base_usd + royalty_supplemental_payments_by_year_usd[year_index])

    if model.surfaceplant.enduse_option.value == EndUseOptions.HEAT:
        # For pure direct-use, pumping is a grid purchase.
        # Create an annual array adding the specific year's pumping cost to the base O&M.
        # TODO evaluate eventually migrating to SAM's native electricity purchase mechanisms instead
        #  (would require refactoring GEOPHIRES generation internals to support negative production...)

        elec_rate_usd_per_kwh = model.surfaceplant.electricity_cost_to_buy.quantity().to('USD/kWh').magnitude
        annual_pumping_kwh = model.surfaceplant.PumpingkWh.quantity().to('kWh/year').magnitude
        opex_by_year_usd = [
            opex_by_year_usd[year_index] + annual_pumping_kwh[year_index] * elec_rate_usd_per_kwh
            for year_index in range(model.surfaceplant.plant_lifetime.value)
        ]

    ret['om_fixed'] = opex_by_year_usd

    # GEOPHIRES assumes O&M fixed costs are not affected by inflation
    ret['om_fixed_escal'] = -1.0 * _pct(econ.RINFL)

    # Note generation profile is generated relative to the max in _get_utility_rate_parameters
    ret['system_capacity'] = _get_max_total_generation_kW(model)

    ret['federal_tax_rate'], ret['state_tax_rate'] = _get_fed_and_state_tax_rates(econ.CTR.value)

    geophires_itc_tenths = Decimal(econ.RITC.value)
    ret['itc_fed_percent'] = [float(geophires_itc_tenths * Decimal(100))]

    geophires_state_itc_usd = Decimal(econ.ritc_state_amount.quantity().to(convertible_unit('USD')).magnitude)
    ret['itc_sta_amount'] = [float(geophires_state_itc_usd)]

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

    if model.economics.has_production_based_royalties:
        ret['om_production'] = _get_royalties_variable_om_USD_per_MWh_schedule(model)

    # Debt/equity ratio
    ret['debt_percent'] = pre_revenue_costs.effective_debt_percent

    # Interest rate
    ret['real_discount_rate'] = _pct(econ.discountrate)

    # Project lifetime
    ret['term_tenor'] = _debt_tenor(model)
    ret['term_int_rate'] = _pct(econ.BIR)

    ret['ibi_oth_amount'] = (econ.OtherIncentives.quantity() + econ.TotalGrant.quantity()).to('USD').magnitude

    ret = {**ret, **_get_depreciation_parameters(model)}

    ret = {**ret, **_get_capacity_payment_parameters(model)}

    return ret


def _get_depreciation_parameters(model: Model) -> dict[str, float]:
    """
    :return: SAM depreciation allocations for the Depreciation Schedule, which allocates the entire depreciable basis
        to one depreciation class. Empty for the default (20-year straight line), which the SAM template specifies.
    """
    if model.economics.depreciation_schedule.value == DepreciationSchedule.MACRS_5_YEAR:
        return {
            'depr_alloc_macrs_5_percent': 100.0,
            'depr_alloc_sl_20_percent': 0.0,
        }

    return {}


def _debt_tenor(model: Model) -> int:
    econ = model.economics
    if not econ.debt_tenor.Provided:
        return model.surfaceplant.plant_lifetime.value

    if econ.debt_tenor.value > model.surfaceplant.plant_lifetime.value:
        raise ValueError(
            f'{econ.debt_tenor.Name} ({econ.debt_tenor.value} years) cannot exceed '
            f'{model.surfaceplant.plant_lifetime.Name} '
            f'({model.surfaceplant.plant_lifetime.value} years) - debt would remain '
            f'outstanding at the end of the project.'
        )

    return econ.debt_tenor.value


def _has_capacity_payment_revenue_sources(model: Model) -> bool:
    return len(_get_capacity_payment_revenue_sources(model)) > 0


def _get_capacity_payment_revenue_sources(model: Model) -> list[CapacityPaymentRevenueSource]:
    ret: list[CapacityPaymentRevenueSource] = []

    econ = model.economics

    def _has_revenue_type(econ_revenue_output: OutputParameter) -> bool:
        return isinstance(econ_revenue_output.value, Iterable) and any(it > 0 for it in econ_revenue_output.value)

    has_heat_revenue = _has_revenue_type(econ.HeatRevenue)
    has_cooling_revenue = _has_revenue_type(econ.CoolingRevenue)

    if econ.DoAddOnCalculations.value:
        add_on_profit_per_year_usd = np.sum(
            model.addeconomics.AddOnProfitGainedPerYear.quantity().to('USD/yr').magnitude
        )
        add_on_profit_usd_series = [round(add_on_profit_per_year_usd)] * model.surfaceplant.plant_lifetime.value
        add_on_source = CapacityPaymentRevenueSource(name='Add-On', revenue_usd=add_on_profit_usd_series)
        ret.append(add_on_source)

    def _price_vector(price_value: list[float]) -> list[float | str]:
        return [
            *(['' if it == 0.0 else it for it in price_value[: _pre_revenue_years_count(model) - 1]]),
            *price_value[_pre_revenue_years_count(model) - 1 :],
        ]

    if econ.DoCarbonCalculations.value:
        carbon_revenue_usd_series = (
            econ.CarbonRevenue.quantity().to('USD/yr').magnitude[_pre_revenue_years_count(model) :]
        )
        carbon_revenue_source = CapacityPaymentRevenueSource(
            name='Carbon credits',  # TODO/WIP naming re: https://github.com/NatLabRockies/GEOPHIRES-X/issues/476
            revenue_usd=[round(it) for it in carbon_revenue_usd_series],
            price_label=f'Carbon price ({econ.CarbonPrice.CurrentUnits.value})',
            price=_price_vector(econ.CarbonPrice.value),
            amount_provided_label=f'Saved Carbon Production ({econ.CarbonThatWouldHaveBeenProducedAnnually.CurrentUnits.value})',
            amount_provided=econ.CarbonThatWouldHaveBeenProducedAnnually.value[_pre_revenue_years_count(model) :],
        )
        ret.append(carbon_revenue_source)

    def _get_revenue_usd_series(econ_revenue_output: OutputParameter) -> Iterable[float]:
        return [
            round(it)
            for it in econ_revenue_output.quantity().to('USD/year').magnitude[_pre_revenue_years_count(model) :]
        ]

    if has_heat_revenue:
        ret.append(
            CapacityPaymentRevenueSource(
                name='Heat',
                revenue_usd=_get_revenue_usd_series(econ.HeatRevenue),
                price_label=f'Heat price ({econ.HeatPrice.CurrentUnits.value})',
                price=_price_vector(econ.HeatPrice.value),
                amount_provided_label=f'Heat provided ({model.surfaceplant.HeatkWhProduced.CurrentUnits.value})',
                amount_provided=model.surfaceplant.HeatkWhProduced.value,
            )
        )

    if has_cooling_revenue:
        # cooling_kWh_Produced's default preferred units are kWh/yr.
        # The /yr is redundant when displaying on an annualized basis.
        # TODO there are various degrees of increased sophistication with which this adjustment could be performed,
        #  e.g. adding a derived property to CurrencyFrequencyUnit instead of manually splitting the string,
        #  re-interpolating the revenue vector if it's not annualized, etc.
        cooling_provided_unit = model.surfaceplant.cooling_kWh_Produced.CurrentUnits.value
        if (cooling_provided_unit if cooling_provided_unit is not None else '').endswith('/yr'):
            cooling_provided_unit = cooling_provided_unit.split('/yr')[0]

        ret.append(
            CapacityPaymentRevenueSource(
                name='Cooling',
                revenue_usd=_get_revenue_usd_series(econ.CoolingRevenue),
                price_label=f'Cooling price ({econ.CoolingPrice.CurrentUnits.value})',
                price=_price_vector(econ.CoolingPrice.value),
                amount_provided_label=f'Cooling provided ({cooling_provided_unit})',
                amount_provided=model.surfaceplant.cooling_kWh_Produced.value,
            )
        )

    return ret


def _get_capacity_payment_parameters(model: Model) -> dict[str, Any]:
    ret: dict[str, Any] = {}

    capacity_payment_revenue_sources: list[CapacityPaymentRevenueSource] = _get_capacity_payment_revenue_sources(model)

    if len(capacity_payment_revenue_sources) == 0:
        return ret

    ret['cp_capacity_payment_type'] = 1
    ret['cp_capacity_payment_amount'] = [0.0] * model.surfaceplant.plant_lifetime.value

    for capacity_payment_revenue_source in capacity_payment_revenue_sources:
        for i, revenue_usd in enumerate(capacity_payment_revenue_source.revenue_usd):
            ret['cp_capacity_payment_amount'][i] += revenue_usd

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
        end_price_or_max(econ.ElecEndPrice),
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
    """
    Delegates to the Economics instance which now supports the DSL-based
    royalty_rate_schedule parameter with automatic fallback.
    """
    return model.economics.get_royalty_rate_schedule(model)


def _get_max_total_generation_kW(model: Model) -> float:
    max_total_kw = np.max(model.surfaceplant.ElectricityProduced.quantity().to(convertible_unit('kW')).magnitude)

    if not model.surfaceplant.enduse_option.value.has_electricity_component:
        # SAM requires a non-zero nameplate capacity, so we must provide a value even if there is no electricity
        # component. The stub value is both accepted/processed by SAM and results in
        # zero electricity production/revenue in the cash flow due to rounding.
        # This logic should be revisited if SAM adds support for combined energy-heat models per
        # https://github.com/softwareengineerprogrammer/GEOPHIRES/pull/142#pullrequestreview-3999949844
        non_electricity_end_use_stub_value = 0.0001

        max_total_kw = max(non_electricity_end_use_stub_value, max_total_kw)
        if max_total_kw != non_electricity_end_use_stub_value:
            # Shouldn't happen
            model.logger.warning(
                f'Unexpected non-zero maximum total electricity generation for heat end-use option: {max_total_kw} kW. '
                f'This may be a result of an internal bug in GEOPHIRES or an invalid parameter configuration.'
            )

    return max_total_kw
