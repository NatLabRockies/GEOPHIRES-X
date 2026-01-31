from __future__ import annotations

import math
import sys
# noinspection PyPackageRequirements
import numpy as np
import numpy_financial as npf
from pint.facets.plain import PlainQuantity

import geophires_x.Model as Model
from geophires_x import EconomicsSam
from geophires_x.EconomicsSam import calculate_sam_economics, SamEconomicsCalculations
from geophires_x.EconomicsUtils import BuildPricingModel, wacc_output_parameter, nominal_discount_rate_parameter, \
    real_discount_rate_parameter, after_tax_irr_parameter, moic_parameter, project_vir_parameter, \
    project_payback_period_parameter, inflation_cost_during_construction_output_parameter, \
    interest_during_construction_output_parameter, total_capex_parameter_output_parameter, \
    overnight_capital_cost_output_parameter, CONSTRUCTION_CAPEX_SCHEDULE_PARAMETER_NAME, \
    _YEAR_INDEX_VALUE_EXPLANATION_SNIPPET, investment_tax_credit_output_parameter
from geophires_x.GeoPHIRESUtils import quantity
from geophires_x.OptionList import Configuration, WellDrillingCostCorrelation, EconomicModel, EndUseOptions, PlantType, \
    _WellDrillingCostCorrelationCitation
from geophires_x.Parameter import intParameter, floatParameter, OutputParameter, ReadParameter, boolParameter, \
    coerce_int_params_to_enum_values, listParameter, Parameter
from geophires_x.SurfacePlantUtils import MAX_CONSTRUCTION_YEARS
from geophires_x.Units import *
from geophires_x.WellBores import calculate_total_drilling_lengths_m


def calculate_cost_of_one_vertical_well(model: Model, depth_m: float, well_correlation: int,
                                        vertical_drilling_cost_per_m: float,
                                        fixed_well_cost_name: str, well_cost_adjustment_factor: float) -> float:
    """
    CalculateCostOfOneWell calculates the cost of one vertical well based on the depth of the well and the cost correlation.
    :param model: The model object
    :type model: :class:`~geophires
    :param depth_m: The depth of the well in meters
    :type depth_m: float
    :param well_correlation: The well correlation
    :type well_correlation: int
    :param vertical_drilling_cost_per_m: The vertical drilling cost per meter in $/m
    :type vertical_drilling_cost_per_m: float
    :param fixed_well_cost_name: The fixed well cost name
    :type fixed_well_cost_name: str
    :param well_cost_adjustment_factor: The well cost adjustment factor
    :type well_cost_adjustment_factor: float
    :return: cost_of_one_well: The cost of one well in MUSD
    :rtype: float
    """
    # Check if  well depth is out of standard bounds for cost correlation
    correlations_min_valid_depth_m = 500.
    correlations_max_valid_depth_m = 7000.
    cost_of_one_well = 0.0

    if depth_m < correlations_min_valid_depth_m and not well_correlation is WellDrillingCostCorrelation.SIMPLE:
        well_correlation = WellDrillingCostCorrelation.SIMPLE
        model.logger.warning(
            f'Invalid cost correlation specified ({well_correlation}) for drilling depth '
            f'<{correlations_min_valid_depth_m}m ({depth_m}m). '
            f'Falling back to simple user-specified cost '
            f'({vertical_drilling_cost_per_m} per meter)'
        )

    if depth_m > correlations_max_valid_depth_m and not well_correlation is WellDrillingCostCorrelation.SIMPLE:
        model.logger.warning(
            f'{well_correlation} may be invalid for drilling depth '
            f'>{correlations_max_valid_depth_m}m ({depth_m}m). '
            f'Consider using {WellDrillingCostCorrelation.SIMPLE} (per-meter cost) or '
            f'{fixed_well_cost_name} (fixed cost per well) instead.'
        )

    if well_correlation is WellDrillingCostCorrelation.SIMPLE:
        cost_of_one_well = vertical_drilling_cost_per_m * depth_m * 1E-6
    else:
        cost_of_one_well = well_correlation.calculate_cost_MUSD(depth_m)

    # account for adjustment factor
    cost_of_one_well = well_cost_adjustment_factor * cost_of_one_well

    return cost_of_one_well


def calculate_cost_of_non_vertical_section(model: Model, length_m: float, well_correlation: int,
                                        nonvertical_drilling_cost_per_m: float,
                                           num_nonvertical_sections: int,
                                        fixed_well_cost_name: str, NonverticalsCased: bool,
                                           well_cost_adjustment_factor: float) -> float:
    """
    calculate_cost_of_non_vertical_section calculates the cost of the non vertical section of the well.
    Assume that the cost per meter for drilling of the non-vertical section is the same as the vertical section.
    :param model: The model object
    :type model: :class:`~geophires
    :param length_m: The depth of the well in meters
    :type length_m: float
    :param well_correlation: The well cost correlation
    :type well_correlation: int
    :param nonvertical_drilling_cost_per_m: The nonvertical drilling cost per meter in $/m
    :type nonvertical_drilling_cost_per_m: float
    :param num_nonvertical_sections: The number of non vertical sections
    :type num_nonvertical_sections: int
    :param fixed_well_cost_name: The fixed well cost name
    :type fixed_well_cost_name: str
    :param NonverticalsCased: Are the nonverticals cased?
    :type NonverticalsCased: bool
    :param well_cost_adjustment_factor: The well cost adjustment factor
    :type well_cost_adjustment_factor: float
    :return: cost_of_one_well: The cost of the nonvertical section in MUSD
    :rtype: float
    """

    # if we are drilling a vertical well, the nonvertical cost is 0
    if model.wellbores.Configuration.value == Configuration.VERTICAL:
        return 0.0

    # Check if  well length is out of standard bounds for cost correlation
    length_per_section_m = length_m / num_nonvertical_sections
    correlations_min_valid_length_m = 500.
    correlations_max_valid_length_m = 7000.
    cost_of_non_vertical_section = 0.0
    cost_per_section = 0.0

    if length_per_section_m < correlations_min_valid_length_m and not well_correlation is WellDrillingCostCorrelation.SIMPLE:
        well_correlation = WellDrillingCostCorrelation.SIMPLE
        model.logger.warning(
            f'Invalid cost correlation specified ({well_correlation}) for drilling length '
            f'<{correlations_min_valid_length_m}m ({length_m}m). '
            f'Falling back to simple user-specified cost '
            f'({nonvertical_drilling_cost_per_m} per meter)'
        )

    if length_per_section_m > correlations_max_valid_length_m and not well_correlation is WellDrillingCostCorrelation.SIMPLE:
        model.logger.warning(
            f'{well_correlation} may be invalid for drilling length '
            f'>{correlations_max_valid_length_m}m ({length_m}m). '
            f'Consider using {WellDrillingCostCorrelation.SIMPLE} (per-meter cost) or '
            f'{fixed_well_cost_name} (fixed cost per well) instead.'
        )

    # assume that casing & cementing costs 50% of drilling costs
    casing_factor = 1.0 if NonverticalsCased else 0.5

    if model.economics.Nonvertical_drilling_cost_per_m.Provided or well_correlation is WellDrillingCostCorrelation.SIMPLE:
        cost_of_non_vertical_section = casing_factor * ((num_nonvertical_sections * nonvertical_drilling_cost_per_m * length_per_section_m)) * 1E-6
    else:
        cost_per_section = well_correlation.calculate_cost_MUSD(length_per_section_m)
        cost_of_non_vertical_section = casing_factor * num_nonvertical_sections * cost_per_section

    # account for adjustment factor
    cost_of_non_vertical_section = well_cost_adjustment_factor * cost_of_non_vertical_section

    return cost_of_non_vertical_section


def BuildPTCModel(plantlifetime: int, duration: int, ptc_price: float,
                  ptc_inflation_adjusted: bool, inflation_rate: float) -> list:
    """
    BuildPricingModel builds the price model array for the project lifetime.  It is used to calculate the revenue
    stream for the project.
    :param plantlifetime: The lifetime of the project in years
    :type plantlifetime: int
    :param duration: The duration of the PTC in years
    :type duration: int
    :param ptc_price: The PTC in $/kWh
    :type ptc_price: float
    :param ptc_inflation_adjusted: Is the PTC is inflation?
    :type ptc_inflation_adjusted: bool
    :param inflation_rate: The inflation rate in %
    :type inflation_rate: float
    :return: Price: The price model array for the PTC in $/kWh
    :rtype: list
    """
    # Build the PTC price model by setting the price to the PTCPrice for the duration of the PTC
    Price = [0.0] * plantlifetime
    for year in range(0, duration, 1):
        Price[year] = ptc_price
        if ptc_inflation_adjusted and year > 0:
            Price[year] = Price[year-1] * (1 + inflation_rate)
    return Price


def CalculateTotalRevenue(plantlifetime: int, ConstructionYears: int, CAPEX: float, OPEX: float, AnnualRev):
    """
    CalculateRevenue calculates the revenue stream for the project.  It is used to calculate the revenue
    stream for the project.
    :param plantlifetime: The lifetime of the project in years in years (not including construction years) in years
    :type plantlifetime: int
    :param ConstructionYears: The number of years of construction for the project in years
    :type ConstructionYears: int
    :param CAPEX: The total capital cost of the project in MUSD
    :type CAPEX: float
    :param OPEX: The total annual operating cost of the project in MUSD
    :type OPEX: float
    :param AnnualRev: The annual revenue array for the project in MUSD
    :type AnnualRev: list
    :return: CashFlow: The annual cash flow for the project in MUSD and CummCashFlow: The cumulative cash flow for the
    project in MUSD
    :rtype: list
    """
    # Calculate the revenue
    ProjectCAPEXPerConstructionYear = CAPEX / ConstructionYears
    CashFlow = [0.0] * (plantlifetime + ConstructionYears)
    CummCashFlow = [0.0] * (plantlifetime + ConstructionYears)

    # Insert the cost of construction into the front of the array that will be used to calculate NPV
    # the convention is that the upfront CAPEX is negative
    for i in range(0, ConstructionYears, 1):
        CashFlow[i] = -1.0 * ProjectCAPEXPerConstructionYear
        CummCashFlow[i] = -1.0 * ProjectCAPEXPerConstructionYear

    for i in range(ConstructionYears, plantlifetime + ConstructionYears, 1):
        CashFlow[i] = (AnnualRev[i]) - OPEX

    # Calculate the cumulative revenue, skipping the first year because it is cumulative
    for i in range(1, plantlifetime + ConstructionYears, 1):
        CummCashFlow[i] = CummCashFlow[i - 1] + CashFlow[i]
    return CashFlow, CummCashFlow


def CalculateRevenue(plantlifetime: int, ConstructionYears: int, Energy, Price):
    """
    CalculateRevenue calculates the revenue stream for the project.  It is used to calculate the revenue
    stream for the project.
    # note this doesn't account for OPEX
    :param plantlifetime: The lifetime of the project in years in years (not including construction years) in years
    :type plantlifetime: int
    :param ConstructionYears: The number of years of construction for the project in years
    :type ConstructionYears: int
    :param Energy: The energy production array for the project in kWh
    :type Energy: list
    :param Price: The price model array for the project in $/kWh
    :type Price: list
    :return: CashFlow: The annual cash flow for the project in MUSD and CummCashFlow: The cumulative cash flow for the
    project in MUSD
    :rtype: list
    """
    # Calculate the revenue
    CashFlow = [0.0] * (plantlifetime + ConstructionYears)
    CummCashFlow = [0.0] * (plantlifetime + ConstructionYears)

    # Revenue/yr in MUSD
    for i in range(ConstructionYears, plantlifetime + ConstructionYears, 1):
        CashFlow[i] = ((Energy[i - ConstructionYears] * Price[i - ConstructionYears]) / 1_000_000.0)

    # Calculate the cumulative revenue, skipping the first year because it is cumulative
    for i in range(ConstructionYears, plantlifetime + ConstructionYears, 1):
        CummCashFlow[i] = CummCashFlow[i - 1] + CashFlow[i]
    return CashFlow, CummCashFlow


def CalculateCarbonRevenue(model, plant_lifetime: int, construction_years: int, price_dollar_lb,
                           grid_CO2_intensity_lb_kwh: float, natural_gas_CO2_intensity_lb_kwh: float,
                           NetkWhProduced, HeatkWhProduced):
    # Figure out how much carbon is being produced each year, and the amount of carbon that would have been
    # produced if that energy had been made using the grid average carbon production.
    # That then gives us the revenue, since we have a carbon price model
    # We can also get cumulative cash flow from it.
    # note this doesn't account for OPEX
    cash_flow_musd = [0.0] * (plant_lifetime + construction_years)
    cumm_cash_flow_musd = [0.0] * (plant_lifetime + construction_years)
    carbon_that_would_have_been_produced_annually_lbs = ([0.0] * (plant_lifetime + construction_years))
    carbon_that_would_have_been_produced_total_lbs = 0.0
    for i in range(construction_years, plant_lifetime + construction_years, 1):
        electrical_energy_kwh = 0.0
        heat_energy_kwh = 0.0
        elec_CO2_produced_lbs = 0.0
        heat_CO2_produced_lbs = 0.0

        # Carbon cashflow revenue (from both heat and elec) based net energy produced
        if model.surfaceplant.enduse_option.value == EndUseOptions.ELECTRICITY:  # This option has no heat component
            electrical_energy_kwh = NetkWhProduced[i - construction_years]
        elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT:  # has heat component but no electricity
            heat_energy_kwh = HeatkWhProduced[i - construction_years]
        else:  # everything else has a component of both
            electrical_energy_kwh = NetkWhProduced[i - construction_years]
            heat_energy_kwh = HeatkWhProduced[i - construction_years]

        elec_CO2_produced_lbs = electrical_energy_kwh * grid_CO2_intensity_lb_kwh
        heat_CO2_produced_lbs = heat_energy_kwh * natural_gas_CO2_intensity_lb_kwh

        # convert lbs/year to tonnes/year
        carbon_that_would_have_been_produced_annually_lbs[i] = elec_CO2_produced_lbs + heat_CO2_produced_lbs
        carbon_that_would_have_been_produced_total_lbs = carbon_that_would_have_been_produced_total_lbs + \
                                                            carbon_that_would_have_been_produced_annually_lbs[i]

        cash_flow_musd[i] = (carbon_that_would_have_been_produced_annually_lbs[i] * price_dollar_lb[i - construction_years]) / 1_000_000.0
        if i >= construction_years:
            cumm_cash_flow_musd[i] = cumm_cash_flow_musd[i - 1] + cash_flow_musd[i]

    return cash_flow_musd, cumm_cash_flow_musd, carbon_that_would_have_been_produced_annually_lbs, carbon_that_would_have_been_produced_total_lbs


def calculate_npv(
    discount_rate_tenths: float,
    cashflow_series: list,
    discount_initial_year_cashflow: bool
) -> float:
    # TODO warn/raise exception if discount rate > 1 (i.e. it's probably not converted from percent to tenths)

    npv_cashflow_series = cashflow_series.copy()  # Copy to guard against unintentional mutation of consumer field

    if discount_initial_year_cashflow:
        # Enable Excel-style NPV calculation - see https://github.com/NREL/GEOPHIRES-X/discussions/344
        npv_cashflow_series = [0, *npv_cashflow_series]

    return npf.npv(discount_rate_tenths, npv_cashflow_series)


def CalculateFinancialPerformance(plantlifetime: int,
                                  FixedInternalRate: float,
                                  TotalRevenue: list,
                                  TotalCummRevenue: list,
                                  CAPEX: float,
                                  OPEX: float,
                                  discount_initial_year_cashflow: bool = False):
    """
    CalculateFinancialPerformance calculates the financial performance of the project.  It is used to calculate the
    financial performance of the project. It is used to calculate the revenue stream for the project.
    :param plantlifetime: The lifetime of the project in years
    :type plantlifetime: int
    :param FixedInternalRate: The fixed internal rate of return for the project in %
    :type FixedInternalRate: float
    :param TotalRevenue: The total revenue stream for the project in MUSD
    :type TotalRevenue: list
    :param TotalCummRevenue: The total cumulative revenue stream for the project in MUSD
    :type TotalCummRevenue: list
    :param CAPEX: The total capital cost of the project in MUSD
    :type CAPEX: float
    :param OPEX: The total annual operating cost of the project in MUSD
    :type OPEX: float
    :param discount_initial_year_cashflow: Whether to discount the initial year of cashflow used to calculate NPV
    :type discount_initial_year_cashflow: bool

    :return: NPV: The net present value of the project in MUSD
    :rtype: float
    :return: IRR: The internal rate of return of the project in %
    :rtype: float
    :return: VIR: The value to investment ratio of the project in %
    :rtype: float
    :return: MOIC: The money on investment capital of the project in %
    :rtype: float
    :rtype: tuple
    """
    # Calculate financial performance values using numpy financials

    NPV = calculate_npv(FixedInternalRate / 100, TotalRevenue.copy(), discount_initial_year_cashflow)
    IRR = npf.irr(TotalRevenue)
    if math.isnan(IRR):
        IRR = 0.0
    else:
        IRR *= 100.  # convert from decimal to percent
    VIR = 1.0 + (NPV / CAPEX)

    # Calculate MOIC which depends on CumCashFlow
    MOIC = TotalCummRevenue[len(TotalCummRevenue) - 1] / (CAPEX + (OPEX * plantlifetime))

    return NPV, IRR, VIR, MOIC


def CalculateLCOELCOHLCOC(econ, model: Model) -> tuple[float, float, float]:
    """
    CalculateLCOELCOH calculates the levelized cost of electricity and heat for the project.
    :param econ: Economics object
    :type econ: :class:`~geophires_x.Economics.Economics`
    :param model: The model object
    :type model: :class:`~geophires_x.Model.Model`
    :return: LCOE: The levelized cost of electricity and LCOH: The levelized cost of heat and LCOC: The levelized cost of cooling
    :rtype: tuple[float, float, float]
    """
    LCOE = LCOH = LCOC = 0.0
    CCap_elec = (econ.CCap.value * econ.CAPEX_heat_electricity_plant_ratio.value)
    Coam_elec = (econ.Coam.value * econ.CAPEX_heat_electricity_plant_ratio.value)
    CCap_heat = (econ.CCap.value * (1.0 - econ.CAPEX_heat_electricity_plant_ratio.value))
    Coam_heat = (econ.Coam.value * (1.0 - econ.CAPEX_heat_electricity_plant_ratio.value))

    def _capex_total_plus_construction_inflation() -> float:
        # TODO should be return value instead of mutating econ
        econ.inflation_cost_during_construction.value = quantity(
            econ.CCap.value * econ.inflrateconstruction.value,
            econ.CCap.CurrentUnits
        ).to(econ.inflation_cost_during_construction.CurrentUnits).magnitude

        return econ.CCap.value + econ.inflation_cost_during_construction.value

    def _construction_inflation_cost_elec_heat() -> tuple[float, float]:
        construction_inflation_cost_elec = CCap_elec * econ.inflrateconstruction.value
        construction_inflation_cost_heat = CCap_heat * econ.inflrateconstruction.value

        # TODO should be return value instead of mutating econ
        econ.inflation_cost_during_construction.value = quantity(
            construction_inflation_cost_elec + construction_inflation_cost_heat,
            econ.CCap.CurrentUnits
        ).to(econ.inflation_cost_during_construction.CurrentUnits).magnitude

        return CCap_elec + construction_inflation_cost_elec, CCap_heat + construction_inflation_cost_heat

    # Calculate LCOE/LCOH/LCOC
    if econ.econmodel.value == EconomicModel.FCR:
        capex_total_plus_infl = _capex_total_plus_construction_inflation()

        if model.surfaceplant.enduse_option.value == EndUseOptions.ELECTRICITY:
            LCOE = (econ.FCR.value * capex_total_plus_infl + econ.Coam.value) / \
                   np.average(model.surfaceplant.NetkWhProduced.value) * 1E8  # cents/kWh
        elif (model.surfaceplant.enduse_option.value == EndUseOptions.HEAT and
              model.surfaceplant.plant_type.value not in [PlantType.ABSORPTION_CHILLER, PlantType.HEAT_PUMP, PlantType.DISTRICT_HEATING]):
            LCOH = (econ.FCR.value * capex_total_plus_infl + econ.Coam.value +
                    econ.averageannualpumpingcosts.value) / np.average(
                model.surfaceplant.HeatkWhProduced.value) * 1E8  # cents/kWh
            LCOH = LCOH * 2.931  # $/Million Btu
        # co-gen
        elif model.surfaceplant.enduse_option.value in [EndUseOptions.COGENERATION_TOPPING_EXTRA_HEAT,
                                                        EndUseOptions.COGENERATION_TOPPING_EXTRA_ELECTRICITY,
                                                        EndUseOptions.COGENERATION_BOTTOMING_EXTRA_ELECTRICITY,
                                                        EndUseOptions.COGENERATION_BOTTOMING_EXTRA_HEAT,
                                                        EndUseOptions.COGENERATION_PARALLEL_EXTRA_HEAT,
                                                        EndUseOptions.COGENERATION_PARALLEL_EXTRA_ELECTRICITY]:
            capex_elec_plus_infl, capex_heat_plus_infl = _construction_inflation_cost_elec_heat()
            LCOE = (econ.FCR.value * capex_elec_plus_infl + Coam_elec) / np.average(model.surfaceplant.NetkWhProduced.value) * 1E8  # cents/kWh
            LCOH = (econ.FCR.value * capex_heat_plus_infl + Coam_heat + econ.averageannualpumpingcosts.value) / np.average(model.surfaceplant.HeatkWhProduced.value) * 1E8  # cents/kWh
            LCOH = LCOH * 2.931  # $/Million Btu

        elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT and model.surfaceplant.plant_type.value == PlantType.ABSORPTION_CHILLER:
            LCOC = (econ.FCR.value * capex_total_plus_infl + econ.Coam.value + econ.averageannualpumpingcosts.value) / np.average(
                model.surfaceplant.cooling_kWh_Produced.value) * 1E8  # cents/kWh
            LCOC = LCOC * 2.931  # $/Million Btu
        elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT and model.surfaceplant.plant_type.value == PlantType.HEAT_PUMP:
            LCOH = (econ.FCR.value * capex_total_plus_infl
                    + econ.Coam.value + econ.averageannualpumpingcosts.value + econ.averageannualheatpumpelectricitycost.value) / np.average(
                model.surfaceplant.HeatkWhProduced.value) * 1E8  # cents/kWh
            LCOH = LCOH * 2.931  # $/Million Btu
        elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT and model.surfaceplant.plant_type.value == PlantType.DISTRICT_HEATING:
            LCOH = (econ.FCR.value * capex_total_plus_infl
                    + econ.Coam.value + econ.averageannualpumpingcosts.value + econ.averageannualngcost.value) / model.surfaceplant.annual_heating_demand.value * 1E2  # cents/kWh
            LCOH = LCOH * 2.931  # $/Million Btu
    elif econ.econmodel.value == EconomicModel.STANDARDIZED_LEVELIZED_COST:
        discount_vector = 1. / np.power(1 + econ.discountrate.value,
                                       np.linspace(0, model.surfaceplant.plant_lifetime.value - 1,
                                                   model.surfaceplant.plant_lifetime.value))
        capex_total_plus_infl = _capex_total_plus_construction_inflation()

        if model.surfaceplant.enduse_option.value == EndUseOptions.ELECTRICITY:
            LCOE = (capex_total_plus_infl + np.sum(
                econ.Coam.value * discount_vector)) / np.sum(
                model.surfaceplant.NetkWhProduced.value * discount_vector) * 1E8  # cents/kWh
        elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT and \
            model.surfaceplant.plant_type.value not in [PlantType.ABSORPTION_CHILLER, PlantType.HEAT_PUMP, PlantType.DISTRICT_HEATING]:
            econ.averageannualpumpingcosts.value = np.average(
                model.surfaceplant.PumpingkWh.value) * model.surfaceplant.electricity_cost_to_buy.value / 1E6  # M$/year
            LCOH = (capex_total_plus_infl + np.sum((
                econ.Coam.value + model.surfaceplant.PumpingkWh.value * model.surfaceplant.electricity_cost_to_buy.value / 1E6) * discount_vector)) / np.sum(
                model.surfaceplant.HeatkWhProduced.value * discount_vector) * 1E8  # cents/kWh
            LCOH = LCOH * 2.931  # $/MMBTU

        # co-gen
        elif model.surfaceplant.enduse_option.value in [EndUseOptions.COGENERATION_TOPPING_EXTRA_HEAT,
                                                        EndUseOptions.COGENERATION_TOPPING_EXTRA_ELECTRICITY,
                                                        EndUseOptions.COGENERATION_BOTTOMING_EXTRA_ELECTRICITY,
                                                        EndUseOptions.COGENERATION_BOTTOMING_EXTRA_HEAT,
                                                        EndUseOptions.COGENERATION_PARALLEL_EXTRA_HEAT,
                                                        EndUseOptions.COGENERATION_PARALLEL_EXTRA_ELECTRICITY]:
            capex_elec_plus_infl, capex_heat_plus_infl = _construction_inflation_cost_elec_heat()

            LCOE = (capex_elec_plus_infl + np.sum(Coam_elec * discount_vector)) / np.sum(model.surfaceplant.NetkWhProduced.value * discount_vector) * 1E8  # cents/kWh
            LCOH = (capex_heat_plus_infl +
                    np.sum((Coam_heat + model.surfaceplant.PumpingkWh.value * model.surfaceplant.electricity_cost_to_buy.value / 1E6) * discount_vector)) / np.sum(model.surfaceplant.HeatkWhProduced.value * discount_vector) * 1E8  # cents/kWh
            LCOH = LCOH * 2.931  # $/MMBTU

        elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT and model.surfaceplant.plant_type.value == PlantType.ABSORPTION_CHILLER:
            capex_total_plus_infl = _capex_total_plus_construction_inflation()

            LCOC = (capex_total_plus_infl + np.sum((
                econ.Coam.value + model.surfaceplant.PumpingkWh.value * model.surfaceplant.electricity_cost_to_buy.value / 1E6) * discount_vector)) / np.sum(
                model.surfaceplant.cooling_kWh_Produced.value * discount_vector) * 1E8  # cents/kWh
            LCOC = LCOC * 2.931  # $/Million Btu
        elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT and model.surfaceplant.plant_type.value == PlantType.HEAT_PUMP:
            capex_total_plus_infl = _capex_total_plus_construction_inflation()
            LCOH = (capex_total_plus_infl + np.sum(
                (econ.Coam.value + model.surfaceplant.PumpingkWh.value * model.surfaceplant.electricity_cost_to_buy.value / 1E6 +
                 model.surfaceplant.heat_pump_electricity_kwh_used.value * model.surfaceplant.electricity_cost_to_buy.value / 1E6) * discount_vector)) / np.sum(
                model.surfaceplant.HeatkWhProduced.value * discount_vector) * 1E8  # cents/kWh
            LCOH = LCOH * 2.931  # $/Million Btu
        elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT and model.surfaceplant.plant_type.value == PlantType.DISTRICT_HEATING:
            capex_total_plus_infl = _capex_total_plus_construction_inflation()
            LCOH = (capex_total_plus_infl + np.sum(
                (econ.Coam.value + model.surfaceplant.PumpingkWh.value * model.surfaceplant.electricity_cost_to_buy.value / 1E6 +
                 econ.annualngcost.value) * discount_vector)) / np.sum(
                model.surfaceplant.annual_heating_demand.value * discount_vector) * 1E2  # cents/kWh
            LCOH = LCOH * 2.931  # $/Million Btu
    elif econ.econmodel.value == EconomicModel.SAM_SINGLE_OWNER_PPA:
        # Designated as nominal (as opposed to real) in parameter tooltip text
        LCOE = econ.sam_economics_calculations.lcoe_nominal.quantity().to(convertible_unit(econ.LCOE.CurrentUnits.value)).magnitude
    else:
        # must be BICYCLE
        # average return on investment (tax and inflation adjusted)
        i_ave = econ.FIB.value * econ.BIR.value * (1 - econ.CTR.value) + (1 - econ.FIB.value) * econ.EIR.value
        # capital recovery factor
        CRF = i_ave / (1 - np.power(1 + i_ave, -model.surfaceplant.plant_lifetime.value))
        inflation_vector = np.power(1 + econ.RINFL.value, np.linspace(1, model.surfaceplant.plant_lifetime.value, model.surfaceplant.plant_lifetime.value))
        discount_vector = 1. / np.power(1 + i_ave, np.linspace(1, model.surfaceplant.plant_lifetime.value, model.surfaceplant.plant_lifetime.value))
        capex_total_plus_infl = _capex_total_plus_construction_inflation()

        NPV_cap = np.sum(capex_total_plus_infl * CRF * discount_vector)
        NPV_fc = np.sum(capex_total_plus_infl * econ.PTR.value * inflation_vector * discount_vector)
        NPV_it = np.sum(econ.CTR.value / (1 - econ.CTR.value) * (capex_total_plus_infl * CRF - econ.CCap.value / model.surfaceplant.plant_lifetime.value) * discount_vector)
        NPV_itc = capex_total_plus_infl * econ.RITC.value / (1 - econ.CTR.value)

        if model.surfaceplant.enduse_option.value == EndUseOptions.ELECTRICITY:
            NPV_oandm = np.sum(econ.Coam.value * inflation_vector * discount_vector)
            NPV_grt = econ.GTR.value / (1 - econ.GTR.value) * (NPV_cap + NPV_oandm + NPV_fc + NPV_it - NPV_itc)
            LCOE = (NPV_cap + NPV_oandm + NPV_fc + NPV_it + NPV_grt - NPV_itc) / np.sum(model.surfaceplant.NetkWhProduced.value * inflation_vector * discount_vector) * 1E8
        elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT and model.surfaceplant.plant_type.value not in [PlantType.ABSORPTION_CHILLER, PlantType.HEAT_PUMP, PlantType.DISTRICT_HEATING]:
            PumpingCosts = model.surfaceplant.PumpingkWh.value * model.surfaceplant.electricity_cost_to_buy.value / 1E6
            NPV_oandm = np.sum((econ.Coam.value + PumpingCosts) * inflation_vector * discount_vector)
            NPV_grt = econ.GTR.value / (1 - econ.GTR.value) * (NPV_cap + NPV_oandm + NPV_fc + NPV_it - NPV_itc)
            LCOH = (NPV_cap + NPV_oandm + NPV_fc + NPV_it + NPV_grt - NPV_itc) / np.sum(model.surfaceplant.HeatkWhProduced.value * inflation_vector * discount_vector) * 1E8
            LCOH = LCOH * 2.931  # $/MMBTU
        # co-gen
        elif model.surfaceplant.enduse_option.value in [EndUseOptions.COGENERATION_TOPPING_EXTRA_HEAT,
                                                        EndUseOptions.COGENERATION_TOPPING_EXTRA_ELECTRICITY,
                                                        EndUseOptions.COGENERATION_BOTTOMING_EXTRA_ELECTRICITY,
                                                        EndUseOptions.COGENERATION_BOTTOMING_EXTRA_HEAT,
                                                        EndUseOptions.COGENERATION_PARALLEL_EXTRA_HEAT,
                                                        EndUseOptions.COGENERATION_PARALLEL_EXTRA_ELECTRICITY]:
            capex_elec_plus_infl, capex_heat_plus_infl = _construction_inflation_cost_elec_heat()

            NPVcap_elec = np.sum(capex_elec_plus_infl * CRF * discount_vector)
            NPVfc_elec = np.sum(capex_elec_plus_infl * econ.PTR.value * inflation_vector * discount_vector)
            NPVit_elec = np.sum(econ.CTR.value / (1 - econ.CTR.value) * (capex_elec_plus_infl * CRF - CCap_elec / model.surfaceplant.plant_lifetime.value) * discount_vector)
            NPVitc_elec = capex_elec_plus_infl * econ.RITC.value / (1 - econ.CTR.value)
            NPVoandm_elec = np.sum(Coam_elec * inflation_vector * discount_vector)
            NPVgrt_elec = econ.GTR.value / (1 - econ.GTR.value) * (NPVcap_elec + NPVoandm_elec + NPVfc_elec + NPVit_elec - NPVitc_elec)

            LCOE = ((NPVcap_elec + NPVoandm_elec + NPVfc_elec + NPVit_elec + NPVgrt_elec - NPVitc_elec) /
                    np.sum(model.surfaceplant.NetkWhProduced.value * inflation_vector * discount_vector) * 1E8)

            NPV_cap_heat = np.sum(capex_heat_plus_infl * CRF * discount_vector)
            NPV_fc_heat = np.sum((1 + econ.inflrateconstruction.value) * (econ.CCap.value * (1.0 - econ.CAPEX_heat_electricity_plant_ratio.value)) * econ.PTR.value * inflation_vector * discount_vector)
            NPV_it_heat = np.sum(econ.CTR.value / (1 - econ.CTR.value) * (capex_heat_plus_infl * CRF - CCap_heat / model.surfaceplant.plant_lifetime.value) * discount_vector)
            NPV_itc_heat = capex_heat_plus_infl * econ.RITC.value / (1 - econ.CTR.value)
            NPV_oandm_heat = np.sum((econ.Coam.value * (1.0 - econ.CAPEX_heat_electricity_plant_ratio.value)) * inflation_vector * discount_vector)
            NPV_grt_heat = econ.GTR.value / (1 - econ.GTR.value) * (NPV_cap_heat + NPV_oandm_heat + NPV_fc_heat + NPV_it_heat - NPV_itc_heat)

            LCOH = ((NPV_cap_heat + NPV_oandm_heat + NPV_fc_heat + NPV_it_heat + NPV_grt_heat - NPV_itc_heat) /
                    np.sum(model.surfaceplant.HeatkWhProduced.value * inflation_vector * discount_vector) * 1E8)
            LCOH = LCOH * 2.931  # $/MMBTU

        elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT and model.surfaceplant.plant_type.value == PlantType.ABSORPTION_CHILLER:
            PumpingCosts = model.surfaceplant.PumpingkWh.value * model.surfaceplant.electricity_cost_to_buy.value / 1E6
            NPV_oandm = np.sum((econ.Coam.value + PumpingCosts) * inflation_vector * discount_vector)
            NPV_grt = econ.GTR.value / (1 - econ.GTR.value) * (NPV_cap + NPV_oandm + NPV_fc + NPV_it - NPV_itc)
            LCOC = (NPV_cap + NPV_oandm + NPV_fc + NPV_it + NPV_grt - NPV_itc) / np.sum(
                model.surfaceplant.cooling_kWh_Produced.value * inflation_vector * discount_vector) * 1E8
            LCOC = LCOC * 2.931  # $/MMBTU

        elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT and model.surfaceplant.plant_type.value == PlantType.HEAT_PUMP:
            PumpingCosts = model.surfaceplant.PumpingkWh.value * model.surfaceplant.electricity_cost_to_buy.value / 1E6
            HeatPumpElecCosts = model.surfaceplant.heat_pump_electricity_kwh_used.value * model.surfaceplant.electricity_cost_to_buy.value / 1E6
            NPV_oandm = np.sum((econ.Coam.value + PumpingCosts + HeatPumpElecCosts) * inflation_vector * discount_vector)
            NPV_grt = econ.GTR.value / (1 - econ.GTR.value) * (NPV_cap + NPV_oandm + NPV_fc + NPV_it - NPV_itc)
            LCOH = (NPV_cap + NPV_oandm + NPV_fc + NPV_it + NPV_grt - NPV_itc) / np.sum(
                model.surfaceplant.HeatkWhProduced.value * inflation_vector * discount_vector) * 1E8
            LCOH = LCOH * 2.931  # $/MMBTU

        elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT and model.surfaceplant.plant_type.value == PlantType.DISTRICT_HEATING:
            PumpingCosts = model.surfaceplant.PumpingkWh.value * model.surfaceplant.electricity_cost_to_buy.value / 1E6
            NPV_oandm = np.sum(
                (econ.Coam.value + PumpingCosts + econ.annualngcost.value) * inflation_vector * discount_vector)
            NPV_grt = econ.GTR.value / (1 - econ.GTR.value) * (NPV_cap + NPV_oandm + NPV_fc + NPV_it - NPV_itc)
            LCOH = (NPV_cap + NPV_oandm + NPV_fc + NPV_it + NPV_grt - NPV_itc) / np.sum(
                model.surfaceplant.annual_heating_demand.value * inflation_vector * discount_vector) * 1E2
            LCOH = LCOH * 2.931  # $/MMBTU

    return LCOE, LCOH, LCOC


class Economics:
    """
     Class to support the default economic calculations in GEOPHIRES
    """

    def __init__(self, model: Model):
        """
        The __init__ function is called automatically when a class is instantiated.
        It initializes the attributes of an object, and sets default values for certain arguments that can be overridden
        by user input.
        The __init__ function is used to set up all the parameters in Economics.
        Set up all the Parameters that will be predefined by this class using the different types of parameter classes.
        Setting up includes giving it a name, a default value, The Unit Type (length, volume, temperature, etc.) and
        Unit Name of that value, sets it as required (or not), sets allowable range, the error message if that range
        is exceeded, the ToolTip Text, and the name of teh class that created it.
        This includes setting up temporary variables that will be available to all the class but noy read in by user,
        or used for Output
        This also includes all Parameters that are calculated and then published using the Printouts function.
        If you choose to subclass this master class, you can do so before or after you create your own parameters.
        If you do, you can also choose to call this method from you class, which will effectively add and set all
        these parameters to your class.
        :param model: The container class of the application, giving access to everything else, including the logger
        :type model: :class:`~geophires_x.Model.Model`
        :return: None
        """

        model.logger.info(f'Init {__class__!s}: {sys._getframe().f_code.co_name}')

        # These dictionaries contain a list of all the parameters set in this object, stored as "Parameter" and
        # "OutputParameter" Objects.  This will allow us later to access them in a user interface and get that list,
        # along with unit type, preferred units, etc.
        self.ParameterDict = {}
        self.OutputParameterDict = {}

        # Note: setting Valid to False for any of the cost parameters forces GEOPHIRES to use it's builtin cost engine.
        # This is the default.
        self.econmodel = self.ParameterDict[self.econmodel.Name] = intParameter(
            "Economic Model",
            DefaultValue=EconomicModel.STANDARDIZED_LEVELIZED_COST.int_value,
            AllowableRange=[1, 2, 3, 4, 5],
            ValuesEnum=EconomicModel,
            Required=True,
            ErrMessage="assume default economic model (2)",
            ToolTipText="Specify the economic model to calculate the levelized cost of energy. " +
                        '; '.join([f'{it.int_value}: {it.value}' for it in EconomicModel])
        )

        self.ccstimfixed = self.ParameterDict[self.ccstimfixed.Name] = floatParameter(
            "Reservoir Stimulation Capital Cost",
            DefaultValue=-1.0,
            Min=0,
            Max=1000,
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS,
            Provided=False,
            Valid=False,
            ToolTipText='Total reservoir stimulation capital cost, including indirect costs and contingency. '
                        f'For traditional hydrothermal reservoirs, this parameter should be set to $0.'
        )

        max_stimulation_cost_per_well_MUSD = 100
        self.stimulation_cost_per_injection_well = \
          self.ParameterDict[self.stimulation_cost_per_injection_well.Name] = floatParameter(
            'Reservoir Stimulation Capital Cost per Injection Well',
            DefaultValue=1.25,
            Min=0,
            Max=max_stimulation_cost_per_well_MUSD,
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS,
            Provided=False,
            ToolTipText='Reservoir stimulation capital cost per injection well before indirect costs and contingency'
        )

        stimulation_cost_per_production_well_default_value_MUSD = 0
        stimulation_cost_per_production_well_default_value_note = \
            '. By default, only the injection wells are assumed to be stimulated unless this parameter is provided.' \
                if stimulation_cost_per_production_well_default_value_MUSD == 0 else ''
        self.stimulation_cost_per_production_well = \
          self.ParameterDict[self.stimulation_cost_per_production_well.Name] = floatParameter(
            'Reservoir Stimulation Capital Cost per Production Well',
            DefaultValue=stimulation_cost_per_production_well_default_value_MUSD,
            Min=0,
            Max=max_stimulation_cost_per_well_MUSD,
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS,
            ToolTipText=f'Reservoir stimulation capital cost per production well before indirect costs and contingency'
                        f'{stimulation_cost_per_production_well_default_value_note}'
        )

        self.ccstimadjfactor = self.ParameterDict[self.ccstimadjfactor.Name] = floatParameter(
            "Reservoir Stimulation Capital Cost Adjustment Factor",
            DefaultValue=1.0,
            Min=0,
            Max=10,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            Provided=False,
            Valid=True,
            ToolTipText="Multiplier for reservoir stimulation capital cost correlation"
        )
        self.stimulation_indirect_capital_cost_percentage = \
          self.ParameterDict[self.stimulation_indirect_capital_cost_percentage.Name] = floatParameter(
            'Reservoir Stimulation Indirect Capital Cost Percentage',
            DefaultValue=5,
            Min=0,
            Max=100,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.PERCENT,
            CurrentUnits=PercentUnit.PERCENT,
            ToolTipText=f'The indirect capital cost for reservoir stimulation, '
                        f'calculated as a percentage of the direct cost. '
                        f'(Not applied if {self.ccstimfixed.Name} is provided.)'
        )

        self.ccexplfixed = self.ParameterDict[self.ccexplfixed.Name] = floatParameter(
            "Exploration Capital Cost",
            DefaultValue=-1.0,
            Min=0,
            Max=1000,
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS,
            Provided=False,
            Valid=False,
            ToolTipText="Total exploration capital cost"
        )
        self.ccexpladjfactor = self.ParameterDict[self.ccexpladjfactor.Name] = floatParameter(
            "Exploration Capital Cost Adjustment Factor",
            DefaultValue=1.0,
            Min=0,
            Max=10,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            Provided=False,
            Valid=True,
            ToolTipText="Multiplier for built-in exploration capital cost correlation"
        )

        per_injection_well_cost_name = 'Injection Well Drilling and Completion Capital Cost'
        self.per_production_well_cost = self.ParameterDict[self.per_production_well_cost.Name] = floatParameter(
            "Well Drilling and Completion Capital Cost",
            DefaultValue=-1,
            Min=0,
            Max=200,
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS,
            Provided=False,
            Valid=False,
            ToolTipText=f'Well drilling and completion capital cost per well including indirect costs and contingency. '
                        f'Applied to production wells; also applied to injection wells unless '
                        f'{per_injection_well_cost_name} is provided.'
        )
        self.per_injection_well_cost = self.ParameterDict[self.per_injection_well_cost.Name] = floatParameter(
            per_injection_well_cost_name,
            DefaultValue=self.per_production_well_cost.DefaultValue,
            Min=0,
            Max=200,
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS,
            Provided=False,
            Valid=False,
            ToolTipText='Injection well drilling and completion capital cost per well '
                        'including indirect costs and contingency'
        )

        inj_well_cost_adjustment_factor_name = "Injection Well Drilling and Completion Capital Cost Adjustment Factor"
        self.production_well_cost_adjustment_factor = self.ParameterDict[self.production_well_cost_adjustment_factor.Name] = floatParameter(
            "Well Drilling and Completion Capital Cost Adjustment Factor",
            DefaultValue=1.0,
            Min=0,
            Max=10,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            Provided=False,
            Valid=True,
            ToolTipText=f'Well Drilling and Completion Capital Cost Adjustment Factor. Applies to production wells; '
                        f'also applies to injection wells unless a value is provided for '
                        f'{inj_well_cost_adjustment_factor_name}.'
        )
        self.injection_well_cost_adjustment_factor = self.ParameterDict[self.injection_well_cost_adjustment_factor.Name] = floatParameter(
            inj_well_cost_adjustment_factor_name,
            DefaultValue=self.production_well_cost_adjustment_factor.DefaultValue,
            Min=self.production_well_cost_adjustment_factor.Min,
            Max=self.production_well_cost_adjustment_factor.Max,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            Provided=False,
            Valid=True,
            ToolTipText="Injection Well Drilling and Completion Capital Cost Adjustment Factor. "
                        f"If not provided, this value will be set automatically to the same value as "
                        f"{self.production_well_cost_adjustment_factor.Name}."
        )

        self.oamwellfixed = self.ParameterDict[self.oamwellfixed.Name] = floatParameter(
            "Wellfield O&M Cost",
            DefaultValue=-1.0,
            Min=0,
            Max=100,
            UnitType=Units.CURRENCYFREQUENCY,
            PreferredUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            CurrentUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            Provided=False,
            Valid=False,
            ToolTipText="Total annual wellfield O&M cost"
        )
        self.oamwelladjfactor = self.ParameterDict[self.oamwelladjfactor.Name] = floatParameter(
            "Wellfield O&M Cost Adjustment Factor",
            DefaultValue=1.0,
            Min=0,
            Max=10,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            Provided=False,
            Valid=True,
            ToolTipText="Multiplier for built-in wellfield O&M cost correlation"
        )

        self.ccplantfixed = self.ParameterDict[self.ccplantfixed.Name] = floatParameter(
            "Surface Plant Capital Cost",
            DefaultValue=-1.0,
            Min=0,
            Max=10000,
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS,
            Provided=False,
            Valid=False,
            ToolTipText="Total surface plant capital cost"
        )
        self.ccplantadjfactor = self.ParameterDict[self.ccplantadjfactor.Name] = floatParameter(
            "Surface Plant Capital Cost Adjustment Factor",
            DefaultValue=1.0,
            Min=0,
            Max=10,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            Provided=False,
            Valid=True,
            ToolTipText="Multiplier for built-in surface plant capital cost correlation"
        )
        self._default_Power_plant_cost_USD_per_kWe = 3000
        self.Power_plant_cost_per_kWe = self.ParameterDict[self.Power_plant_cost_per_kWe.Name] = floatParameter(
            "Capital Cost for Power Plant for Electricity Generation",
            DefaultValue=self._default_Power_plant_cost_USD_per_kWe,
            Min=0.0,
            Max=10000.0,
            UnitType=Units.ENERGYCOST,
            PreferredUnits=EnergyCostUnit.DOLLARSPERKW,
            CurrentUnits=EnergyCostUnit.DOLLARSPERKW,
            ErrMessage=f'assume default Power plant capital cost per kWe '
                       f'({self._default_Power_plant_cost_USD_per_kWe} USD/kWe)'
        )

        self.ccgathfixed = self.ParameterDict[self.ccgathfixed.Name] = floatParameter(
            "Field Gathering System Capital Cost",
            DefaultValue=-1.0,
            Min=0,
            Max=100,
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS,
            Provided=False,
            Valid=False,
            ToolTipText="Total field gathering system capital cost"
        )
        self.ccgathadjfactor = self.ParameterDict[self.ccgathadjfactor.Name] = floatParameter(
            "Field Gathering System Capital Cost Adjustment Factor",
            DefaultValue=1.0,
            Min=0,
            Max=10,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            Provided=False,
            Valid=True,
            ToolTipText="Multiplier for built-in field gathering system capital cost correlation"
        )
        self.oamplantfixed = self.ParameterDict[self.oamplantfixed.Name] = floatParameter(
            "Surface Plant O&M Cost",
            DefaultValue=-1.0,
            Min=0,
            Max=100,
            UnitType=Units.CURRENCYFREQUENCY,
            PreferredUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            CurrentUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            Provided=False,
            Valid=False,
            ToolTipText="Total annual surface plant O&M cost"
        )
        self.oamplantadjfactor = self.ParameterDict[self.oamplantadjfactor.Name] = floatParameter(
            "Surface Plant O&M Cost Adjustment Factor",
            DefaultValue=1.0,
            Min=0,
            Max=10,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            Provided=False,
            Valid=True,
            ToolTipText="Multiplier for built-in surface plant O&M cost correlation"
        )
        self.oamwaterfixed = self.ParameterDict[self.oamwaterfixed.Name] = floatParameter(
            "Water Cost",
            DefaultValue=-1.0,
            Min=0,
            Max=100,
            UnitType=Units.CURRENCYFREQUENCY,
            PreferredUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            CurrentUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            Provided=False,
            Valid=False,
            ToolTipText="Total annual make-up water cost"
        )
        self.oamwateradjfactor = self.ParameterDict[self.oamwateradjfactor.Name] = floatParameter(
            "Water Cost Adjustment Factor",
            DefaultValue=1.0,
            Min=0,
            Max=10,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            Provided=False,
            Valid=True,
            ToolTipText="Multiplier for built-in make-up water cost correlation"
        )
        self.totalcapcost = self.ParameterDict[self.totalcapcost.Name] = floatParameter(
            "Total Capital Cost",
            DefaultValue=-1.0,
            Min=0,
            # pint treats GUSD as billions of dollars (G for giga)
            Max=quantity(100, 'GUSD').to('MUSD').magnitude,
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS,
            Provided=False,
            Valid=False,
            ErrMessage="calculate total capital cost using user-provided costs or" +
                       " built-in correlations for each category.",
            ToolTipText="Total initial capital cost."
        )
        self.oamtotalfixed = self.ParameterDict[self.oamtotalfixed.Name] = floatParameter(
            "Total O&M Cost",
            DefaultValue=-1.0,
            Min=0,
            Max=100,
            UnitType=Units.CURRENCYFREQUENCY,
            PreferredUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            CurrentUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            Provided=False,
            Valid=False,
            ErrMessage="calculate total O&M cost using user-provided costs or built-in correlations for each category.",
            ToolTipText="Total initial O&M cost."
        )
        self.timestepsperyear = self.ParameterDict[self.timestepsperyear.Name] = intParameter(
            "Time steps per year",
            DefaultValue=4,
            AllowableRange=list(range(1, 101, 1)),
            UnitType=Units.NONE,
            Required=True,
            ErrMessage="assume default number of time steps per year (4)",
            ToolTipText='Number of internal simulation time steps per year. GEOPHIRES assumes linear time '
                        'discretization with a user-provided number of time steps per year over the lifetime of the '
                        'plant. The default is four time steps per year, meaning a time step of 3 months. '
                        'At every time step, GEOPHIRES calculates the reservoir output temperature, production '
                        'wellhead temperature, direct-use heat and/or electricity power output (in MW), pressure '
                        'drops and pumping power. On an annual basis, GEOPHIRES calculates the O&M costs and '
                        'direct-use heat and/or electricity production. To investigate seasonal effects, e.g., to '
                        'assess the impact of more geothermal heat demand for district heating in winter than in '
                        'summer, the user can select a smaller time step, e.g., a month (or 12 time steps per year). '
                        'For even shorter timescale effects, e.g., to account for an hourly varying ambient '
                        'temperature or investigate the response in plant operation to a fluctuating revenue rate), '
                        'the user can select an even smaller time step, e.g., 1 h (or 8760 time steps per year).'
        )
        self.FCR = self.ParameterDict[self.FCR.Name] = floatParameter(
            "Fixed Charge Rate",
            DefaultValue=0.1,
            Min=0.0,
            Max=1.0,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            ErrMessage="assume default fixed charge rate (0.1)",
            ToolTipText="Fixed charge rate (FCR) used in the Fixed Charge Rate Model"
        )

        discount_rate_default_val = 0.07
        self.discountrate = self.ParameterDict[self.discountrate.Name] = floatParameter(
            "Discount Rate",
            DefaultValue=discount_rate_default_val,
            Min=0.0,
            Max=1.0,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            ErrMessage=f'assume default discount rate ({discount_rate_default_val})',
            ToolTipText="Discount rate used in the Standard Levelized Cost Model and SAM Economic Models. "
                        "Discount Rate is synonymous with Fixed Internal Rate. If one is provided, the other's value "
                        "will be automatically set to the same value."
        )

        self.royalty_rate = self.ParameterDict[self.royalty_rate.Name] = floatParameter(
            'Royalty Rate',
            DefaultValue=0.,
            Min=0.0,
            Max=1.0,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            ToolTipText="The fraction of the project's gross annual revenue paid to the royalty holder. "
                        "This is modeled as a variable production-based operating expense, reducing the developer's "
                        "taxable income."
        )

        self.royalty_escalation_rate = self.ParameterDict[self.royalty_escalation_rate.Name] = floatParameter(
            'Royalty Rate Escalation',
            DefaultValue=0.,
            Min=0.0,
            Max=1.0,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            ToolTipText="The additive amount the royalty rate increases each year. For example, a value of 0.001 "
                        "increases a 4% rate (0.04) to 4.1% (0.041) in the next year."
        )

        self.royalty_escalation_rate_start_year = self.ParameterDict[self.royalty_escalation_rate_start_year.Name] = intParameter(
            'Royalty Rate Escalation Start Year',
            DefaultValue=1,
            AllowableRange=list(range(1, model.surfaceplant.plant_lifetime.AllowableRange[-1], 1)),
            UnitType=Units.NONE,
            PreferredUnits=TimeUnit.YEAR,
            CurrentUnits=TimeUnit.YEAR,
            ToolTipText=f'The first year that the {self.royalty_escalation_rate.Name} is applied. '
                        f'{_YEAR_INDEX_VALUE_EXPLANATION_SNIPPET}.'
        )

        maximum_royalty_rate_default_val = 1.0
        self.maximum_royalty_rate = self.ParameterDict[self.maximum_royalty_rate.Name] = floatParameter(
            'Royalty Rate Maximum',
            DefaultValue=maximum_royalty_rate_default_val,
            Min=0.0,
            Max=1.0,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            ToolTipText=f"The maximum royalty rate after escalation, expressed as a fraction (e.g., 0.06 for a 6% cap)."
                        f"{' Defaults to 100% (no effective cap).' if maximum_royalty_rate_default_val == 1.0 else ''}"
        )

        # TODO support custom royalty rate schedule as a list parameter
        #  (as an alternative to specifying rate/escalation/max)

        self.royalty_holder_discount_rate = self.ParameterDict[self.royalty_holder_discount_rate.Name] = floatParameter(
            'Royalty Holder Discount Rate',
            DefaultValue=0.05,
            Min=0.0,
            Max=1.0,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            ToolTipText="The discount rate used to calculate the Net Present Value (NPV) of the royalty holder's "
                        "income stream. This rate should reflect the royalty holder's specific risk profile and is "
                        "separate from the main project discount rate."
        )


        self.discount_initial_year_cashflow = self.ParameterDict[self.discount_initial_year_cashflow.Name] = boolParameter(
            'Discount Initial Year Cashflow',
            DefaultValue=False,
            UnitType=Units.NONE,
            ToolTipText='Whether to discount cashflow in the initial project year when calculating NPV '
                        '(Net Present Value). '
                        'The default value of False conforms to NREL\'s standard convention for NPV calculation '
                        '(Short W et al, 1995. https://www.nrel.gov/docs/legosti/old/5173.pdf). '
                        'A value of True will, by contrast, cause NPV calculation to follow the convention used by '
                        'Excel, Google Sheets, and other common spreadsheet software. '
                        'Although NREL\'s NPV convention may typically be considered more technically correct, '
                        'Excel-style NPV calculation might be preferred for familiarity '
                        'or compatibility with existing business processes. '
                        'See https://github.com/NREL/GEOPHIRES-X/discussions/344 for further details.'
        )

        default_fraction_in_bonds = 0.5
        self.FIB = self.ParameterDict[self.FIB.Name] = floatParameter(
            "Fraction of Investment in Bonds",
            DefaultValue=default_fraction_in_bonds,
            Min=0.0,
            Max=1.0,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            ErrMessage=f"assume default fraction of investment in bonds ({default_fraction_in_bonds})",
            ToolTipText="Fraction of geothermal project financing through bonds (debt/loans)."
        )

        default_bond_interest_rate = 0.05
        self.BIR = self.ParameterDict[self.BIR.Name] = floatParameter(
            "Inflated Bond Interest Rate",
            DefaultValue=default_bond_interest_rate,
            Min=0.0,
            Max=1.0,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            ErrMessage=f"assume default inflated bond interest rate ({default_bond_interest_rate})",
            ToolTipText="Inflated bond interest rate (for debt/loans)"
        )

        self.bond_interest_rate_during_construction = self.ParameterDict[self.bond_interest_rate_during_construction.Name] = floatParameter(
            'Inflated Bond Interest Rate During Construction',
            DefaultValue=self.BIR.DefaultValue,
            Min=0.0,
            Max=1.0,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            ToolTipText='Inflated bond interest rate during construction (for debt/loans)'
        )

        self.EIR = self.ParameterDict[self.EIR.Name] = floatParameter(
            "Inflated Equity Interest Rate",
            DefaultValue=0.1,
            Min=0.0,
            Max=1.0,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            ErrMessage="assume default inflated equity interest rate (0.1)",
            ToolTipText="Inflated equity interest rate (see docs)"
        )
        self.RINFL = self.ParameterDict[self.RINFL.Name] = floatParameter(
            "Inflation Rate",
            DefaultValue=0.02,
            Min=0.0,
            Max=1.0,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            ErrMessage="assume default inflation rate (0.02)",
            ToolTipText="Inflation rate"
        )
        self.CTR = self.ParameterDict[self.CTR.Name] = floatParameter(
            "Combined Income Tax Rate",
            DefaultValue=0.02,
            Min=0.0,
            Max=1.0,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            ErrMessage="assume default combined income tax rate (0.3)",
            ToolTipText="Combined income tax rate (see docs)"
        )
        self.GTR = self.ParameterDict[self.GTR.Name] = floatParameter(
            "Gross Revenue Tax Rate",
            DefaultValue=0.02,
            Min=0.0,
            Max=1.0,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            ErrMessage="assume default gross revenue tax rate (0)",
            ToolTipText="Gross revenue tax rate (see docs)"
        )
        self.RITC = self.ParameterDict[self.RITC.Name] = floatParameter(
            "Investment Tax Credit Rate",
            DefaultValue=0.0,
            Min=0.0,
            Max=1.0,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            ErrMessage="assume default investment tax credit rate (0)",
            ToolTipText="Investment tax credit rate (see docs)"
        )
        self.PTR = self.ParameterDict[self.PTR.Name] = floatParameter(
            "Property Tax Rate",
            DefaultValue=0.0,
            Min=0.0,
            Max=1.0,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            ErrMessage="assume default property tax rate (0)",
            ToolTipText="Property tax rate (see docs)"
        )
        # noinspection SpellCheckingInspection
        self.inflrateconstruction = self.ParameterDict[self.inflrateconstruction.Name] = floatParameter(
            "Inflation Rate During Construction",
            DefaultValue=0.0,
            Min=0.0,
            Max=1.0,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.PERCENT,
            CurrentUnits=PercentUnit.TENTH,
            ErrMessage="assume default inflation rate during construction (0)",
            ToolTipText='The total inflation rate applied to capital costs over the entire construction period, '
                        'entered as a fraction (e.g., 0.15 for 15%). '
                        'This value defines the Accrued financing during construction output. '
                        'Note: For SAM Economic Models, if this parameter is not provided, inflation costs will be '
                        'calculated automatically by compounding Inflation Rate over Construction Years.'
        )

        self.construction_capex_schedule = self.ParameterDict[self.construction_capex_schedule.Name] = listParameter(
            CONSTRUCTION_CAPEX_SCHEDULE_PARAMETER_NAME,
            DefaultValue=[1.],
            Min=0.0,
            Max=1.0,
            ToolTipText=f'A list of fractions of the total overnight CAPEX spent in each construction year. '
                        f'For example, for 3 construction years with 10% in the first year, 40% in the second, '
                        f'and 50% in the third, provide {CONSTRUCTION_CAPEX_SCHEDULE_PARAMETER_NAME} = 0.1,0.4,0.5. '
                        f'The schedule will be automatically interpolated to match the number of construction years '
                        f'and normalized to sum to 1.0.'
        )

        bond_financing_start_year_name = 'Bond Financing Start Year'
        min_bond_financing_start_year = -1*(MAX_CONSTRUCTION_YEARS - 1)
        default_bond_financing_start_year = min_bond_financing_start_year
        latest_allowed_bond_financing_start_year_index = 0
        self.bond_financing_start_year = self.ParameterDict[self.bond_financing_start_year.Name] = intParameter(
            bond_financing_start_year_name,
            DefaultValue=default_bond_financing_start_year,
            AllowableRange=list(range(
                min_bond_financing_start_year,
                latest_allowed_bond_financing_start_year_index + 1,
                1)),
            UnitType=Units.TIME,
            PreferredUnits=TimeUnit.YEAR,
            CurrentUnits=TimeUnit.YEAR,
            ToolTipText=f'By default, bond financing (debt/loans) starts during the first construction year '
                        f'(if {self.FIB.Name} is >0). '
                        f'Provide {bond_financing_start_year_name} to delay the '
                        f'start of bond financing during construction; years prior to {bond_financing_start_year_name} '
                        f'will be financed with equity only. '
                        f'{_YEAR_INDEX_VALUE_EXPLANATION_SNIPPET}; the first construction year has the year index '
                        f'{{({model.surfaceplant.construction_years.Name} - 1) * -1}})'
                        f' and the final construction year index is 0. '
                        f'For example, a project with 4 construction years '
                        f'where bond financing starts on the third '
                        f'{model.surfaceplant.construction_years.Name[:-1].lower()} '
                        f'would have a {bond_financing_start_year_name} value of -1; construction starts in Year -3, '
                        f'the second year is Year -2, and the final 2 bond-financed construction years are Year -1 '
                        f'and Year 0. '
                        f'Bond financing will start on the first construction year if the specified year index is '
                        f'prior to the first construction year.'
        )

        self.contingency_percentage = self.ParameterDict[self.contingency_percentage.Name] = floatParameter(
            'Contingency Percentage',
            DefaultValue=15.,
            Min=0.,
            Max=100.,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.PERCENT,
            CurrentUnits=PercentUnit.PERCENT,
            ToolTipText='The contingency percentage applied to the direct capital costs for stimulation, '
                        'field gathering system, exploration, and surface plant. '
                        '(Note: well drilling and completion costs do not have contingency applied and are not '
                        'affected by this parameter.)'
        )

        self.wellcorrelation = self.ParameterDict[self.wellcorrelation.Name] = intParameter(
            "Well Drilling Cost Correlation",
            DefaultValue=WellDrillingCostCorrelation.VERTICAL_LARGE_INT1.int_value,
            AllowableRange=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17],
            ValuesEnum=WellDrillingCostCorrelation,
            UnitType=Units.NONE,
            ErrMessage="assume default well drilling cost correlation (10)",
            ToolTipText="Select the built-in well drilling and completion cost correlation: " +
                        '; '.join([f'{it.int_value}: {it.value}'
                                   for it in WellDrillingCostCorrelation]) +
                        f'. '
                        f'Baseline correlations (1-4) are from '
                        f'{_WellDrillingCostCorrelationCitation.NREL_COST_CURVE_2025.value}.'
                        f' Intermediate and ideal correlations (6-17) are from '
                        f'{_WellDrillingCostCorrelationCitation.GEOVISION.value}.'

        )
        self.DoAddOnCalculations = self.ParameterDict[self.DoAddOnCalculations.Name] = boolParameter(
            "Do AddOn Calculations",
            DefaultValue=False,
            UnitType=Units.NONE,
            Required=False,
            ErrMessage="assume default: no economics calculations",
            ToolTipText="Set to true if you want the add-on economics calculations to be made"
        )
        self.DoCarbonCalculations = self.ParameterDict[self.DoCarbonCalculations.Name] = boolParameter(
            "Do Carbon Price Calculations",
            DefaultValue=False,
            UnitType=Units.NONE,
            Required=False,
            ErrMessage="assume default: no Carbon Credit calculations",
            ToolTipText="Set to true if you want the Carbon Credit economics calculations to be made"
        )
        self.DoSDACGTCalculations = self.ParameterDict[self.DoSDACGTCalculations.Name] = boolParameter(
            "Do S-DAC-GT Calculations",
            DefaultValue=False,
            UnitType=Units.NONE,
            Required=False,
            ErrMessage="assume default: no S-DAC-GT calculations",
            ToolTipText="Set to true if you want the S-DAC-GT economics calculations to be made"
        )

        self.Vertical_drilling_cost_per_m = self.ParameterDict[self.Vertical_drilling_cost_per_m.Name] = floatParameter(
            "All-in Vertical Drilling Costs",
            DefaultValue=1000.0,
            Min=0.0,
            Max=10_000.0,
            UnitType=Units.COSTPERDISTANCE,
            PreferredUnits=CostPerDistanceUnit.DOLLARSPERM,
            CurrentUnits=CostPerDistanceUnit.DOLLARSPERM,
            ErrMessage="assume default all-in cost for drill vertical well segment(s) (1000 $/m)",
            ToolTipText="Set user specified all-in cost per meter of vertical drilling, including drilling, casing, "
                        "cement, insulated insert"
        )
        self.Nonvertical_drilling_cost_per_m = self.ParameterDict[
            self.Nonvertical_drilling_cost_per_m.Name] = floatParameter(
            "All-in Nonvertical Drilling Costs",
            DefaultValue=1300.0,
            Min=0.0,
            Max=15_000.0,
            UnitType=Units.COSTPERDISTANCE,
            PreferredUnits=CostPerDistanceUnit.DOLLARSPERM,
            CurrentUnits=CostPerDistanceUnit.DOLLARSPERM,
            ErrMessage="assume default all-in cost for drill non-vertical well segment(s) ($1300/m)",
            ToolTipText="Set user specified all-in cost per meter of non-vertical drilling, including drilling, "
                        "casing, cement, insulated insert"
        )
        self.wellfield_indirect_capital_cost_percentage = self.ParameterDict[self.wellfield_indirect_capital_cost_percentage.Name] = floatParameter(
            'Well Drilling and Completion Indirect Capital Cost Percentage',
            DefaultValue=5,
            Min=0,
            Max=100,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.PERCENT,
            CurrentUnits=PercentUnit.PERCENT,
            ToolTipText=f'The indirect capital cost for well drilling and completion of all wells (the wellfield), '
                        f'calculated as a percentage of the direct cost.'
        )

        default_indirect_capital_cost_percentage = 12
        self.indirect_capital_cost_percentage = \
          self.ParameterDict[self.indirect_capital_cost_percentage.Name] = floatParameter(
            'Indirect Capital Cost Percentage',
            DefaultValue=default_indirect_capital_cost_percentage,
            Min=0,
            Max=100,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.PERCENT,
            CurrentUnits=PercentUnit.PERCENT,
            ToolTipText=f'The indirect cost percentage applied to capital costs '
                        f'(default {default_indirect_capital_cost_percentage}%). '
                        f'This value is used for all cost categories including surface plant, field gathering system, '
                        f'and exploration except when a category-specific indirect cost parameter is defined or '
                        f'provided. '
                        f'Wellfield costs use {self.wellfield_indirect_capital_cost_percentage.Name} '
                        f'(default {self.wellfield_indirect_capital_cost_percentage.DefaultValue}%). '
                        f'Stimulation costs use {self.stimulation_indirect_capital_cost_percentage.Name} '
                        f'(default {self.stimulation_indirect_capital_cost_percentage.DefaultValue}%).'
        )

        # absorption chiller
        self.chillercapex = self.ParameterDict[self.chillercapex.Name] = floatParameter(
            "Absorption Chiller Capital Cost",
            value=-1.0,
            DefaultValue=5,
            Min=0,
            Max=100,
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS,
            Provided=False,
            Valid=False,
            ToolTipText="Absorption chiller capital cost"
        )
        self.chilleropex = self.ParameterDict[self.chilleropex.Name] = floatParameter(
            "Absorption Chiller O&M Cost",
            value=-1.0,
            DefaultValue=1,
            Min=0,
            Max=100,
            UnitType=Units.CURRENCYFREQUENCY,
            PreferredUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            CurrentUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            Provided=False,
            Valid=False,
            ToolTipText="Absorption chiller O&M cost"
        )

        # heat pump
        self.heatpumpcapex = self.ParameterDict[self.heatpumpcapex.Name] = floatParameter(
            "Heat Pump Capital Cost",
            value=-1.0,
            DefaultValue=5,
            Min=0,
            Max=100,
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS,
            Provided=False,
            Valid=False,
            ToolTipText="Heat pump capital cost"
        )

        # district heating
        self.ngprice = self.ParameterDict[self.ngprice.Name] = floatParameter(
            "Peaking Fuel Cost Rate",
            DefaultValue=0.034,
            Min=0.0,
            Max=1.0,
            UnitType=Units.ENERGYCOST,
            PreferredUnits=EnergyCostUnit.DOLLARSPERKWH,
            CurrentUnits=EnergyCostUnit.DOLLARSPERKWH,
            ErrMessage="assume default peaking fuel rate ($0.034/kWh)",
            ToolTipText="Price of peaking fuel for peaking boilers"
        )
        self.peakingboilerefficiency = self.ParameterDict[self.peakingboilerefficiency.Name] = floatParameter(
            "Peaking Boiler Efficiency",
            DefaultValue=0.85,
            Min=0,
            Max=1,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            Provided=False,
            Valid=False,
            ErrMessage="assume default peaking boiler efficiency (85%)",
            ToolTipText="Peaking boiler efficiency"
        )
        self._default_peaking_boiler_cost_USD_per_kW = 65
        self.peaking_boiler_cost_per_kW = self.ParameterDict[self.peaking_boiler_cost_per_kW.Name] = floatParameter(
            "Peaking Boiler Cost per kW",
            DefaultValue=self._default_peaking_boiler_cost_USD_per_kW,
            Min=0,
            Max=1000,
            UnitType=Units.ENERGYCOST,
            PreferredUnits=EnergyCostUnit.DOLLARSPERKW,
            CurrentUnits=EnergyCostUnit.DOLLARSPERKW,
            Required=False,
            ToolTipText="Peaking boiler cost per kW of maximum peaking boiler demand"
        )
        self.dhpipingcostrate = self.ParameterDict[self.dhpipingcostrate.Name] = floatParameter(
            "District Heating Piping Cost Rate",
            DefaultValue=1200,
            Min=0,
            Max=10000,
            UnitType=Units.COSTPERDISTANCE,
            PreferredUnits=CostPerDistanceUnit.DOLLARSPERM,
            CurrentUnits=CostPerDistanceUnit.DOLLARSPERM,
            Provided=False,
            Valid=False,
            ErrMessage="assume default district heating piping cost rate ($1,200/m)",
            ToolTipText="District heating piping cost rate ($/m)"
        )
        self.dhtotaldistrictnetworkcost = self.ParameterDict[self.dhtotaldistrictnetworkcost.Name] = floatParameter(
            "Total District Heating Network Cost",
            DefaultValue=10,
            Min=0,
            Max=1000,
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS,
            Provided=False,
            Valid=False,
            ErrMessage="assume default district heating network cost ($10M)",
            ToolTipText="Total district heating network cost ($M)"
        )
        self.dhoandmcost = self.ParameterDict[self.dhoandmcost.Name] = floatParameter(
            "District Heating O&M Cost",
            DefaultValue=1,
            Min=0,
            Max=100,
            UnitType=Units.CURRENCYFREQUENCY,
            PreferredUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            CurrentUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            Provided=False, Valid=False,
            ToolTipText="Total annual district heating O&M cost ($M/year)"
        )
        self.dhpipinglength = self.ParameterDict[self.dhpipinglength.Name] = floatParameter(
            "District Heating Network Piping Length",
            DefaultValue=10.0,
            Min=0,
            Max=1000,
            UnitType=Units.LENGTH,
            PreferredUnits=LengthUnit.KILOMETERS,
            CurrentUnits=LengthUnit.KILOMETERS,
            ErrMessage="assume default district heating network piping length (10 km)",
            ToolTipText="District heating network piping length (km)"
        )
        self.dhroadlength = self.ParameterDict[self.dhroadlength.Name] = floatParameter(
            "District Heating Road Length",
            DefaultValue=10.0,
            Min=0,
            Max=1000,
            UnitType=Units.LENGTH,
            PreferredUnits=LengthUnit.KILOMETERS,
            CurrentUnits=LengthUnit.KILOMETERS,
            ErrMessage="assume default district heating road length (10 km)",
            ToolTipText="District heating road length (km)"
        )
        self.dhlandarea = self.ParameterDict[self.dhlandarea.Name] = floatParameter(
            "District Heating Land Area",
            DefaultValue=10.0,
            Min=0,
            Max=1000,
            UnitType=Units.AREA,
            PreferredUnits=AreaUnit.KILOMETERS2,
            CurrentUnits=AreaUnit.KILOMETERS2,
            ErrMessage="assume default district heating land area (10 km2)",
            ToolTipText="District heating land area (km2)"
        )
        self.dhpopulation = self.ParameterDict[self.dhpopulation.Name] = floatParameter(
            "District Heating Population",
            DefaultValue=200,
            Min=0,
            Max=1000000,
            UnitType=Units.NONE,
            ErrMessage="assume default population (200)",
            ToolTipText="Specify the population in the district heating network"
        )

        self.HeatStartPrice = self.ParameterDict[self.HeatStartPrice.Name] = floatParameter(
            "Starting Heat Sale Price",
            DefaultValue=0.025,
            Min=0,
            Max=100,
            UnitType=Units.ENERGYCOST,
            PreferredUnits=EnergyCostUnit.DOLLARSPERKWH,
            CurrentUnits=EnergyCostUnit.DOLLARSPERKWH
        )
        self.HeatEndPrice = self.ParameterDict[self.HeatEndPrice.Name] = floatParameter(
            "Ending Heat Sale Price",
            DefaultValue=0.025,
            Min=0,
            Max=100,
            UnitType=Units.ENERGYCOST,
            PreferredUnits=EnergyCostUnit.DOLLARSPERKWH,
            CurrentUnits=EnergyCostUnit.DOLLARSPERKWH
        )
        self.HeatEscalationStart = self.ParameterDict[self.HeatEscalationStart.Name] = intParameter(
            "Heat Escalation Start Year",
            DefaultValue=5,
            AllowableRange=list(range(0, 101, 1)),
            UnitType=Units.TIME,
            PreferredUnits=TimeUnit.YEAR,
            CurrentUnits=TimeUnit.YEAR,
            ErrMessage="assume default heat escalation delay time (5 years)",
            ToolTipText="Number of years after start of project before start of escalation"
        )
        self.HeatEscalationRate = self.ParameterDict[self.HeatEscalationRate.Name] = floatParameter(
            "Heat Escalation Rate Per Year",
            DefaultValue=0.0,
            Min=0.0,
            Max=100.0,
            UnitType=Units.ENERGYCOST,
            PreferredUnits=EnergyCostUnit.DOLLARSPERKWH,
            CurrentUnits=EnergyCostUnit.DOLLARSPERKWH,
            ErrMessage="assume no heat price escalation (0.0)",
            ToolTipText="additional cost per year of price after escalation starts"
        )
        self.ElecStartPrice = self.ParameterDict[self.ElecStartPrice.Name] = floatParameter(
            "Starting Electricity Sale Price",
            DefaultValue=0.055,
            Min=0,
            Max=100,
            UnitType=Units.ENERGYCOST,
            PreferredUnits=EnergyCostUnit.DOLLARSPERKWH,
            CurrentUnits=EnergyCostUnit.DOLLARSPERKWH
        )
        self.ElecEndPrice = self.ParameterDict[self.ElecEndPrice.Name] = floatParameter(
            "Ending Electricity Sale Price",
            DefaultValue=0.055,
            Min=0,
            Max=100,
            UnitType=Units.ENERGYCOST,
            PreferredUnits=EnergyCostUnit.DOLLARSPERKWH,
            CurrentUnits=EnergyCostUnit.DOLLARSPERKWH,
            ToolTipText="The maximum price to which the electricity sale price can escalate. For example, if "
                        "Starting Electricity Sale Price = 0.10 USD/kWh and Electricity Escalation Rate = "
                        "0.01 USD/kWh/yr: Electricity Price will reach 0.15 USD/kWh after 4 years of escalation. "
                        "The price will then remain at 0.15 USD/kWh for the remaining years of the project lifetime. "
                        "If the Ending Electricity Sale Price is not reached by escalation during the project "
                        "lifetime, then the value will have no effect beyond allowing escalation to occur every year."
        )
        self.ElecEscalationStart = self.ParameterDict[self.ElecEscalationStart.Name] = intParameter(
            "Electricity Escalation Start Year",
            DefaultValue=5,
            AllowableRange=list(range(0, 101, 1)),
            UnitType=Units.TIME,
            PreferredUnits=TimeUnit.YEAR,
            CurrentUnits=TimeUnit.YEAR,
            ErrMessage="assume default electricity escalation delay time (5 years)",
            ToolTipText="Number of years after start of project before start of escalation"
        )
        self.ElecEscalationRate = self.ParameterDict[self.ElecEscalationRate.Name] = floatParameter(
            "Electricity Escalation Rate Per Year",
            DefaultValue=0.0,
            Min=0.0,
            Max=100.0,
            UnitType=Units.ENERGYCOST,
            PreferredUnits=EnergyCostUnit.DOLLARSPERKWH,
            CurrentUnits=EnergyCostUnit.DOLLARSPERKWH,
            ErrMessage="assume no electricity price escalation (0.0)",
            ToolTipText="additional cost per year of price after escalation starts"
        )
        self.CoolingStartPrice = self.ParameterDict[self.CoolingStartPrice.Name] = floatParameter(
            "Starting Cooling Sale Price",
            DefaultValue=0.025,
            Min=0,
            Max=100,
            UnitType=Units.ENERGYCOST,
            PreferredUnits=EnergyCostUnit.DOLLARSPERKWH,
            CurrentUnits=EnergyCostUnit.DOLLARSPERKWH
        )
        self.CoolingEndPrice = self.ParameterDict[self.CoolingEndPrice.Name] = floatParameter(
            "Ending Cooling Sale Price",
            DefaultValue=0.025,
            Min=0,
            Max=100,
            UnitType=Units.ENERGYCOST,
            PreferredUnits=EnergyCostUnit.DOLLARSPERKWH,
            CurrentUnits=EnergyCostUnit.DOLLARSPERKWH
        )
        self.CoolingEscalationStart = self.ParameterDict[self.CoolingEscalationStart.Name] = intParameter(
            "Cooling Escalation Start Year",
            DefaultValue=5,
            AllowableRange=list(range(0, 101, 1)),
            UnitType=Units.TIME,
            PreferredUnits=TimeUnit.YEAR,
            CurrentUnits=TimeUnit.YEAR,
            ErrMessage="assume default cooling escalation delay time (5 years)",
            ToolTipText="Number of years after start of project before start of escalation"
        )
        self.CoolingEscalationRate = self.ParameterDict[self.CoolingEscalationRate.Name] = floatParameter(
            "Cooling Escalation Rate Per Year",
            DefaultValue=0.0,
            Min=0.0,
            Max=100.0,
            UnitType=Units.ENERGYCOST,
            PreferredUnits=EnergyCostUnit.DOLLARSPERKWH,
            CurrentUnits=EnergyCostUnit.DOLLARSPERKWH,
            ErrMessage="assume no cooling price escalation (0.0)",
            ToolTipText="additional cost per year of price after escalation starts"
        )
        self.CarbonStartPrice = self.ParameterDict[self.CarbonStartPrice.Name] = floatParameter(
            "Starting Carbon Credit Value",
            DefaultValue=0.0,
            Min=0,
            Max=1000,
            UnitType=Units.COSTPERMASS,
            PreferredUnits=CostPerMassUnit.DOLLARSPERLB,
            CurrentUnits=CostPerMassUnit.DOLLARSPERLB
        )
        self.CarbonEndPrice = self.ParameterDict[self.CarbonEndPrice.Name] = floatParameter(
            "Ending Carbon Credit Value",
            DefaultValue=0.0,
            Min=0,
            Max=1000,
            UnitType=Units.COSTPERMASS,
            PreferredUnits=CostPerMassUnit.DOLLARSPERLB,
            CurrentUnits=CostPerMassUnit.DOLLARSPERLB
        )
        self.CarbonEscalationStart = self.ParameterDict[self.CarbonEscalationStart.Name] = intParameter(
            "Carbon Escalation Start Year",
            DefaultValue=0,
            AllowableRange=list(range(0, 101, 1)),
            UnitType=Units.TIME,
            PreferredUnits=TimeUnit.YEAR,
            CurrentUnits=TimeUnit.YEAR,
            ErrMessage="assume default Carbon escalation delay time (5 years)",
            ToolTipText="Number of years after start of project before start of Carbon incentives"
            )
        self.CarbonEscalationRate = self.ParameterDict[self.CarbonEscalationRate.Name] = floatParameter(
            "Carbon Escalation Rate Per Year",
            DefaultValue=0.0,
            Min=0.0,
            Max=100.0,
            UnitType=Units.COSTPERMASS,
            PreferredUnits=CostPerMassUnit.DOLLARSPERLB,
            CurrentUnits=CostPerMassUnit.DOLLARSPERLB,
            ErrMessage="assume no Carbon credit escalation (0.0)",
            ToolTipText="additional value per year of price after escalation starts"
        )
        self.GridCO2Intensity = self.ParameterDict[self.GridCO2Intensity.Name] = floatParameter(
            "Current Grid CO2 production",
            DefaultValue=0.93916924,
            Min=0,
            Max=50000,
            UnitType=Units.CO2PRODUCTION,
            PreferredUnits=CO2ProductionUnit.LBSPERKWH,
            CurrentUnits=CO2ProductionUnit.LBSPERKWH,
            ErrMessage="assume the grid carbon intensity of Texas ERCOT by grid (0.93916924 lbs/kWh)",  #LBSPERKWH https://uh.edu/uh-energy-innovation/uh-energy/energy-research/white-papers/white-paper-files/net-zero-in-texas-electric-grid.pdf
            ToolTipText="CO2 intensity of the grid (how much CO2 is produced per kWh of electricity produced (0.93916924 lbs/kWh for Texas ERCOT))"
        )
        self.NaturalGasCO2Intensity = self.ParameterDict[self.NaturalGasCO2Intensity.Name] = floatParameter(
            "CO2 produced by Natural Gas",
            DefaultValue=0.070324961,
            Min=0,
            Max=50000,
            UnitType=Units.CO2PRODUCTION,
            PreferredUnits=CO2ProductionUnit.LBSPERKWH,
            CurrentUnits=CO2ProductionUnit.LBSPERKWH,
            ErrMessage="assume the default value CO2 production for burning natural gas (0.070324961 lbs/kWh)",
            ToolTipText="CO2 intensity of burning natural gas (how much CO2 is produced per kWh of heat produced "
                        "(0.070324961 lbs/kWh; https://www.epa.gov/energy/greenhouse-gases-equivalencies-calculator-calculations-and-references))"
        )

        self.AnnualLicenseEtc = self.ParameterDict[self.AnnualLicenseEtc.Name] = floatParameter(
            "Annual License Fees Etc",
            DefaultValue=0.0,
            Min=-1000.0,
            Max=1000.0,
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS
        )
        self.FlatLicenseEtc = self.ParameterDict[self.FlatLicenseEtc.Name] = floatParameter(
            "One-time Flat License Fees Etc",
            Min=-1000.0,
            Max=1000.0,
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS
        )
        self.OtherIncentives = self.ParameterDict[self.OtherIncentives.Name] = floatParameter(
            "Other Incentives",
            Min=-1000.0,
            Max=1000.0,
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS
        )
        self.TaxRelief = self.ParameterDict[self.TaxRelief.Name] = floatParameter(
            "Tax Relief Per Year",
            DefaultValue=0.0,
            Min=0.0,
            Max=100.0,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.PERCENT,
            CurrentUnits=PercentUnit.PERCENT,
            ErrMessage="assume no tax relief (0.0)",
            ToolTipText="Fixed percent reduction in annual tax rate"
        )
        self.TotalGrant = self.ParameterDict[self.TotalGrant.Name] = floatParameter(
            "One-time Grants Etc",
            Min=-1000.0,
            Max=1000.0,
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS
        )

        fir_default_unit = PercentUnit.PERCENT
        fir_default_val = self.discountrate.quantity().to(convertible_unit(fir_default_unit)).magnitude
        self.FixedInternalRate = self.ParameterDict[self.FixedInternalRate.Name] = floatParameter(
            "Fixed Internal Rate",
            DefaultValue=fir_default_val,
            Min=0.0,
            Max=100.0,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.PERCENT,
            CurrentUnits=fir_default_unit,
            ErrMessage=f'assume default for fixed internal rate ({fir_default_val}%)',
            ToolTipText="Fixed Internal Rate (used in NPV calculation). "
                        "Fixed Internal Rate is synonymous with Discount Rate. If one is provided, the other's value "
                        "will be automatically set to the same value."
        )
        self.CAPEX_heat_electricity_plant_ratio = self.ParameterDict[self.CAPEX_heat_electricity_plant_ratio.Name] = floatParameter(
            "CHP Electrical Plant Cost Allocation Ratio",
            DefaultValue=-1.0,
            Min=0.0,
            Max=1.0,
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.TENTH,
            CurrentUnits=PercentUnit.TENTH,
            Provided=False,
            ErrMessage="assume calculation for CHP Electrical Plant Cost Allocation Ratio (cost electrical plant/total CAPEX)",
            ToolTipText="CHP Electrical Plant Cost Allocation Ratio (cost electrical plant/total CAPEX)"
        )
        self.PTCElec = self.ParameterDict[self.PTCElec.Name] = floatParameter(
            "Production Tax Credit Electricity",
            DefaultValue=0.04,
            Min=0.0,
            Max=10.0,
            UnitType=Units.ENERGYCOST,
            PreferredUnits=EnergyCostUnit.DOLLARSPERKWH,
            CurrentUnits=EnergyCostUnit.DOLLARSPERKWH,
            ErrMessage="assume default for Production Tax Credit Electricity ($0.04/kWh)",
            ToolTipText="Production tax credit for electricity in $/kWh"
        )
        self.PTCHeat = self.ParameterDict[self.PTCHeat.Name] = floatParameter(
            "Production Tax Credit Heat",
            DefaultValue=0.0,
            Min=0.0,
            Max=100.0,
            UnitType=Units.ENERGYCOST,
            PreferredUnits=EnergyCostUnit.DOLLARSPERMMBTU,
            CurrentUnits=EnergyCostUnit.DOLLARSPERMMBTU,
            ErrMessage="assume default for Production Tax Credit Heat ($0.0/MMBTU)",
            ToolTipText="Production tax credit for heat in $/MMBTU"
        )
        self.PTCCooling = self.ParameterDict[self.PTCCooling.Name] = floatParameter(
            "Production Tax Credit Cooling",
            DefaultValue=0.0,
            Min=0.0,
            Max=100.0,
            UnitType=Units.ENERGYCOST,
            PreferredUnits=EnergyCostUnit.DOLLARSPERMMBTU,
            CurrentUnits=EnergyCostUnit.DOLLARSPERMMBTU,
            ErrMessage="assume default for Production Tax Credit Cooling ($0.0/MMBTU)",
            ToolTipText="Production tax credit for cooling in $/MMBTU"
        )
        self.PTCDuration = self.ParameterDict[self.PTCDuration.Name] = intParameter(
            "Production Tax Credit Duration",
            DefaultValue=10,
            AllowableRange=list(range(0, 100, 1)),
            UnitType=Units.TIME,
            PreferredUnits=TimeUnit.YEAR,
            CurrentUnits=TimeUnit.YEAR,
            ErrMessage="assume default for Production Tax Credit Duration (10 years)",
            ToolTipText="Production tax credit for duration in years"
        )
        self.PTCInflationAdjusted = self.ParameterDict[self.PTCInflationAdjusted.Name] = boolParameter(
            "Production Tax Credit Inflation Adjusted",
            DefaultValue=False,
            UnitType=Units.NONE,
            Required=False,
            ErrMessage="assume default for Production Tax Credit Inflation Adjusted (False)",
            ToolTipText="Production tax credit inflation adjusted"
        )

        self.jobs_created_per_MW_electricity = self.ParameterDict[
            self.jobs_created_per_MW_electricity.Name] = floatParameter(
            "Estimated Jobs Created per MW of Electricity Produced",
            DefaultValue=2.13,
            UnitType=Units.NONE,
            Required=False,
            ToolTipText="Estimated jobs created per MW of electricity produced, per https://geothermal.org/resources/geothermal-basics"
        )

        # local variable initialization
        self.CAPEX_cost_electricity_plant = 0.0
        self.CAPEX_cost_heat_plant = 0.0
        self.OPEX_cost_electricity_plant = 0.0
        self.OPEX_cost_heat_plant = 0.0
        self.CAPEX_heat_electricity_plant_ratio.value = 0.0
        self.Claborcorrelation = 0.0
        self.Cpumps = 0.0
        self.annualelectricityincome = 0.0
        self.annualheatincome = 0.0
        self.InputFile = ""
        self.Cplantcorrelation = 0.0

        self.sam_economics_calculations: SamEconomicsCalculations = None

        sclass = str(__class__).replace("<class \'", "")
        self.MyClass = sclass.replace("\'>", "")
        self.MyPath = os.path.abspath(__file__)

        # results
        self.ElecPrice = self.OutputParameterDict[self.ElecPrice.Name] = OutputParameter(
            "Electricity Sale Price Model",
            UnitType=Units.ENERGYCOST,
            PreferredUnits=EnergyCostUnit.CENTSSPERKWH,
            CurrentUnits=EnergyCostUnit.DOLLARSPERKWH,
        )
        self.HeatPrice = self.OutputParameterDict[self.HeatPrice.Name] = OutputParameter(
            "Heat Sale Price Model",
            UnitType=Units.ENERGYCOST,
            PreferredUnits=EnergyCostUnit.CENTSSPERKWH,
            CurrentUnits=EnergyCostUnit.DOLLARSPERKWH,
        )
        self.CoolingPrice = self.OutputParameterDict[self.CoolingPrice.Name] = OutputParameter(
            "Cooling Sale Price Model",
            UnitType=Units.ENERGYCOST,
            PreferredUnits=EnergyCostUnit.CENTSSPERKWH,
            CurrentUnits=EnergyCostUnit.DOLLARSPERKWH,
        )
        self.CarbonPrice = self.OutputParameterDict[self.CarbonPrice.Name] = OutputParameter(
            "Carbon Price Model",
            UnitType=Units.COSTPERMASS,
            PreferredUnits=CostPerMassUnit.DOLLARSPERLB,
            CurrentUnits=CostPerMassUnit.DOLLARSPERLB
        )

        self.LCOC = self.OutputParameterDict[self.LCOC.Name] = OutputParameter(
            Name="LCOC",
            display_name='Direct-Use Cooling Breakeven Price (LCOC)',
            UnitType=Units.ENERGYCOST,
            PreferredUnits=EnergyCostUnit.DOLLARSPERMMBTU,
            CurrentUnits=EnergyCostUnit.DOLLARSPERMMBTU
        )

        self.LCOE = self.OutputParameterDict[self.LCOE.Name] = OutputParameter(
            Name="LCOE",
            display_name='Electricity breakeven price',
            UnitType=Units.ENERGYCOST,
            PreferredUnits=EnergyCostUnit.CENTSSPERKWH,
            CurrentUnits=EnergyCostUnit.CENTSSPERKWH,
            ToolTipText="For SAM economic models, this is the nominal LCOE value (as opposed to real)."
        )
        self.LCOH = self.OutputParameterDict[self.LCOH.Name] = OutputParameter(
            Name="LCOH",
            display_name='Direct-Use heat breakeven price (LCOH)',
            UnitType=Units.ENERGYCOST,
            PreferredUnits=EnergyCostUnit.DOLLARSPERMMBTU,  # $/MMBTU
            CurrentUnits=EnergyCostUnit.DOLLARSPERMMBTU
        )

        stimulation_contingency_and_indirect_costs_tooltip = (
            f'plus {self.contingency_percentage.quantity().to(convertible_unit("%")).magnitude:g}% contingency '
            f'plus {self.stimulation_indirect_capital_cost_percentage.quantity().to(convertible_unit("%")).magnitude}% '
            f'indirect costs'
        )

        # noinspection SpellCheckingInspection
        self.Cstim = self.OutputParameterDict[self.Cstim.Name] = OutputParameter(
            Name="Stimulation costs",
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS,
            ToolTipText=f'Default correlation: ${self.stimulation_cost_per_injection_well.value}M '
                        f'per injection well {stimulation_contingency_and_indirect_costs_tooltip}. '
                        f'Provide {self.stimulation_cost_per_injection_well.Name} and '
                        f'{self.stimulation_cost_per_production_well.Name} to set the correlation '
                        f'costs per well. '
                        f'Provide {self.ccstimadjfactor.Name} to multiply the correlation-calculated cost. '
                        f'Provide {self.ccstimfixed.Name} to override the correlation and set your own '
                        f'total stimulation cost. '
                        f'For traditional hydrothermal reservoirs, {self.ccstimfixed.Name} should be set to $0.'
        )

        # TODO switch order to align with theoretical basis, which lists indirect costs first
        contingency_and_indirect_costs_tooltip_stem = (
            f'{self.contingency_percentage.quantity().to(convertible_unit("%")).magnitude:g}% contingency '
            f'plus {self.indirect_capital_cost_percentage.quantity().to(convertible_unit("%")).magnitude}% '
            f'indirect costs'
        )
        contingency_and_indirect_costs_tooltip = (
            f'plus {contingency_and_indirect_costs_tooltip_stem}'
        )

        self.Cexpl = self.OutputParameterDict[self.Cexpl.Name] = OutputParameter(
            Name="Exploration cost",
            display_name='Exploration costs',
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS,
            ToolTipText=f'The built-in exploration cost correlation considers drilling of a slim-hole well at 60% of '
                        f'the cost of a regular well, $1M for geophysical and field work, '
                        f'{contingency_and_indirect_costs_tooltip}. '
                        f'Provide {self.ccexpladjfactor.Name} to multiply the default correlation. '
                        f'Provide {self.ccexplfixed.Name} to override the default correlation and set your own cost.'
        )

        # noinspection SpellCheckingInspection
        self.Cwell = self.OutputParameterDict[self.Cwell.Name] = OutputParameter(
            Name="Wellfield cost",
            display_name='Drilling and completion costs',
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS,
            ToolTipText=f'Includes total drilling and completion cost of all injection and production wells and '
                        f'laterals, plus indirect costs '
                        f'(default: {self.wellfield_indirect_capital_cost_percentage.DefaultValue}%).'
        )
        self.drilling_and_completion_costs_per_well = self.OutputParameterDict[
            self.drilling_and_completion_costs_per_well.Name] = OutputParameter(
            Name='Drilling and completion costs per well',
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS,
            ToolTipText='Drilling and completion cost per well, including indirect costs '
                        f'(default: {self.wellfield_indirect_capital_cost_percentage.DefaultValue}%).'
        )

        # noinspection SpellCheckingInspection
        self.Coamwell = self.OutputParameterDict[self.Coamwell.Name] = OutputParameter(
            Name="O&M Wellfield cost",
            display_name='Wellfield maintenance costs',
            UnitType=Units.CURRENCYFREQUENCY,
            PreferredUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            CurrentUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            # TODO parameterize relevant constants in tooltip text
            ToolTipText='The built-in correlation for the wellfield O&M costs is similar as the surface plant O&M '
                        'costs: it assumes that it consists of 1% of the total wellfield plus field gathering system '
                        'costs (for annual non-labor costs) and 25% of the labor costs (the other 75% of the labor '
                        'costs are assigned to the surface plant O&M costs).'
        )

        self.redrilling_annual_cost = self.OutputParameterDict[self.redrilling_annual_cost.Name] = OutputParameter(
            Name="Redrilling costs",
            UnitType=Units.CURRENCYFREQUENCY,
            PreferredUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            CurrentUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            ToolTipText=f'Total redrilling costs over the {model.surfaceplant.plant_lifetime.Name} are calculated as '
                        f'({self.Cwell.display_name} + {self.Cstim.display_name}) '
                        f'× {model.wellbores.redrill.display_name}. '
                        f'The total is then divided over {model.surfaceplant.plant_lifetime.Name} years to calculate '
                        f'Redrilling costs per year.'
        )
        # noinspection SpellCheckingInspection
        self.Cplant = self.OutputParameterDict[self.Cplant.Name] = OutputParameter(
            Name="Surface Plant cost",
            display_name='Surface power plant costs',
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS,
            # TODO incorporate direct references to relevant parameters for adjusting correlation in tooltip text
            # TODO interpolate relevant constants (that are currently hardcoded) in tooltip text
            ToolTipText='The built-in power plant cost correlations are based on the original correlations developed '
                        'by Beckers (2016), indexed to 2017 using the IHS Markit North American Power Capital Costs '
                        'Index (NAPCCI) excluding nuclear plants (IHS 2018). The ORC power plant cost data have been '
                        'updated with data from the 2016 GETEM tool (DOE 2016) and the geothermal binary power plants '
                        'study by Verkis (2014). '
                        # Note: actual author name above is "Verkís" but the unicode accented i may cause unexpected
                        # problems in consumers.
                        'Figure 4 in the Theoretical Basis shows the power plant capital cost expressed in $ kWe-1 '
                        'as a function of plant size and initial production temperature for subcritical ORC and '
                        'double-flash power plants. '
                        f'The default correlations in GEOPHIRES include {contingency_and_indirect_costs_tooltip_stem}. '
                        'For the same plant size and production temperature, double-flash power plants are considered '
                        'about 25% more expensive than single-flash power plants (Zeyghami 2010), and supercritical '
                        'ORC plants are roughly 10% more than subcritical ORC plants (Astolfi et al. 2014). A wide '
                        'range in power plant specific cost values is reported in academic and popular literature. '
                        'The GEOPHIRES built-in surface plant cost correlations represent typical values. However, '
                        'the user is recommended to provide their own power plant cost data if available for their '
                        'case study. The ORC plant specific cost decreases only moderately at higher temperatures. '
                        'The reasons are that when increasing the temperature, the ORC plant design also changes: '
                        '(1) a different organic fluid is selected, (2) piping, pump, heat exchangers, and other '
                        'equipment are designed to handle the higher temperature (and potentially also pressure), '
                        'requiring thicker walls, potentially different materials, etc., and (3) additional components '
                        'may be implemented, such as a heat recuperator, making the design and operation more complex. '
                        'Unlike flash power plants, ORC plants are a small, niche market, typically case specific, '
                        'and rely on relatively young technology, which has not been subject yet to decades of '
                        'technological advancement. The cost for direct-use heat applications is highly dependent '
                        'on the type of application. A generic cost of $250 kWth-1 is assumed '
                        f'{contingency_and_indirect_costs_tooltip}. '
                        'However, users are encouraged to provide their own cost figures for '
                        'their specific application. Beckers and Young (2017) collected several cost figures to '
                        'estimate the surface equipment cost for geothermal district-heating systems.'
        )
        self.Coamplant = self.OutputParameterDict[self.Coamplant.Name] = OutputParameter(
            Name="O&M Surface Plant costs",
            display_name='Power plant maintenance costs',
            UnitType=Units.CURRENCYFREQUENCY,
            PreferredUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            CurrentUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            # TODO parameterize relevant constants in tooltip text
            # TODO update index year and/or make indexing parameterizable in tooltip text
            ToolTipText='GEOPHIRES estimates the annual surface plant O&M costs as the sum of 1.5% of the total plant '
                        'capital cost (for annual non-labor costs), and 75% of the annual labor costs. The other 25% '
                        'of the labor costs are assigned to the wellfield O&M cost. The labor costs are calculated '
                        'internally in GEOPHIRES using the 2014 labor costs provided by Beckers (2016), indexed to '
                        '2017 using the Bureau of Labor Statistics (BLS) Employment Cost Index for utilities (2018). '
                        'The original 2014 labor cost correlation expresses the labor costs as a function of the plant '
                        'size (MW) using an approximate logarithmic curve fit to the built-in labor cost data in '
                        'GETEM.'
        )
        # noinspection SpellCheckingInspection
        self.Cgath = self.OutputParameterDict[self.Cgath.Name] = OutputParameter(
            Name="Field gathering system cost",
            display_name='Field gathering system costs',
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS,
            # TODO interpolate constant values in tooltip text instead of hardcoding in tooltip text
            ToolTipText='The built-in cost correlation for estimating the field gathering system cost includes '
                        'the cost for surface piping from each well to the plant and pumps for production and '
                        'injection wells. The length of the surface piping is assumed 750 m per well at a cost of '
                        '$500 per meter. The pumping cost for each pump in the production wells (line-shaft pumps) '
                        'and a single pump for the injection wells is calculated with the same correlation as GETEM. '
                        f'Contingency (default: '
                        f'{self.contingency_percentage.quantity().to(convertible_unit("%")).magnitude:g}%). '
                        f'and indirect costs (default: '
                        f'{self.indirect_capital_cost_percentage.quantity().to(convertible_unit("%")).magnitude}%) '
                        f'are added. '
                        'The built-in cost correlation does not include the cost of pipelines to an off-site heat '
                        'user or a district-heating system. These costs are estimated at $750 per meter pipeline '
                        'length and can be manually added by the user to the pipeline distribution costs.'
        )
        self.Cpiping = self.OutputParameterDict[self.Cpiping.Name] = OutputParameter(
            Name="Transmission pipeline costs",
            display_name='Transmission pipeline cost',
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS
        )
        self.Coamwater = self.OutputParameterDict[self.Coamwater.Name] = OutputParameter(
            Name="O&M Make-up Water costs",
            display_name='Water costs',
            UnitType=Units.CURRENCYFREQUENCY,
            PreferredUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            CurrentUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            ToolTipText=f'Default correlation: Assumes $3.50/1,000 gallons of water. '
                        f'Provide {self.oamwateradjfactor.Name} to multiply the default correlation.'
            # Note: $3.50 could possibly be parameterized, but adjustment factor param serves the same purpose for now.
        )
        self.CCap = self.OutputParameterDict[self.CCap.Name] = OutputParameter(
            Name="Total Capital Cost",
            display_name='Total capital costs',
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS,
        )
        self.capex_total = self.OutputParameterDict[self.capex_total.Name] = total_capex_parameter_output_parameter()

        # noinspection SpellCheckingInspection
        self.Coam = self.OutputParameterDict[self.Coam.Name] = OutputParameter(
            Name="Total O&M Cost",
            display_name='Total operating and maintenance costs',
            UnitType=Units.CURRENCYFREQUENCY,
            PreferredUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            CurrentUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            ToolTipText=f'GEOPHIRES estimates the annual O&M costs as the sum of the annual surface plant, wellfield, '
                        f'make-up water, and pumping O&M costs.'
        )
        self.averageannualpumpingcosts = OutputParameter(
            Name="Average Annual Pumping Costs",
            UnitType=Units.CURRENCYFREQUENCY,
            PreferredUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            CurrentUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR
        )
        # heat pump
        self.averageannualheatpumpelectricitycost = self.OutputParameterDict[
            self.averageannualheatpumpelectricitycost.Name] = OutputParameter(
            Name="Average Annual Heat Pump Electricity Cost",
            UnitType=Units.CURRENCYFREQUENCY,
            PreferredUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            CurrentUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR
        )
        self.royalties_average_annual_cost = self.OutputParameterDict[self.royalties_average_annual_cost.Name] = OutputParameter(
            Name='Average Annual Royalty Cost',
            UnitType=Units.CURRENCYFREQUENCY,
            PreferredUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            CurrentUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            ToolTipText='The average annual cost paid to a royalty holder, calculated as a percentage of the '
                        'project\'s gross annual revenue. This is modeled as a variable operating expense.'
        )


        # district heating
        self.peakingboilercost = self.OutputParameterDict[self.peakingboilercost.Name] = OutputParameter(
            Name="Peaking boiler cost",
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS,
            ToolTipText=f'Default cost: ${self._default_peaking_boiler_cost_USD_per_kW}/KW '
                        f'of maximum peaking boiler demand. '
                        f'Provide {self.peaking_boiler_cost_per_kW.Name} override the default.'
        )

        self.dhdistrictcost = self.OutputParameterDict[self.dhdistrictcost.Name] = OutputParameter(
            Name="District Heating System Cost",
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS
        )
        self.populationdensity = self.OutputParameterDict[self.populationdensity.Name] = OutputParameter(
            Name="District Heating System Population Density",
            UnitType=Units.POPDENSITY,
            PreferredUnits=PopDensityUnit.perkm2,
            CurrentUnits=PopDensityUnit.perkm2
        )
        self.annualngcost = self.OutputParameterDict[self.annualngcost.Name] = OutputParameter(
            Name="Annual Peaking Fuel Cost",
            UnitType=Units.CURRENCYFREQUENCY,
            PreferredUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            CurrentUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR
        )
        self.dhdistrictoandmcost = self.OutputParameterDict[self.dhdistrictoandmcost.Name] = OutputParameter(
            Name="Annual District Heating O&M Cost",
            UnitType=Units.CURRENCYFREQUENCY,
            PreferredUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            CurrentUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR
        )
        self.averageannualngcost = self.OutputParameterDict[self.averageannualngcost.Name] = OutputParameter(
            Name="Average Annual Peaking Fuel Cost",
            UnitType=Units.CURRENCYFREQUENCY,
            PreferredUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            CurrentUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR
        )

        self.ElecRevenue = self.OutputParameterDict[self.ElecRevenue.Name] = OutputParameter(
            Name="Annual Revenue from Electricity Production",
            UnitType=Units.CURRENCYFREQUENCY,
            PreferredUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            CurrentUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR
        )
        self.ElecCummRevenue = self.OutputParameterDict[self.ElecCummRevenue.Name] = OutputParameter(
            Name="Cumulative Revenue from Electricity Production",
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS
        )
        self.HeatRevenue = self.OutputParameterDict[self.HeatRevenue.Name] = OutputParameter(
            Name="Annual Revenue from Heat Production",
            UnitType=Units.CURRENCYFREQUENCY,
            PreferredUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            CurrentUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR
        )
        self.HeatCummRevenue = self.OutputParameterDict[self.HeatCummRevenue.Name] = OutputParameter(
            Name="Cumulative Revenue from Heat Production",
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS
        )
        self.CoolingRevenue = self.OutputParameterDict[self.CoolingRevenue.Name] = OutputParameter(
            Name="Annual Revenue from Cooling Production",
            UnitType=Units.CURRENCYFREQUENCY,
            PreferredUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            CurrentUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR
        )
        self.CoolingCummRevenue = self.OutputParameterDict[self.CoolingCummRevenue.Name] = OutputParameter(
            Name="Cumulative Revenue from Cooling Production",
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS
        )
        self.CarbonRevenue = self.OutputParameterDict[self.CarbonRevenue.Name] = OutputParameter(
            Name="Annual Revenue from Carbon Pricing",
            UnitType=Units.CURRENCYFREQUENCY,
            PreferredUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            CurrentUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR
        )
        self.CarbonCummCashFlow = self.OutputParameterDict[self.CarbonCummCashFlow.Name] = OutputParameter(
            Name="Cumulative Revenue from Carbon Pricing",
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS
        )
        self.CarbonThatWouldHaveBeenProducedAnnually = self.OutputParameterDict[
            self.CarbonThatWouldHaveBeenProducedAnnually.Name] = OutputParameter(
            "Annual Saved Carbon Production",
            UnitType=Units.MASS,
            PreferredUnits=MassUnit.LB,
            CurrentUnits=MassUnit.LB
        )
        self.CarbonThatWouldHaveBeenProducedTotal = self.OutputParameterDict[
            self.CarbonThatWouldHaveBeenProducedTotal.Name] = OutputParameter(
            "Total Saved Carbon Production",
            display_name='Total Avoided Carbon Emissions',
            UnitType=Units.MASS,
            PreferredUnits=MassUnit.LB,
            CurrentUnits=MassUnit.LB
        )
        self.interest_rate = self.OutputParameterDict[self.interest_rate.Name] = OutputParameter(
            Name='Interest Rate',
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.PERCENT,
            CurrentUnits=PercentUnit.PERCENT
        )

        self.overnight_capital_cost = self.OutputParameterDict[
            self.overnight_capital_cost.Name] = overnight_capital_cost_output_parameter()

        self.accrued_financing_during_construction_percentage = self.OutputParameterDict[
          self.accrued_financing_during_construction_percentage.Name] = OutputParameter(
            Name='Accrued financing during construction',
            UnitType=Units.PERCENT,
            PreferredUnits=PercentUnit.PERCENT,
            CurrentUnits=PercentUnit.PERCENT,
            ToolTipText='The accrued inflation on total capital costs over the construction period, '
                        f'as defined by {self.inflrateconstruction.Name}.'
        )

        self.inflation_cost_during_construction = self.OutputParameterDict[
            self.inflation_cost_during_construction.Name] = inflation_cost_during_construction_output_parameter()

        self.interest_during_construction = self.OutputParameterDict[
            self.interest_during_construction.Name] = interest_during_construction_output_parameter()

        self.after_tax_irr = self.OutputParameterDict[self.after_tax_irr.Name] = (
            after_tax_irr_parameter())
        self.real_discount_rate = self.OutputParameterDict[self.real_discount_rate.Name] = (
            real_discount_rate_parameter())
        self.nominal_discount_rate = self.OutputParameterDict[self.nominal_discount_rate.Name] = (
            nominal_discount_rate_parameter())
        self.wacc = self.OutputParameterDict[self.wacc.Name] = wacc_output_parameter()

        # TODO this is displayed as "Project Net Revenue" in Revenue & Cashflow Profile which is probably not an
        #   accurate synonym for annual revenue
        self.TotalRevenue = self.OutputParameterDict[self.TotalRevenue.Name] = OutputParameter(
            Name="Annual Revenue from Project",
            UnitType=Units.CURRENCYFREQUENCY,
            PreferredUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            CurrentUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR
        )

        # TODO this is displayed as "Project Net Cashflow" in Revenue & Cashflow Profile which is probably not an
        #   accurate synonym for cumulative revenue
        self.TotalCummRevenue = self.OutputParameterDict[self.TotalCummRevenue.Name] = OutputParameter(
            Name="Cumulative Revenue from Project",
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS
        )

        self.ProjectNPV = self.OutputParameterDict[self.ProjectNPV.Name] = OutputParameter(
            "Project Net Present Value",
            display_name='Project NPV',
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS,
            ToolTipText='NPV is calculated with cashflows lumped at the end of periods. '
                        'See: Short W et al, 1995. '
                        '"A Manual for the Economic Evaluation of Energy Efficiency and Renewable Energy '
                        'Technologies.", p. 41. '
                        'https://www.nrel.gov/docs/legosti/old/5173.pdf'
        )
        self.ProjectIRR = self.OutputParameterDict[self.ProjectIRR.Name] = OutputParameter(
            "Project Internal Rate of Return",
            display_name='Project IRR',
            UnitType=Units.PERCENT,
            CurrentUnits=PercentUnit.PERCENT,
            PreferredUnits=PercentUnit.PERCENT,
        )
        self.ProjectVIR = self.OutputParameterDict[self.ProjectVIR.Name] = project_vir_parameter()
        self.ProjectMOIC = self.OutputParameterDict[self.ProjectMOIC.Name] = moic_parameter()
        self.ProjectPaybackPeriod = self.OutputParameterDict[self.ProjectPaybackPeriod.Name] = (
            project_payback_period_parameter())
        self.RITCValue = self.OutputParameterDict[self.RITCValue.Name] = investment_tax_credit_output_parameter()
        self.cost_one_production_well = self.OutputParameterDict[self.cost_one_production_well.Name] = OutputParameter(
            Name="Cost of One Production Well",
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS
        )
        self.cost_one_injection_well = self.OutputParameterDict[self.cost_one_injection_well.Name] = OutputParameter(
            Name="Cost of One Injection Well",
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS
        )
        self.cost_lateral_section = self.OutputParameterDict[self.cost_lateral_section.Name] = OutputParameter(
            Name="Cost of the entire (multi-) lateral section of a well",
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS
        )
        self.cost_per_lateral_section = self.OutputParameterDict[self.cost_per_lateral_section.Name] = OutputParameter(
            Name='Drilling and completion costs per non-vertical section',
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS
        )
        self.cost_to_junction_section = self.OutputParameterDict[self.cost_to_junction_section.Name] = OutputParameter(
            Name="Cost of the entire section of a well from bottom of vertical to junction with laterals",
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS
        )
        self.jobs_created = self.OutputParameterDict[self.jobs_created.Name] = OutputParameter(
            Name="Estimated Jobs Created",
            UnitType=Units.NONE,
        )

        # Results for the Royalty Holder
        self.royalty_holder_npv = self.OutputParameterDict[self.royalty_holder_npv.Name] = OutputParameter(
            'Royalty Holder NPV',
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS,
            ToolTipText=f"The pre-tax Net Present Value (NPV) of the royalty holder's income stream, "
                        f"calculated using the {self.royalty_holder_discount_rate.Name}. "
                        f"This is a pre-tax value because the model does not account for the royalty holder's specific "
                        f"tax liabilities."
        )
        self.royalty_holder_annual_revenue = self.OutputParameterDict[
            self.royalty_holder_annual_revenue.Name
        ] = OutputParameter(
            'Royalty Holder Average Annual Revenue',
            UnitType=Units.CURRENCYFREQUENCY,
            PreferredUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            CurrentUnits=CurrencyFrequencyUnit.MDOLLARSPERYEAR,
            ToolTipText="The royalty holder's gross (pre-tax) annual revenue stream from the royalty agreement."
        )
        self.royalty_holder_total_revenue = self.OutputParameterDict[
            self.royalty_holder_total_revenue.Name
        ] = OutputParameter(
            'Royalty Holder Total Revenue',
            UnitType=Units.CURRENCY,
            PreferredUnits=CurrencyUnit.MDOLLARS,
            CurrentUnits=CurrencyUnit.MDOLLARS,
            ToolTipText='The total gross (pre-tax), undiscounted revenue received by the royalty holder over the '
                        'project lifetime.'
        )

        model.logger.info(f'Complete {__class__!s}: {sys._getframe().f_code.co_name}')

    def read_parameters(self, model: Model) -> None:
        """
        read_parameters read and update the Economics parameters and handle the special cases
        Deal with all the parameter values that the user has provided.  They should really only provide values
        that they want to change from the default values, but they can provide a value that is already set
        because it is a default value set in __init__.  It will ignore those.
        This also deals with all the special cases that need to be taken care of after a
        value has been read in and checked.
        If you choose to subclass this master class, you can also choose to override this method (or not),
        and if you do, do it before or after you call you own version of this method.  If you do, you can also
        choose to call this method from you class, which can effectively modify all these superclass parameters
        in your class.
        :param model: The container class of the application, giving access to everything else, including the logger
        :type model: :class:`~geophires_x.Model.Model`
        :return: None
        """
        model.logger.info(f'Init {__class__!s}: {sys._getframe().f_code.co_name}')

        def _warn(_msg: str) -> None:
            print(f'Warning: {_msg}')
            model.logger.warning(_msg)

        if len(model.InputParameters) > 0:
            # loop through all the parameters that the user wishes to set, looking for parameters that match this object
            for item in self.ParameterDict.items():
                ParameterToModify = item[1]
                key = ParameterToModify.Name.strip()
                if key in model.InputParameters:
                    ParameterReadIn = model.InputParameters[key]

                    # this should handle all the non-special cases
                    ReadParameter(ParameterReadIn, ParameterToModify, model)

                    # handle special cases
                    if ParameterToModify.Name == "Economic Model":
                        self.econmodel.value = EconomicModel.from_input_string(ParameterReadIn.sValue)

                    elif ParameterToModify.Name == "Well Drilling Cost Correlation":
                        ParameterToModify.value = WellDrillingCostCorrelation.from_input_string(ParameterReadIn.sValue)

                    elif ParameterToModify.Name == "Reservoir Stimulation Capital Cost Adjustment Factor":
                        if self.ccstimfixed.Valid and ParameterToModify.Valid:
                            _warn("Provided reservoir stimulation cost adjustment factor not considered" +
                                  " because valid total reservoir stimulation cost provided.")
                        elif not self.ccstimfixed.Provided and not ParameterToModify.Provided:
                            ParameterToModify.value = 1.0
                            _warn("No valid reservoir stimulation total cost or adjustment factor" +
                                                 " provided. GEOPHIRES will assume default built-in reservoir stimulation cost correlation" +
                                                 " with adjustment factor = 1.")
                        elif self.ccstimfixed.Provided and not self.ccstimfixed.Valid:
                            _warn(
                                "Provided reservoir stimulation cost outside of range 0-100. GEOPHIRES" +
                                " will assume default built-in reservoir stimulation cost correlation with" +
                                " adjustment factor = 1.")
                            ParameterToModify.value = 1.0
                        elif not self.ccstimfixed.Provided and ParameterToModify.Provided and not ParameterToModify.Valid:
                            _warn("Provided reservoir stimulation cost adjustment factor outside of" +
                                                 " range 0-10. GEOPHIRES will assume default reservoir stimulation cost correlation with" +
                                                 " adjustment factor = 1.")
                            ParameterToModify.value = 1.0
                    elif ParameterToModify.Name == "Exploration Capital Cost Adjustment Factor":
                        if self.totalcapcost.Valid:
                            if self.ccexplfixed.Provided:
                                _warn("Warning: Provided exploration cost not considered" +
                                                     " because valid total capital cost provided.")
                            if ParameterToModify.Provided:
                                _warn("Warning: Provided exploration cost not considered because valid" +
                                                     " total capital cost provided.")
                        else:
                            if self.ccexplfixed.Valid and ParameterToModify.Valid:
                                _warn("Provided exploration cost adjustment factor not" +
                                                     " considered because valid total exploration cost provided.")
                            elif not self.ccexplfixed.Provided and not ParameterToModify.Provided:
                                ParameterToModify.value = 1.0
                                _warn("No valid exploration total cost or adjustment factor provided." +
                                                     " GEOPHIRES will assume default built-in exploration cost correlation with" +
                                                     " adjustment factor = 1.")
                            elif self.ccexplfixed.Provided and not self.ccexplfixed.Valid:
                                _warn("Provided exploration cost outside of range 0-100. GEOPHIRES" +
                                                     " will assume default built-in exploration cost correlation with adjustment factor = 1.")
                                ParameterToModify.value = 1.0
                            elif not self.ccexplfixed.Provided and ParameterToModify.Provided and not ParameterToModify.Valid:
                                _warn("Provided exploration cost adjustment factor outside of" +
                                                     " range 0-10. GEOPHIRES will assume default exploration cost correlation with" +
                                                     " adjustment factor = 1.")
                                ParameterToModify.value = 1.0
                    elif ParameterToModify.Name == "Well Drilling and Completion Capital Cost Adjustment Factor":
                        if self.per_production_well_cost.Valid and ParameterToModify.Valid:
                            _warn('Provided well drilling and completion cost adjustment factor not considered '
                                   'because valid total well drilling and completion cost provided.')
                        elif not self.per_production_well_cost.Provided and not self.production_well_cost_adjustment_factor.Provided:
                            ParameterToModify.value = 1.0
                            _warn("No valid well drilling and completion total cost or adjustment factor provided. "
                                   "GEOPHIRES will assume default built-in well drilling and completion cost "
                                   "correlation with adjustment factor = 1.")
                        elif self.per_production_well_cost.Provided and not self.per_production_well_cost.Valid:
                            _warn("Provided well drilling and completion cost outside of range 0-1000. GEOPHIRES "
                                   "will assume default built-in well drilling and completion cost correlation "
                                   "with adjustment factor = 1.")
                            self.production_well_cost_adjustment_factor.value = 1.0
                        elif not self.per_production_well_cost.Provided and self.production_well_cost_adjustment_factor.Provided and not self.production_well_cost_adjustment_factor.Valid:
                            _warn("Provided well drilling and completion cost adjustment factor outside of range "
                                   "0-10. GEOPHIRES will assume default built-in well drilling and completion cost "
                                   "correlation with adjustment factor = 1.")
                            self.production_well_cost_adjustment_factor.value = 1.0
                    elif ParameterToModify.Name == "Wellfield O&M Cost Adjustment Factor":
                        if self.oamtotalfixed.Valid:
                            if self.oamwellfixed.Provided:
                                _warn("Provided total wellfield O&M cost not considered because" +
                                                     " valid total annual O&M cost provided.")
                            if ParameterToModify.Provided:
                                _warn("Provided wellfield O&M cost adjustment factor not considered" +
                                                     " because valid total annual O&M cost provided.")
                        else:
                            if self.oamwellfixed.Valid and ParameterToModify.Valid:
                                _warn("Provided wellfield O&M cost adjustment factor not considered" +
                                                     " because valid total wellfield O&M cost provided.")
                            elif not self.oamwellfixed.Provided and not ParameterToModify.Provided:
                                ParameterToModify.value = 1.0
                                _warn("No valid total wellfield O&M cost or adjustment factor" +
                                                     " provided. GEOPHIRES will assume default built-in wellfield O&M cost correlation" +
                                                     " with adjustment factor = 1.")
                            elif self.oamwellfixed.Provided and not self.oamwellfixed.Valid:
                                _warn("Provided total wellfield O&M cost outside of range 0-100." +
                                                     " GEOPHIRES will assume default built-in wellfield O&M cost correlation with" +
                                                     " adjustment factor = 1.")
                                ParameterToModify.value = 1.0
                            elif not self.oamwellfixed.Provided and self.oamwelladjfactor.Provided and not self.oamwelladjfactor.Valid:
                                _warn("Provided wellfield O&M cost adjustment factor outside of" +
                                                     " range 0-10. GEOPHIRES will assume default wellfield O&M cost correlation with" +
                                                     " adjustment factor = 1.")
                                ParameterToModify.value = 1.0
                    elif ParameterToModify.Name == "Surface Plant Capital Cost Adjustment Factor":
                        if self.totalcapcost.Valid:
                            if self.ccplantfixed.Provided:
                                _warn("Provided surface plant cost not considered because valid" +
                                                     " total capital cost provided.")
                            if ParameterToModify.Provided:
                                _warn("Provided surface plant cost adjustment factor not considered" +
                                                     " because valid total capital cost provided.")
                        else:
                            if self.ccplantfixed.Valid and ParameterToModify.Valid:
                                _warn("Provided surface plant cost adjustment factor not considered" +
                                                     " because valid total surface plant cost provided.")
                            elif not self.ccplantfixed.Provided and not ParameterToModify.Provided:
                                ParameterToModify.value = 1.0
                                _warn("No valid surface plant total cost or adjustment factor" +
                                                     " provided. GEOPHIRES will assume default built-in surface plant cost correlation" +
                                                     " with adjustment factor = 1.")
                            elif self.ccplantfixed.Provided and not self.ccplantfixed.Valid:
                                _warn("Provided surface plant cost outside of range 0-1000." +
                                                     " GEOPHIRES will assume default built-in surface plant cost correlation with" +
                                                     " adjustment factor = 1.")
                                ParameterToModify.value = 1.0
                            elif not self.ccplantfixed.Provided and self.ccplantadjfactor.Provided and not self.ccplantadjfactor.Valid:
                                _warn("Provided surface plant cost adjustment factor outside of" +
                                                     " range 0-10. GEOPHIRES will assume default surface plant cost correlation with" +
                                                     " adjustment factor = 1.")
                                ParameterToModify.value = 1.0
                    elif ParameterToModify.Name == "Field Gathering System Capital Cost Adjustment Factor":
                        if self.totalcapcost.Valid:
                            if self.ccgathfixed.Provided:
                                _warn(
                                    "Provided field gathering system cost not considered because valid" +
                                    " total capital cost provided.")
                            if ParameterToModify.Provided:
                                _warn("Provided field gathering system cost adjustment factor not" +
                                                     " considered because valid total capital cost provided.")
                        else:
                            if self.ccgathfixed.Valid and ParameterToModify.Valid:
                                _warn("Provided field gathering system cost adjustment factor not" +
                                                     " considered because valid total field gathering system cost provided.")
                            elif not self.ccgathfixed.Provided and not ParameterToModify.Provided:
                                ParameterToModify.value = 1.0
                                _warn("No valid field gathering system total cost or adjustment factor" +
                                                     " provided. GEOPHIRES will assume default built-in field gathering system cost" +
                                                     " correlation with adjustment factor = 1.")
                            elif self.ccgathfixed.Provided and not self.ccgathfixed.Valid:
                                _warn("Provided field gathering system cost outside of range 0-100." +
                                                     " GEOPHIRES will assume default built-in field gathering system cost correlation with" +
                                                     " adjustment factor = 1.")
                                ParameterToModify.value = 1.0
                            elif not self.ccgathfixed.Provided and ParameterToModify.Provided and not ParameterToModify.Valid:
                                _warn("Provided field gathering system cost adjustment factor" +
                                                     " outside of range 0-10. GEOPHIRES will assume default field gathering system cost" +
                                                     " correlation with adjustment factor = 1.")
                                ParameterToModify.value = 1.0
                    elif ParameterToModify.Name == "Water Cost Adjustment Factor":
                        if self.oamtotalfixed.Valid:
                            if self.oamwaterfixed.Provided:
                                _warn("Provided total water cost not considered because valid" +
                                                     " total annual O&M cost provided.")
                            if ParameterToModify.Provided:
                                _warn("Provided water cost adjustment factor not considered because" +
                                                     " valid total annual O&M cost provided.")
                        else:
                            if self.oamwaterfixed.Valid and ParameterToModify.Valid:
                                _warn("Provided water cost adjustment factor not considered because" +
                                                     " valid total water cost provided.")
                            elif not self.oamwaterfixed.Provided and not ParameterToModify.Provided:
                                ParameterToModify.value = 1.0
                                _warn("No valid total water cost or adjustment factor provided." +
                                                     " GEOPHIRES will assume default built-in water cost correlation with" +
                                                     " adjustment factor = 1.")
                            elif self.oamwaterfixed.Provided and not self.oamwaterfixed.Valid:
                                _warn("Provided total water cost outside of range 0-100. GEOPHIRES" +
                                                     " will assume default built-in water cost correlation with adjustment factor = 1.")
                                ParameterToModify.value = 1.0
                            elif not self.oamwaterfixed.Provided and ParameterToModify.Provided and not ParameterToModify.Valid:
                                _warn("Provided water cost adjustment factor outside of range 0-10." +
                                                     " GEOPHIRES will assume default water cost correlation with adjustment factor = 1.")
                                ParameterToModify.value = 1.0
                    elif ParameterToModify.Name == "Surface Plant O&M Cost Adjustment Factor":
                        if self.oamtotalfixed.Valid:
                            if self.oamplantfixed.Provided:
                                _warn("Provided total surface plant O&M cost not considered because" +
                                                     " valid total annual O&M cost provided.")
                            if ParameterToModify.Provided:
                                _warn(
                                    "Provided surface plant O&M cost adjustment factor not considered" +
                                    " because valid total annual O&M cost provided.")
                        else:
                            if self.oamplantfixed.Valid and ParameterToModify.Valid:
                                _warn(
                                    "Provided surface plant O&M cost adjustment factor not considered" +
                                    " because valid total surface plant O&M cost provided.")
                            elif not self.oamplantfixed.Provided and not ParameterToModify.Provided:
                                ParameterToModify.value = 1.0
                                _warn("No valid surface plant O&M cost or adjustment factor provided." +
                                                     " GEOPHIRES will assume default built-in surface plant O&M cost correlation with" +
                                                     " adjustment factor = 1.")
                            elif self.oamplantfixed.Provided and not self.oamplantfixed.Valid:
                                _warn("Provided surface plant O&M cost outside of range 0-100." +
                                                     " GEOPHIRES will assume default built-in surface plant O&M cost correlation with" +
                                                     " adjustment factor = 1.")
                                ParameterToModify.value = 1.0
                            elif not self.oamplantfixed.Provided and ParameterToModify.Provided and not ParameterToModify.Valid:
                                _warn("Provided surface plant O&M cost adjustment factor outside of" +
                                                     " range 0-10. GEOPHIRES will assume default surface plant O&M cost correlation with" +
                                                     " adjustment factor = 1.")
                                ParameterToModify.value = 1.0

            if self.HeatStartPrice.value > self.HeatEndPrice.value:
                s = f'{self.HeatStartPrice.Name} ({self.HeatStartPrice.quantity()}) cannot be ' \
                    f'greater than {self.HeatEndPrice.Name} ({self.HeatEndPrice.quantity()}).  ' \
                    f'GEOPHIRES will assume {self.HeatStartPrice.Name} is equal to {self.HeatEndPrice.Name}.'
                model.logger.warning(s)

            if self.econmodel.value == EconomicModel.SAM_SINGLE_OWNER_PPA:
                EconomicsSam.validate_read_parameters(model)
            else:
                sam_em_only_params: list[Parameter] = [
                    self.royalty_rate,
                    # TODO other royalty params
                    self.construction_capex_schedule,
                    self.bond_financing_start_year
                ]
                for sam_em_only_param in sam_em_only_params:
                    if sam_em_only_param.Provided:
                        raise NotImplementedError(f'{sam_em_only_param.Name} is only supported for SAM Economic Models')

        else:
            model.logger.info("No parameters read because no content provided")

        # we can determine on-the-fly if Addons, CCUS, or S-DAC-GT are being used in the user input file
        for key in model.InputParameters.keys():
            if key.startswith("AddOn") and not self.DoAddOnCalculations.Provided:
                self.DoAddOnCalculations.value = True
                break

        for key in model.InputParameters.keys():
            if key.startswith("S-DAC-GT"):
                self.DoSDACGTCalculations.value = True
                break

        coerce_int_params_to_enum_values(self.ParameterDict)
        self.sync_interest_rate(model)
        self.sync_well_drilling_and_completion_capital_cost_adjustment_factor(model)

        # SAM Economic Models recalculate accrued financing value based on construction years and inflation rate if
        # inflation rate during construction is not provided.
        # TODO to determine whether the same logic should be applied for other economic models.
        self.accrued_financing_during_construction_percentage.value = self.inflrateconstruction.quantity().to(
            convertible_unit(self.accrued_financing_during_construction_percentage.CurrentUnits)
        ).magnitude

        model.logger.info(f'complete {__class__!s}: {sys._getframe().f_code.co_name}')

    def sync_interest_rate(self, model):
        def discount_rate_display() -> str:
            return str(self.discountrate.quantity()).replace(' dimensionless', '')

        if self.discountrate.Provided ^ self.FixedInternalRate.Provided:
            if self.discountrate.Provided:
                self.FixedInternalRate.value = self.discountrate.quantity().to(
                    convertible_unit(self.FixedInternalRate.CurrentUnits)).magnitude
                model.logger.info(f'Set {self.FixedInternalRate.Name} to {self.FixedInternalRate.quantity()} '
                                  f'because {self.discountrate.Name} was provided ({discount_rate_display()})')
            else:
                self.discountrate.value = self.FixedInternalRate.quantity().to(
                    convertible_unit(self.discountrate.CurrentUnits)).magnitude
                model.logger.info(
                    f'Set {self.discountrate.Name} to {discount_rate_display()} because '
                    f'{self.FixedInternalRate.Name} was provided ({self.FixedInternalRate.quantity()})')

        if self.discountrate.Provided and self.FixedInternalRate.Provided \
            and self.discountrate.quantity().to(convertible_unit(self.FixedInternalRate.CurrentUnits)).magnitude \
                != self.FixedInternalRate.value:
            model.logger.warning(f'{self.discountrate.Name} and {self.FixedInternalRate.Name} provided with different '
                                 f'values ({discount_rate_display()}; {self.FixedInternalRate.quantity()}). '
                                 f'It is recommended to only provide one of these values.')

        self.interest_rate.value = self.discountrate.quantity().to(convertible_unit(self.interest_rate.CurrentUnits)).magnitude

    def sync_well_drilling_and_completion_capital_cost_adjustment_factor(self, model):
        if (self.production_well_cost_adjustment_factor.Provided
                and not self.injection_well_cost_adjustment_factor.Provided):
            factor = self.production_well_cost_adjustment_factor.value
            self.injection_well_cost_adjustment_factor.value = factor
            model.logger.info(
                f'Set {self.injection_well_cost_adjustment_factor.Name} to {factor} because '
                f'{self.production_well_cost_adjustment_factor.Name} was provided.')


    def Calculate(self, model: Model) -> None:
        """
        The Calculate function is where all the calculations are done.
        This function can be called multiple times, and will only recalculate what has changed each time it is called.
        This is where all the calculations are made using all the values that have been set.
        If you subclass this class, you can choose to run these calculations before (or after) your calculations,
        but that assumes you have set all the values that are required for these calculations
        If you choose to subclass this master class, you can also choose to override this method (or not),
        and if you do, do it before or after you call you own version of this method.  If you do,
        you can also choose to call this method from you class, which can effectively run the calculations
        of the superclass, making all thr values available to your methods. but you had
        better have set all the parameters!
        :param model: The container class of the application, giving access to everything else, including the logger
        :type model: :class:`~geophires_x.Model.Model`
        :return: Nothing, but it does make calculations and set values in the model
        """
        model.logger.info(f'Init {__class__!s}: {sys._getframe().f_code.co_name}')

        # capital costs
        self.calculate_wellfield_costs(model)
        self.Cstim.value = self.calculate_stimulation_costs(model).to(self.Cstim.CurrentUnits).magnitude
        self.calculate_field_gathering_costs(model)
        self.calculate_plant_costs(model)
        self.calculate_total_capital_costs(model)
        self.calculate_operating_and_maintenance_costs(model)

        # The Reservoir depth measure was arbitrarily changed to meters despite being defined in the docs as kilometers.
        # For display consistency sake, we need to convert it back
        if model.reserv.depth.value > 500:
            model.reserv.depth.value = model.reserv.depth.value / 1000.0
            model.reserv.depth.CurrentUnits = LengthUnit.KILOMETERS

        self.build_price_models(model)

        # do the additional economic calculations first, if needed, so the summaries below work.
        if self.DoAddOnCalculations.value:
            model.addeconomics.Calculate(model)

        if self.DoSDACGTCalculations.value:
            model.sdacgteconomics.Calculate(model)

        self.calculate_cashflow(model)

        # Calculate more financial values using numpy financials
        self.ProjectNPV.value, self.ProjectIRR.value, self.ProjectVIR.value, self.ProjectMOIC.value = \
            CalculateFinancialPerformance(
                model.surfaceplant.plant_lifetime.value,
                self.FixedInternalRate.value,
                self.TotalRevenue.value,
                self.TotalCummRevenue.value,
                self.CCap.value,
                self.Coam.value,
                self.discount_initial_year_cashflow.value
            )

        if self.econmodel.value == EconomicModel.SAM_SINGLE_OWNER_PPA:
            self._calculate_sam_economics(model)

        # Calculate the project payback period
        if self.econmodel.value != EconomicModel.SAM_SINGLE_OWNER_PPA:
            self.ProjectPaybackPeriod.value = 0.0  # start by assuming the project never pays back
            for i in range(0, len(self.TotalCummRevenue.value), 1):
                # find out when the cumm cashflow goes from negative to positive
                if self.TotalCummRevenue.value[i] > 0 >= self.TotalCummRevenue.value[i - 1]:
                    # we just crossed the threshold into positive project cummcashflow,
                    # so we can calculate payback period
                    dFullDiff = self.TotalCummRevenue.value[i] + math.fabs(self.TotalCummRevenue.value[(i - 1)])
                    dPerc = math.fabs(self.TotalCummRevenue.value[(i - 1)]) / dFullDiff
                    self.ProjectPaybackPeriod.value = i + dPerc

        # Calculate LCOE/LCOH
        self.LCOE.value, self.LCOH.value, self.LCOC.value = CalculateLCOELCOHLCOC(self, model)

        # https://github.com/NREL/GEOPHIRES-X/issues/232
        self.jobs_created.value = round(
            np.average(model.surfaceplant.ElectricityProduced.quantity().to(
                'MW').magnitude * self.jobs_created_per_MW_electricity.value))

        self._calculate_derived_outputs(model)
        model.logger.info(f'complete {__class__!s}: {sys._getframe().f_code.co_name}')

    @property
    def _indirect_cost_factor(self) -> float:
        return 1 + self.indirect_capital_cost_percentage.quantity().to('dimensionless').magnitude

    @property
    def _wellfield_indirect_cost_factor(self) -> float:
        return 1 + self.wellfield_indirect_capital_cost_percentage.quantity().to('dimensionless').magnitude

    @property
    def _stimulation_indirect_cost_factor(self) -> float:
        return 1 + self.stimulation_indirect_capital_cost_percentage.quantity().to('dimensionless').magnitude

    @property
    def _contingency_factor(self) -> float:
        return 1 + self.contingency_percentage.quantity().to('dimensionless').magnitude

    def calculate_wellfield_costs(self, model: Model) -> None:
        if self.per_production_well_cost.Valid:
            self.cost_one_production_well.value = self.per_production_well_cost.value
            if not self.per_injection_well_cost.Provided:
                self.cost_one_injection_well.value = self.per_production_well_cost.value
            else:
                self.cost_one_injection_well.value = self.per_injection_well_cost.value
            self.Cwell.value = ((self.cost_one_production_well.value * model.wellbores.nprod.value) +
                                (self.cost_one_injection_well.value * model.wellbores.ninj.value))
        else:
            if hasattr(model.wellbores, 'numnonverticalsections') and model.wellbores.numnonverticalsections.Provided:
                self.cost_lateral_section.value = 0.0
                if not model.wellbores.IsAGS.value:
                    input_vert_depth_km = model.reserv.depth.quantity().to('km').magnitude
                    output_vert_depth_km = 0.0
                else:
                    input_vert_depth_km = model.reserv.InputDepth.quantity().to('km').magnitude
                    output_vert_depth_km = model.reserv.OutputDepth.quantity().to('km').magnitude
                model.wellbores.injection_reservoir_depth.value = input_vert_depth_km

                tot_m, tot_vert_m, tot_horiz_m, _ = calculate_total_drilling_lengths_m(
                    model.wellbores.Configuration.value,
                    model.wellbores.numnonverticalsections.value,
                    model.wellbores.Nonvertical_length.value / 1000.0,
                    input_vert_depth_km,
                    output_vert_depth_km,
                    model.wellbores.nprod.value,
                    model.wellbores.ninj.value)

            else:
                tot_m = tot_vert_m = model.reserv.depth.quantity().to('km').magnitude
                tot_horiz_m = 0.0
                if not model.wellbores.injection_reservoir_depth.Provided:
                    model.wellbores.injection_reservoir_depth.value = model.reserv.depth.quantity().to('km').magnitude
                else:
                    model.wellbores.injection_reservoir_depth.value = model.wellbores.injection_reservoir_depth.quantity().to(
                        'km').magnitude

            self.cost_one_production_well.value = calculate_cost_of_one_vertical_well(model,
                                                                                      model.reserv.depth.quantity().to(
                                                                                          'm').magnitude,
                                                                                      self.wellcorrelation.value,
                                                                                      self.Vertical_drilling_cost_per_m.value,
                                                                                      self.per_production_well_cost.Name,
                                                                                      self.production_well_cost_adjustment_factor.value)
            if model.wellbores.ninj.value == 0:
                self.cost_one_injection_well.value = -1.0
            else:
                self.cost_one_injection_well.value = calculate_cost_of_one_vertical_well(model,
                                                                                         model.wellbores.injection_reservoir_depth.value * 1000.0,
                                                                                         self.wellcorrelation.value,
                                                                                         self.Vertical_drilling_cost_per_m.value,
                                                                                         self.per_injection_well_cost.Name,
                                                                                         self.injection_well_cost_adjustment_factor.value)

            if hasattr(model.wellbores, 'numnonverticalsections') and model.wellbores.numnonverticalsections.Provided:
                self.cost_lateral_section.value = calculate_cost_of_non_vertical_section(
                    model,
                    tot_horiz_m,
                    self.wellcorrelation.value,
                    self.Nonvertical_drilling_cost_per_m.value,
                    model.wellbores.numnonverticalsections.value,
                    self.Nonvertical_drilling_cost_per_m.Name,
                    model.wellbores.NonverticalsCased.value,
                    self.production_well_cost_adjustment_factor.value
                )
            else:
                self.cost_lateral_section.value = 0.0

            # cost of the well field
            self.Cwell.value = self._wellfield_indirect_cost_factor * (
                self.cost_one_production_well.value * model.wellbores.nprod.value +
                self.cost_one_injection_well.value * model.wellbores.ninj.value +
                self.cost_lateral_section.value
            )

    def calculate_stimulation_costs(self, model: Model) -> PlainQuantity:
        if self.ccstimfixed.Valid:
            stimulation_costs = self.ccstimfixed.quantity().to(self.Cstim.CurrentUnits).magnitude
        else:
            stim_cost_per_injection_well = self.stimulation_cost_per_injection_well.quantity().to(
                self.Cstim.CurrentUnits).magnitude
            stim_cost_per_production_well = self.stimulation_cost_per_production_well.quantity().to(
                self.Cstim.CurrentUnits).magnitude

            stimulation_costs = (
                (
                    stim_cost_per_injection_well * model.wellbores.ninj.value
                    + stim_cost_per_production_well * model.wellbores.nprod.value
                )
                * self.ccstimadjfactor.value
                * self._stimulation_indirect_cost_factor
                * self._contingency_factor
            )

        return quantity(stimulation_costs, self.Cstim.CurrentUnits)

    def calculate_field_gathering_costs(self, model: Model) -> None:
        if self.ccgathfixed.Valid:
            self.Cgath.value = self.ccgathfixed.value
        else:
            self.Cgath.value = self.ccgathadjfactor.value * 50 - 6 * np.max(
                model.surfaceplant.HeatExtracted.value) * 1000.  # (GEOPHIRES v1 correlation)
            if model.wellbores.impedancemodelused.value:
                pumphp = np.max(model.wellbores.PumpingPower.value) * 1341
                numberofpumps = np.ceil(pumphp / 2000)  # pump can be maximum 2,000 hp
                if numberofpumps == 0:
                    self.Cpumps = 0.0
                else:
                    pumphpcorrected = pumphp / numberofpumps
                    self.Cpumps = numberofpumps * 1.5 * (
                            (1750 * pumphpcorrected ** 0.7) * 3 * pumphpcorrected ** (-0.11))
            else:
                if model.wellbores.productionwellpumping.value:
                    prodpumphp = np.max(model.wellbores.PumpingPowerProd.value) / model.wellbores.nprod.value * 1341
                    Cpumpsprod = model.wellbores.nprod.value * 1.5 * (1750 * prodpumphp ** 0.7 + 5750 *
                                                                      prodpumphp ** 0.2 + 10000 + np.max(
                            model.wellbores.pumpdepth.value) * 50 * 3.281)  # see page 46 in user's manual assuming rental of rig for 1 day.
                else:
                    Cpumpsprod = 0

                injpumphp = np.max(model.wellbores.PumpingPowerInj.value) * 1341
                numberofinjpumps = np.ceil(injpumphp / 2000)  # pump can be maximum 2,000 hp
                if numberofinjpumps == 0:
                    Cpumpsinj = 0
                else:
                    injpumphpcorrected = injpumphp / numberofinjpumps
                    Cpumpsinj = numberofinjpumps * 1.5 * (
                            1750 * injpumphpcorrected ** 0.7) * 3 * injpumphpcorrected ** (-0.11)
                self.Cpumps = Cpumpsinj + Cpumpsprod

            # Based on GETEM 2016
            self.Cgath.value = self._contingency_factor * self.ccgathadjfactor.value * self._indirect_cost_factor * (
                    (model.wellbores.nprod.value + model.wellbores.ninj.value) * 750 * 500. + self.Cpumps) / 1E6

    def calculate_plant_costs(self, model: Model) -> None:
        # plant costs
        if (model.surfaceplant.enduse_option.value == EndUseOptions.HEAT
            and model.surfaceplant.plant_type.value not in [PlantType.ABSORPTION_CHILLER, PlantType.HEAT_PUMP, PlantType.DISTRICT_HEATING]):  # direct-use
            if self.ccplantfixed.Valid:
                self.Cplant.value = self.ccplantfixed.value
            else:
                self.Cplant.value = (self._indirect_cost_factor
                                     * self._contingency_factor
                                     * self.ccplantadjfactor.value
                                     * 250E-6
                                     * np.max(model.surfaceplant.HeatExtracted.value)
                                     * 1000.)

        # absorption chiller
        elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT and model.surfaceplant.plant_type.value == PlantType.ABSORPTION_CHILLER:  # absorption chiller
            if self.ccplantfixed.Valid:
                self.Cplant.value = self.ccplantfixed.value
            else:
                # this is for the direct-use part all the way up to the absorption chiller
                self.Cplant.value = (self._indirect_cost_factor
                                     * self._contingency_factor
                                     * self.ccplantadjfactor.value
                                     * 250E-6
                                     * np.max(model.surfaceplant.HeatExtracted.value)
                                     * 1000.)
                if self.chillercapex.value == -1:  # no value provided by user, use built-in correlation ($2500/ton)
                    self.chillercapex.value = (
                        self._indirect_cost_factor
                        * self._contingency_factor
                        * np.max(model.surfaceplant.cooling_produced.value)
                        * 1000 / 3.517 * 2500 / 1e6 # $2,500/ton of cooling.
                    )

                # now add chiller cost to surface plant cost
                self.Cplant.value += self.chillercapex.value

        # heat pump
        elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT and model.surfaceplant.plant_type.value == PlantType.HEAT_PUMP:
            if self.ccplantfixed.Valid:
                self.Cplant.value = self.ccplantfixed.value
            else:
                # this is for the direct-use part all the way up to the heat pump
                self.Cplant.value = self._indirect_cost_factor * self._contingency_factor * self.ccplantadjfactor.value * 250E-6 * np.max(
                    model.surfaceplant.HeatExtracted.value) * 1000.
                if self.heatpumpcapex.value == -1:  # no value provided by user, use built-in correlation ($150/kWth)
                    self.heatpumpcapex.value = self._indirect_cost_factor * self._contingency_factor * np.max(
                        model.surfaceplant.HeatProduced.value) * 1000 * 150 / 1e6  # $150/kW - TODO parameterize

                # now add heat pump cost to surface plant cost
                self.Cplant.value += self.heatpumpcapex.value

        # district heating
        elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT and model.surfaceplant.plant_type.value == PlantType.DISTRICT_HEATING:
            if self.ccplantfixed.Valid:
                self.Cplant.value = self.ccplantfixed.value
            else:
                self.Cplant.value = self._indirect_cost_factor * self._contingency_factor * self.ccplantadjfactor.value * 250E-6 * np.max(
                    model.surfaceplant.HeatExtracted.value) * 1000.

                # add 65$/KW for peaking boiler
                self.peakingboilercost.value = (self.peaking_boiler_cost_per_kW.quantity()
                                                .to('USD / kilowatt').magnitude
                                                * model.surfaceplant.max_peaking_boiler_demand.value / 1000)

                # add peaking boiler cost to surface plant cost
                self.Cplant.value += self.peakingboilercost.value


        else:  # all other options have power plant
            if model.surfaceplant.plant_type.value == PlantType.SUB_CRITICAL_ORC:
                MaxProducedTemperature = np.max(model.surfaceplant.TenteringPP.value)
                if MaxProducedTemperature < 150.:
                    C3 = -1.458333E-3
                    C2 = 7.6875E-1
                    C1 = -1.347917E2
                    C0 = 1.0075E4
                    CCAPP1 = C3 * MaxProducedTemperature ** 3 + C2 * MaxProducedTemperature ** 2 + C1 * MaxProducedTemperature + C0
                else:
                    CCAPP1 = 2231 - 2 * (MaxProducedTemperature - 150.)
                x = np.max(model.surfaceplant.ElectricityProduced.value)
                y = np.max(model.surfaceplant.ElectricityProduced.value)
                if y == 0.0:
                    y = 15.0
                z = math.pow(y / 15., -0.06)
                self.Cplantcorrelation = CCAPP1 * z * x * 1000. / 1E6

            elif model.surfaceplant.plant_type.value == PlantType.SUPER_CRITICAL_ORC:
                MaxProducedTemperature = np.max(model.surfaceplant.TenteringPP.value)
                if MaxProducedTemperature < 150.:
                    C3 = -1.458333E-3
                    C2 = 7.6875E-1
                    C1 = -1.347917E2
                    C0 = 1.0075E4
                    CCAPP1 = C3 * MaxProducedTemperature ** 3 + C2 * MaxProducedTemperature ** 2 + C1 * MaxProducedTemperature + C0
                else:
                    CCAPP1 = 2231 - 2 * (MaxProducedTemperature - 150.)
                # factor 1.1 to make supercritical 10% more expansive than subcritical
                self.Cplantcorrelation = 1.1 * CCAPP1 * math.pow(
                    np.max(model.surfaceplant.ElectricityProduced.value) / 15., -0.06) * np.max(
                    model.surfaceplant.ElectricityProduced.value) * 1000. / 1E6

            elif model.surfaceplant.plant_type.value == PlantType.SINGLE_FLASH:
                if np.max(model.surfaceplant.ElectricityProduced.value) < 10.:
                    C2 = 4.8472E-2
                    C1 = -35.2186
                    C0 = 8.4474E3
                    D2 = 4.0604E-2
                    D1 = -29.3817
                    D0 = 6.9911E3
                    PLL = 5.
                    PRL = 10.
                elif np.max(model.surfaceplant.ElectricityProduced.value) < 25.:
                    C2 = 4.0604E-2
                    C1 = -29.3817
                    C0 = 6.9911E3
                    D2 = 3.2773E-2
                    D1 = -23.5519
                    D0 = 5.5263E3
                    PLL = 10.
                    PRL = 25.
                elif np.max(model.surfaceplant.ElectricityProduced.value) < 50.:
                    C2 = 3.2773E-2
                    C1 = -23.5519
                    C0 = 5.5263E3
                    D2 = 3.4716E-2
                    D1 = -23.8139
                    D0 = 5.1787E3
                    PLL = 25.
                    PRL = 50.
                elif np.max(model.surfaceplant.ElectricityProduced.value) < 75.:
                    C2 = 3.4716E-2
                    C1 = -23.8139
                    C0 = 5.1787E3
                    D2 = 3.5271E-2
                    D1 = -24.3962
                    D0 = 5.1972E3
                    PLL = 50.
                    PRL = 75.
                else:
                    C2 = 3.5271E-2
                    C1 = -24.3962
                    C0 = 5.1972E3
                    D2 = 3.3908E-2
                    D1 = -23.4890
                    D0 = 5.0238E3
                    PLL = 75.
                    PRL = 100.
                maxProdTemp = np.max(model.surfaceplant.TenteringPP.value)
                CCAPPLL = C2 * maxProdTemp ** 2 + C1 * maxProdTemp + C0
                CCAPPRL = D2 * maxProdTemp ** 2 + D1 * maxProdTemp + D0
                b = math.log(CCAPPRL / CCAPPLL) / math.log(PRL / PLL)
                a = CCAPPRL / PRL ** b
                # factor 0.75 to make double flash 25% more expansive than single flash
                self.Cplantcorrelation = (0.8 * a * math.pow(np.max(model.surfaceplant.ElectricityProduced.value), b) *
                                          np.max(model.surfaceplant.ElectricityProduced.value) * 1000. / 1E6)

            elif model.surfaceplant.plant_type.value == PlantType.DOUBLE_FLASH:
                if np.max(model.surfaceplant.ElectricityProduced.value) < 10.:
                    C2 = 4.8472E-2
                    C1 = -35.2186
                    C0 = 8.4474E3
                    D2 = 4.0604E-2
                    D1 = -29.3817
                    D0 = 6.9911E3
                    PLL = 5.
                    PRL = 10.
                elif np.max(model.surfaceplant.ElectricityProduced.value) < 25.:
                    C2 = 4.0604E-2
                    C1 = -29.3817
                    C0 = 6.9911E3
                    D2 = 3.2773E-2
                    D1 = -23.5519
                    D0 = 5.5263E3
                    PLL = 10.
                    PRL = 25.
                elif np.max(model.surfaceplant.ElectricityProduced.value) < 50.:
                    C2 = 3.2773E-2
                    C1 = -23.5519
                    C0 = 5.5263E3
                    D2 = 3.4716E-2
                    D1 = -23.8139
                    D0 = 5.1787E3
                    PLL = 25.
                    PRL = 50.
                elif np.max(model.surfaceplant.ElectricityProduced.value) < 75.:
                    C2 = 3.4716E-2
                    C1 = -23.8139
                    C0 = 5.1787E3
                    D2 = 3.5271E-2
                    D1 = -24.3962
                    D0 = 5.1972E3
                    PLL = 50.
                    PRL = 75.
                else:
                    C2 = 3.5271E-2
                    C1 = -24.3962
                    C0 = 5.1972E3
                    D2 = 3.3908E-2
                    D1 = -23.4890
                    D0 = 5.0238E3
                    PLL = 75.
                    PRL = 100.
                maxProdTemp = np.max(model.surfaceplant.TenteringPP.value)
                CCAPPLL = C2 * maxProdTemp ** 2 + C1 * maxProdTemp + C0
                CCAPPRL = D2 * maxProdTemp ** 2 + D1 * maxProdTemp + D0
                b = math.log(CCAPPRL / CCAPPLL) / math.log(PRL / PLL)
                a = CCAPPRL / PRL ** b
                self.Cplantcorrelation = (a * math.pow(np.max(model.surfaceplant.ElectricityProduced.value), b) *
                                          np.max(model.surfaceplant.ElectricityProduced.value) * 1000. / 1E6)

            if self.ccplantfixed.Valid:
                self.Cplant.value = self.ccplantfixed.value
                self.CAPEX_cost_electricity_plant = self.Cplant.value * self.CAPEX_heat_electricity_plant_ratio.value
                self.CAPEX_cost_heat_plant = self.Cplant.value * (1.0 - self.CAPEX_heat_electricity_plant_ratio.value)
            else:
                if self.Power_plant_cost_per_kWe.Provided:
                    nameplate_capacity_kW = np.max(model.surfaceplant.ElectricityProduced.quantity().to('kW'))
                    direct_plant_cost_MUSD = (nameplate_capacity_kW.magnitude *
                                              model.economics.Power_plant_cost_per_kWe
                                              .quantity().to('MUSD / kW').magnitude)
                else:
                    # 1.02 to convert cost from 2012 to 2016
                    # factor 1.10 to convert from 2016 to 2022
                    direct_plant_cost_MUSD = self.ccplantadjfactor.value * self.Cplantcorrelation * 1.02 * 1.10

                self.Cplant.value = self._indirect_cost_factor * self._contingency_factor * direct_plant_cost_MUSD
                self.CAPEX_cost_electricity_plant = self.Cplant.value

        # add direct-use plant cost of co-gen system to Cplant (only of no total Cplant was provided)
        if not self.ccplantfixed.Valid:
            if model.surfaceplant.enduse_option.value in [EndUseOptions.COGENERATION_TOPPING_EXTRA_ELECTRICITY,
                                                          EndUseOptions.COGENERATION_TOPPING_EXTRA_HEAT]:  # enduse_option = 3: cogen topping cycle
                self.CAPEX_cost_heat_plant = (
                    self._indirect_cost_factor
                    * self._contingency_factor
                    * self.ccplantadjfactor.value
                    * 250E-6
                    * np.max(model.surfaceplant.HeatProduced.value / model.surfaceplant.enduse_efficiency_factor.value)
                    * 1000.
                )
            elif model.surfaceplant.enduse_option.value in [EndUseOptions.COGENERATION_BOTTOMING_EXTRA_HEAT,
                                                            EndUseOptions.COGENERATION_BOTTOMING_EXTRA_ELECTRICITY]:  # enduse_option = 4: cogen bottoming cycle
                self.CAPEX_cost_heat_plant = self._indirect_cost_factor * self._contingency_factor * self.ccplantadjfactor.value * 250E-6 * np.max(
                    model.surfaceplant.HeatProduced.value / model.surfaceplant.enduse_efficiency_factor.value) * 1000.
            elif model.surfaceplant.enduse_option.value in [EndUseOptions.COGENERATION_PARALLEL_EXTRA_ELECTRICITY,
                                                            EndUseOptions.COGENERATION_PARALLEL_EXTRA_HEAT]:  # cogen parallel cycle
                self.CAPEX_cost_heat_plant = self._indirect_cost_factor * self._contingency_factor * self.ccplantadjfactor.value * 250E-6 * np.max(
                    model.surfaceplant.HeatProduced.value / model.surfaceplant.enduse_efficiency_factor.value) * 1000.

            self.Cplant.value = self.Cplant.value + self.CAPEX_cost_heat_plant
            if not self.CAPEX_heat_electricity_plant_ratio.Provided:
                self.CAPEX_heat_electricity_plant_ratio.value = self.CAPEX_cost_electricity_plant/self.Cplant.value

    def calculate_total_capital_costs(self, model: Model) -> None:
        if not self.totalcapcost.Valid:
            # exploration costs (same as in Geophires v1.2) (M$)
            if self.ccexplfixed.Valid:
                self.Cexpl.value = self.ccexplfixed.value
            else:
                self.Cexpl.value = self._contingency_factor * self.ccexpladjfactor.value * self._indirect_cost_factor * (
                    1. + self.cost_one_production_well.value * 0.6)

            # Surface Piping Length Costs (M$) #assumed $750k/km  # TODO parameterize
            self.Cpiping.value = 750 / 1000 * model.surfaceplant.piping_length.value

            # district heating network costs
            if model.surfaceplant.plant_type.value == PlantType.DISTRICT_HEATING:  # district heat
                if self.dhtotaldistrictnetworkcost.Provided:
                    self.dhdistrictcost.value = self.dhtotaldistrictnetworkcost.value
                elif self.dhpipinglength.Provided:
                    self.dhdistrictcost.value = self.dhpipinglength.value * self.dhpipingcostrate.value / 1000  # M$
                elif self.dhroadlength.Provided:  # check if road length is provided to calculate cost
                    self.dhdistrictcost.value = self.dhroadlength.value * 0.75 * self.dhpipingcostrate.value / 1000  # M$ (assuming 75% of road length is used for district network piping)
                else:  # calculate district network cost based on population density
                    if self.dhlandarea.Provided == False:
                        model.logger.warning("District heating network cost calculated based on default district area")
                    if self.dhpopulation.Provided:
                        self.populationdensity.value = self.dhpopulation.value / self.dhlandarea.value
                    elif model.surfaceplant.dh_number_of_housing_units.Provided:
                        self.populationdensity.value = model.surfaceplant.dh_number_of_housing_units.value * 2.6 / self.dhlandarea.value  # estimate population based on 2.6 number of people per household
                    else:
                        model.logger.warning(
                            "District heating network cost calculated based on default number of people in district")
                        self.populationdensity.value = self.dhpopulation.value / self.dhlandarea.value

                    if self.populationdensity.value > 1000:
                        self.dhpipinglength.value = 7.5 * self.dhlandarea.value  # using constant 7.5km of pipe per km^2 when population density is >1500
                    else:
                        self.dhpipinglength.value = max(
                            self.populationdensity.value / 1000 * 7.5 * self.dhlandarea.value,
                            self.dhlandarea.value)  # scale the piping length based on population density, but with a minimum of 1 km of piping per km^2 of area
                    self.dhdistrictcost.value = self.dhpipingcostrate.value * self.dhpipinglength.value / 1000

            else:
                self.dhdistrictcost.value = 0

            self.CCap.value = self.Cexpl.value + self.Cwell.value + self.Cstim.value + self.Cgath.value + self.Cplant.value + self.Cpiping.value + self.dhdistrictcost.value
        else:
            self.CCap.value = self.totalcapcost.value

        if self.RITC.Provided and self.econmodel.value != EconomicModel.SAM_SINGLE_OWNER_PPA:
            # update the capital costs, assuming the entire ITC is used to reduce the capital costs
            # (not applied for SAM Economic Models since they handle ITC in cash flow, not capex)
            self.RITCValue.value = self.RITC.value * self.CCap.value
            self.CCap.value = self.CCap.value - self.RITCValue.value

        # Add in the FlatLicenseEtc, OtherIncentives, & TotalGrant
        self.CCap.value = self.CCap.value + self.FlatLicenseEtc.value - self.OtherIncentives.value - self.TotalGrant.value

    def calculate_operating_and_maintenance_costs(self, model: Model) -> None:
        # O&M costs
        # calculate first O&M costs independent of whether oamtotalfixed is provided or not
        # additional electricity cost for heat pump as end-use
        if model.surfaceplant.plant_type.value == PlantType.HEAT_PUMP:  # heat pump:
            self.averageannualheatpumpelectricitycost.value = np.average(
                model.surfaceplant.heat_pump_electricity_kwh_used.value) * model.surfaceplant.electricity_cost_to_buy.value / 1E6  # M$/year

        # district heating peaking fuel annual cost
        if model.surfaceplant.plant_type.value == PlantType.DISTRICT_HEATING:  # district heating
            self.annualngcost.value = model.surfaceplant.annual_ng_demand.value * self.ngprice.value / 1000 / self.peakingboilerefficiency.value  # array with annual O&M cost for peaking fuel
            self.averageannualngcost.value = np.average(self.annualngcost.value)

        # calculate average annual pumping costs in case no electricity is provided
        if model.surfaceplant.plant_type.value in [PlantType.INDUSTRIAL, PlantType.ABSORPTION_CHILLER,
                                                   PlantType.HEAT_PUMP, PlantType.DISTRICT_HEATING]:
            self.averageannualpumpingcosts.value = np.average(
                model.surfaceplant.PumpingkWh.value) * model.surfaceplant.electricity_cost_to_buy.value / 1E6  # M$/year

        if not self.oamtotalfixed.Valid:
            # labor cost
            if model.surfaceplant.enduse_option.value == EndUseOptions.ELECTRICITY:  # electricity
                if np.max(model.surfaceplant.ElectricityProduced.value) < 2.5:
                    self.Claborcorrelation = 236. / 1E3  # M$/year
                else:
                    self.Claborcorrelation = (589. * math.log(
                        np.max(model.surfaceplant.ElectricityProduced.value)) - 304.) / 1E3  # M$/year
            else:
                if np.max(model.surfaceplant.HeatExtracted.value) < 2.5 * 5.:
                    self.Claborcorrelation = 236. / 1E3  # M$/year
                else:
                    self.Claborcorrelation = (589. * math.log(
                        np.max(model.surfaceplant.HeatExtracted.value) / 5.) - 304.) / 1E3  # M$/year
                # * 1.1 to convert from 2012 to 2016$ with BLS employment cost index (for utilities in March)
            self.Claborcorrelation = self.Claborcorrelation * 1.1

            # plant O&M cost
            if self.oamplantfixed.Valid:
                self.Coamplant.value = self.oamplantfixed.value
            else:
                self.Coamplant.value = self.oamplantadjfactor.value * (
                    1.5 / 100. * self.Cplant.value + 0.75 * self.Claborcorrelation)

            # wellfield O&M cost
            if self.oamwellfixed.Valid:
                self.Coamwell.value = self.oamwellfixed.value
            else:
                self.Coamwell.value = self.oamwelladjfactor.value * (
                    1. / 100. * (self.Cwell.value + self.Cgath.value) + 0.25 * self.Claborcorrelation)

            # water O&M cost
            if self.oamwaterfixed.Valid:
                self.Coamwater.value = self.oamwaterfixed.value
            else:
                # here is assumed 1 l per kg maybe correct with real temp. (M$/year) 925$/ML = 3.5$/1,000 gallon
                # TODO parameterize
                self.Coamwater.value = self.oamwateradjfactor.value * (model.wellbores.nprod.value *
                                                                       model.wellbores.prodwellflowrate.value *
                                                                       model.reserv.waterloss.value * model.surfaceplant.utilization_factor.value *
                                                                       365. * 24. * 3600. / 1E6 * 925. / 1E6)

            # additional O&M cost for absorption chiller if used
            if model.surfaceplant.plant_type.value == PlantType.ABSORPTION_CHILLER:  # absorption chiller:
                if self.chilleropex.value == -1:
                    self.chilleropex.value = self.chillercapex.value * 2 / 100  # assumed annual O&M for chiller is 2% of investment cost

                # correct plant O&M cost as otherwise chiller opex would be counted double (subtract chiller capex from plant cost when calculating Coandmplant)
                if self.oamplantfixed.Valid == False:
                    self.Coamplant.value = self.oamplantadjfactor.value * (
                        1.5 / 100. * (self.Cplant.value - self.chillercapex.value) + 0.75 * self.Claborcorrelation)

            else:
                self.chilleropex.value = 0

            # district heating O&M cost
            if model.surfaceplant.plant_type.value == PlantType.DISTRICT_HEATING:  # district heating
                self.annualngcost.value = model.surfaceplant.annual_ng_demand.value * self.ngprice.value / 1000  # array with annual O&M cost for peaking fuel

                if self.dhoandmcost.Provided:
                    self.dhdistrictoandmcost.value = self.dhoandmcost.value  # M$/yr
                else:
                    self.dhdistrictoandmcost.value = 0.01 * self.dhdistrictcost.value + 0.02 * sum(
                        model.surfaceplant.daily_heating_demand.value) * model.surfaceplant.electricity_cost_to_buy.value / 1000  # [M$/year] we assume annual district OPEX equals 1% of district CAPEX and 2% of total heat demand for pumping costs

            else:
                self.dhdistrictoandmcost.value = 0

            self.Coam.value = self.Coamwell.value + self.Coamplant.value + self.Coamwater.value + self.chilleropex.value + self.dhdistrictoandmcost.value  # total O&M cost (M$/year)

        else:
            self.Coam.value = self.oamtotalfixed.value  # total O&M cost (M$/year)

        if model.wellbores.redrill.value > 0:
            # account for well redrilling
            redrilling_costs: PlainQuantity = self.calculate_redrilling_costs(model)
            self.redrilling_annual_cost.value = redrilling_costs.to(self.redrilling_annual_cost.CurrentUnits).magnitude
            self.Coam.value += redrilling_costs.to(self.Coam.CurrentUnits).magnitude

        # Add in the AnnualLicenseEtc and TaxRelief
        self.Coam.value = self.Coam.value + self.AnnualLicenseEtc.value - self.TaxRelief.value

        # partition the OPEX for CHP plants based on the CAPEX ratio
        self.OPEX_cost_electricity_plant = self.Coam.value * self.CAPEX_heat_electricity_plant_ratio.value
        self.OPEX_cost_heat_plant = self.Coam.value * (1.0 - self.CAPEX_heat_electricity_plant_ratio.value)

    def calculate_redrilling_costs(self, model: Model) -> PlainQuantity:
        return ((self.Cwell.quantity() + self.Cstim.quantity())
                * model.wellbores.redrill.quantity()
                / model.surfaceplant.plant_lifetime.quantity())

    def build_price_models(self, model: Model) -> None:
        # build the PTC price models
        self.PTCElecPrice = [0.0] * model.surfaceplant.plant_lifetime.value
        self.PTCHeatPrice = [0.0] * model.surfaceplant.plant_lifetime.value
        self.PTCCoolingPrice = [0.0] * model.surfaceplant.plant_lifetime.value
        self.PTCCarbonPrice = [0.0] * model.surfaceplant.plant_lifetime.value
        if self.PTCElec.Provided:
            self.PTCElecPrice = BuildPTCModel(model.surfaceplant.plant_lifetime.value,
                                              self.PTCDuration.value, self.PTCElec.value,
                                              self.PTCInflationAdjusted.value,
                                              self.RINFL.value)
        if self.PTCHeat.Provided:
            self.PTCHeatPrice = BuildPTCModel(model.surfaceplant.plant_lifetime.value,
                                              self.PTCDuration.value, self.PTCHeat.value,
                                              self.PTCInflationAdjusted.value,
                                              self.RINFL.value)
        if self.PTCCooling.Provided:
            self.PTCCoolingPrice = BuildPTCModel(model.surfaceplant.plant_lifetime.value,
                                                 self.PTCDuration.value, self.PTCCooling.value,
                                                 self.PTCInflationAdjusted.value,
                                                 self.RINFL.value)

        # build the price models
        self.ElecPrice.value = BuildPricingModel(model.surfaceplant.plant_lifetime.value,
                                                 self.ElecStartPrice.value, self.ElecEndPrice.value,
                                                 self.ElecEscalationStart.value, self.ElecEscalationRate.value,
                                                 self.PTCElecPrice)
        self.HeatPrice.value = BuildPricingModel(model.surfaceplant.plant_lifetime.value,
                                                 self.HeatStartPrice.value, self.HeatEndPrice.value,
                                                 self.HeatEscalationStart.value, self.HeatEscalationRate.value,
                                                 self.PTCHeatPrice)
        self.CoolingPrice.value = BuildPricingModel(model.surfaceplant.plant_lifetime.value,
                                                    self.CoolingStartPrice.value, self.CoolingEndPrice.value,
                                                    self.CoolingEscalationStart.value, self.CoolingEscalationRate.value,
                                                    self.PTCCoolingPrice)
        self.CarbonPrice.value = BuildPricingModel(model.surfaceplant.plant_lifetime.value,
                                                   self.CarbonStartPrice.value, self.CarbonEndPrice.value,
                                                   self.CarbonEscalationStart.value, self.CarbonEscalationRate.value,
                                                   self.PTCCarbonPrice)

    def get_royalty_rate_schedule(self, model: Model) -> list[float]:
        """
        Builds a year-by-year schedule of royalty rates based on escalation and cap.

        :type model: :class:`~geophires_x.Model.Model`
        :return: schedule: A list of rates as fractions (e.g., 0.05 for 5%).
        """

        def r(x: float) -> float:
            """Ignore apparent float precision issue"""
            _precision = 8
            return round(x, _precision)

        plant_lifetime = model.surfaceplant.plant_lifetime.value

        escalation_rate = r(self.royalty_escalation_rate.value)
        max_rate = r(self.maximum_royalty_rate.value)

        schedule = []
        current_rate = r(self.royalty_rate.value)
        for year_index in range(plant_lifetime):
            current_rate = r(current_rate)
            schedule.append(min(current_rate, max_rate))
            if year_index >= (model.economics.royalty_escalation_rate_start_year.value - 2):
                current_rate += escalation_rate

        return schedule


    def calculate_cashflow(self, model: Model) -> None:
            """
            Calculate cashflow and cumulative cash flow

            Note that these calculations are irrelevant and ignored for SAM economic models, except for
            carbon calculations.
            """

            total_duration = model.surfaceplant.plant_lifetime.value + model.surfaceplant.construction_years.value
            self.ElecRevenue.value = [0.0] * total_duration
            self.ElecCummRevenue.value = [0.0] * total_duration
            self.HeatRevenue.value = [0.0] * total_duration
            self.HeatCummRevenue.value = [0.0] * total_duration
            self.CoolingRevenue.value = [0.0] * total_duration
            self.CoolingCummRevenue.value = [0.0] * total_duration
            self.CarbonRevenue.value = [0.0] * total_duration
            self.CarbonCummCashFlow.value = [0.0] * total_duration
            self.TotalRevenue.value = [0.0] * total_duration
            self.TotalCummRevenue.value = [0.0] * total_duration
            self.CarbonThatWouldHaveBeenProducedTotal.value = 0.0

            # Based on the style of the project, calculate the revenue & cumulative revenue
            if model.surfaceplant.enduse_option.value == EndUseOptions.ELECTRICITY:
                self.ElecRevenue.value, self.ElecCummRevenue.value = CalculateRevenue(
                    model.surfaceplant.plant_lifetime.value, model.surfaceplant.construction_years.value,
                    model.surfaceplant.NetkWhProduced.value, self.ElecPrice.value)
                self.TotalRevenue.value = self.ElecRevenue.value.copy()
                #self.TotalCummRevenue.value = self.ElecCummRevenue.value
            elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT and model.surfaceplant.plant_type.value not in [PlantType.ABSORPTION_CHILLER]:
                self.HeatRevenue.value, self.HeatCummRevenue.value = CalculateRevenue(
                    model.surfaceplant.plant_lifetime.value, model.surfaceplant.construction_years.value,
                    model.surfaceplant.HeatkWhProduced.value, self.HeatPrice.value)
                self.TotalRevenue.value = self.HeatRevenue.value.copy()
                #self.TotalCummRevenue.value = self.HeatCummRevenue.value
            elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT and model.surfaceplant.plant_type.value in [PlantType.ABSORPTION_CHILLER]:
                self.CoolingRevenue.value, self.CoolingCummRevenue.value = CalculateRevenue(
                    model.surfaceplant.plant_lifetime.value, model.surfaceplant.construction_years.value,
                    model.surfaceplant.cooling_kWh_Produced.value, self.CoolingPrice.value)
                self.TotalRevenue.value = self.CoolingRevenue.value.copy()
                #self.TotalCummRevenue.value = self.CoolingCummRevenue.value
            elif model.surfaceplant.enduse_option.value in [EndUseOptions.COGENERATION_TOPPING_EXTRA_HEAT,
                                                            EndUseOptions.COGENERATION_TOPPING_EXTRA_ELECTRICITY,
                                                            EndUseOptions.COGENERATION_BOTTOMING_EXTRA_ELECTRICITY,
                                                            EndUseOptions.COGENERATION_BOTTOMING_EXTRA_HEAT,
                                                            EndUseOptions.COGENERATION_PARALLEL_EXTRA_HEAT,
                                                            EndUseOptions.COGENERATION_PARALLEL_EXTRA_ELECTRICITY]:  # co-gen
                # else:
                self.ElecRevenue.value, self.ElecCummRevenue.value = CalculateRevenue(
                    model.surfaceplant.plant_lifetime.value, model.surfaceplant.construction_years.value,
                    model.surfaceplant.NetkWhProduced.value, self.ElecPrice.value)
                self.HeatRevenue.value, self.HeatCummRevenue.value = CalculateRevenue(
                    model.surfaceplant.plant_lifetime.value, model.surfaceplant.construction_years.value,
                    model.surfaceplant.HeatkWhProduced.value, self.HeatPrice.value)

                for i in range(0, model.surfaceplant.plant_lifetime.value + model.surfaceplant.construction_years.value, 1):
                    self.TotalRevenue.value[i] = self.ElecRevenue.value[i] + self.HeatRevenue.value[i]
                    #if i > 0:
                    #    self.TotalCummRevenue.value[i] = self.TotalCummRevenue.value[i - 1] + self.TotalRevenue.value[i]

            if self.DoCarbonCalculations.value:
                self.CarbonRevenue.value, self.CarbonCummCashFlow.value, self.CarbonThatWouldHaveBeenProducedAnnually.value, \
                 self.CarbonThatWouldHaveBeenProducedTotal.value = CalculateCarbonRevenue(model,
                      model.surfaceplant.plant_lifetime.value, model.surfaceplant.construction_years.value,
                      self.CarbonPrice.value, self.GridCO2Intensity.value, self.NaturalGasCO2Intensity.value,
                      model.surfaceplant.NetkWhProduced.value, model.surfaceplant.HeatkWhProduced.value)
                for i in range(model.surfaceplant.construction_years.value, model.surfaceplant.plant_lifetime.value + model.surfaceplant.construction_years.value, 1):
                    self.TotalRevenue.value[i] = self.TotalRevenue.value[i] + self.CarbonRevenue.value[i]
                    #self.TotalCummRevenue.value[i] = self.TotalCummRevenue.value[i] + self.CarbonCummCashFlow.value[i]

            # for the sake of display, insert zeros at the beginning of the pricing arrays
            for i in range(0, model.surfaceplant.construction_years.value, 1):
                self.ElecPrice.value.insert(0, 0.0)
                self.HeatPrice.value.insert(0, 0.0)
                self.CoolingPrice.value.insert(0, 0.0)
                self.CarbonPrice.value.insert(0, 0.0)

            # Insert the cost of construction into the front of the array that will be used to calculate NPV
            # the convention is that the upfront CAPEX is negative
            # This is the same for all projects
            ProjectCAPEXPerConstructionYear = self.CCap.value / model.surfaceplant.construction_years.value
            for i in range(0, model.surfaceplant.construction_years.value, 1):
                self.TotalRevenue.value[i] = -1.0 * ProjectCAPEXPerConstructionYear
                self.TotalCummRevenue.value[i] = -1.0 * ProjectCAPEXPerConstructionYear
    #        self.TotalRevenue.value, self.TotalCummRevenue.value = CalculateTotalRevenue(
    #            model.surfaceplant.plant_lifetime.value, model.surfaceplant.construction_years.value, self.CCap.value,
    #                self.Coam.value, self.TotalRevenue.value, self.TotalCummRevenue.value)

            # Do a one-time calculation that accounts for OPEX - no OPEX in the first year.
            for i in range(model.surfaceplant.construction_years.value,
                           model.surfaceplant.plant_lifetime.value + model.surfaceplant.construction_years.value, 1):
                self.TotalRevenue.value[i] = self.TotalRevenue.value[i] - self.Coam.value

            # Now do a one-time calculation that calculates the cumulative cash flow after everything else has been accounted for
            for i in range(1, model.surfaceplant.plant_lifetime.value + model.surfaceplant.construction_years.value, 1):
                self.TotalCummRevenue.value[i] = self.TotalCummRevenue.value[i-1] + self.TotalRevenue.value[i]

    def _calculate_sam_economics(self, model: Model) -> None:
        non_calculated_output_placeholder_val = -1
        self.sam_economics_calculations: SamEconomicsCalculations = calculate_sam_economics(model)

        # Setting capex_total distinguishes capex from CCap's display name of 'Total capital costs',
        # since SAM Economic Model doesn't subtract ITC from this value.
        self.capex_total.value = (self.sam_economics_calculations.capex.quantity()
                                  .to(self.capex_total.CurrentUnits.value).magnitude)
        self.CCap.value = (self.sam_economics_calculations.capex.quantity()
                           .to(self.CCap.CurrentUnits.value).magnitude)

        self.overnight_capital_cost.value = (self.sam_economics_calculations.overnight_capital_cost.quantity()
                                             .to(self.overnight_capital_cost.CurrentUnits.value).magnitude)

        self.interest_during_construction.value = quantity(
            self.sam_economics_calculations.pre_revenue_costs_and_cash_flow.interest_during_construction_usd,
            'USD'
        ).to(self.interest_during_construction.CurrentUnits.value).magnitude


        if self.royalty_rate.Provided:
            # ignore pre-revenue year(s) (e.g. Year 0)
            pre_revenue_years_slice_index = model.surfaceplant.construction_years.value

            average_annual_royalties = np.average(
                self.sam_economics_calculations.royalties_opex.value[pre_revenue_years_slice_index:]
            )

            self.royalties_average_annual_cost.value = (quantity(
                average_annual_royalties,
                self.sam_economics_calculations.royalties_opex.CurrentUnits
            ).to(self.royalties_average_annual_cost.CurrentUnits).magnitude)

            self.Coam.value += (self.royalties_average_annual_cost.quantity()
                                .to(self.Coam.CurrentUnits.value).magnitude)

            self.royalty_holder_npv.value = quantity(
                calculate_npv(
                    self.royalty_holder_discount_rate.value,
                    self.sam_economics_calculations.royalties_opex.value,
                    self.discount_initial_year_cashflow.value
                ),
                self.sam_economics_calculations.royalties_opex.CurrentUnits.get_currency_unit_str()
            ).to(self.royalty_holder_npv.CurrentUnits).magnitude

            self.royalty_holder_annual_revenue.value = self.royalties_average_annual_cost.value

            self.royalty_holder_total_revenue.value = quantity(
                np.sum(
                    self.sam_economics_calculations.royalties_opex.value[pre_revenue_years_slice_index:]
                ),
                self.sam_economics_calculations.royalties_opex.CurrentUnits.get_currency_unit_str()
            ).to(self.royalty_holder_total_revenue.CurrentUnits).magnitude


        self.wacc.value = self.sam_economics_calculations.wacc.value
        self.nominal_discount_rate.value = self.sam_economics_calculations.nominal_discount_rate.value
        self.ProjectNPV.value = self.sam_economics_calculations.project_npv.quantity().to(
            convertible_unit(self.ProjectNPV.CurrentUnits)).magnitude

        self.ProjectIRR.value = non_calculated_output_placeholder_val  # SAM calculates After-Tax IRR instead
        self.after_tax_irr.value = self.sam_economics_calculations.after_tax_irr.quantity().to(
            convertible_unit(self.ProjectIRR.CurrentUnits)).magnitude

        self.ProjectMOIC.value = self.sam_economics_calculations.moic.value
        self.ProjectVIR.value = self.sam_economics_calculations.project_vir.value

        self.ProjectPaybackPeriod.value = self.sam_economics_calculations.project_payback_period.value

        self.RITCValue.value = self.sam_economics_calculations.investment_tax_credit.quantity().to(
            self.RITCValue.CurrentUnits).magnitude

    # noinspection SpellCheckingInspection
    def _calculate_derived_outputs(self, model: Model) -> None:
        """
        Subclasses should call _calculate_derived_outputs at the end of their Calculate methods to populate output
        values that are derived from subclass-calculated outputs.
        """

        if hasattr(self, 'cost_lateral_section') and self.cost_lateral_section.value != 0:
            self.cost_per_lateral_section.value = (
                self.cost_lateral_section.quantity().to(self.cost_per_lateral_section.CurrentUnits).magnitude
                / model.wellbores.numnonverticalsections.value
            )

        if hasattr(self, 'discountrate'):
            self.real_discount_rate.value = self.discountrate.quantity().to(convertible_unit(
                self.real_discount_rate.CurrentUnits)).magnitude

        if hasattr(self, 'Cwell') and hasattr(model.wellbores, 'nprod') and hasattr(model.wellbores, 'ninj'):
            self.drilling_and_completion_costs_per_well.value = (
                self.Cwell.value /
                (model.wellbores.nprod.value + model.wellbores.ninj.value)
            )



    def __str__(self):
        return "Economics"



