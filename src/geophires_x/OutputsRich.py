import datetime
import string
import time
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import rich
from matplotlib import pyplot as plt
from rich.console import Console
from rich.table import Table

import geophires_x
from geophires_x import Model as Model
from geophires_x.Economics import Economics

from geophires_x.GeoPHIRESUtils import UpgradeSymbologyOfUnits, render_default, InsertImagesIntoHTML
from geophires_x.MatplotlibUtils import plt_subplots
from geophires_x.OptionList import EndUseOptions, PlantType, EconomicModel, ReservoirModel, FractureShape, \
    ReservoirVolume
from geophires_x.OutputsUtils import OutputTableItem

from geophires_x.Parameter import intParameter, strParameter

NL = '\n'
validFilenameChars = "-_.() %s%s" % (string.ascii_letters, string.digits)

# Duplicative of Outputs.VERTICAL_WELL_DEPTH_OUTPUT_NAME to avoid circular import
VERTICAL_WELL_DEPTH_OUTPUT_NAME = 'Well depth'

_GRAPH_FIGSIZE = (12, 6)

def print_outputs_rich(
        text_output_file: strParameter,
        html_output_file: strParameter,
        model: Model,
        sdac_results: list,
        addon_results: list,
        sdac_df: pd.DataFrame,
        addon_df: pd.DataFrame):
    """
    TODO Implementation of rich output in this method/file is duplicative of Outputs.PrintOutputs. This adds undue
      code complexity, maintenance overhead, inconsistency, and potential for bugs. Rich output should instead be
      generated in a module that uses GeophiresXClient or an equivalent pattern which maintains Outputs.PrintOutputs
      as the ultimate source of truth/authority for output logic.
    """

    # data structures and assignments for HTML and Improved Text Output formats
    simulation_metadata = []
    summary = []
    economic_parameters = []
    engineering_parameters = []
    resource_characteristics = []
    reservoir_parameters = []
    reservoir_stimulation_results = []
    CAPEX = []
    OPEX = []
    surface_equipment_results = []
    # addon_results = []

    simulation_metadata.append(OutputTableItem('GEOPHIRES Version', geophires_x.__version__))
    simulation_metadata.append(OutputTableItem('Simulation Date', datetime.datetime.now().strftime('%Y-%m-%d')))
    simulation_metadata.append(OutputTableItem('Simulation Time', datetime.datetime.now().strftime('%H:%M')))
    simulation_metadata.append(
        OutputTableItem('Calculation Time', '{0:10.3f}'.format((time.time() - model.tic)) + ' sec'))

    summary.append(OutputTableItem('End-Use Option', str(model.surfaceplant.enduse_option.value.value)))

    if model.surfaceplant.enduse_option.value in [EndUseOptions.ELECTRICITY,
                                                  EndUseOptions.COGENERATION_TOPPING_EXTRA_HEAT,
                                                  EndUseOptions.COGENERATION_TOPPING_EXTRA_ELECTRICITY,
                                                  EndUseOptions.COGENERATION_BOTTOMING_EXTRA_ELECTRICITY,
                                                  EndUseOptions.COGENERATION_BOTTOMING_EXTRA_HEAT,
                                                  EndUseOptions.COGENERATION_PARALLEL_EXTRA_HEAT,
                                                  EndUseOptions.COGENERATION_PARALLEL_EXTRA_ELECTRICITY]:  # there is an electricity component
        summary.append(OutputTableItem('Average Net Electricity Production', '{0:10.2f}'.format(
            np.average(model.surfaceplant.NetElectricityProduced.value)),
                                       model.surfaceplant.NetElectricityProduced.CurrentUnits.value))
    if model.surfaceplant.enduse_option.value is not EndUseOptions.ELECTRICITY:  # there is a direct-use component
        summary.append(OutputTableItem('Average Direct-Use Heat Production',
                                       '{0:10.2f}'.format(np.average(model.surfaceplant.HeatProduced.value)),
                                       model.surfaceplant.HeatProduced.CurrentUnits.value))
    if model.surfaceplant.plant_type.value == PlantType.DISTRICT_HEATING:
        summary.append(OutputTableItem('Annual District Heating Demand', '{0:10.2f}'.format(
            np.average(model.surfaceplant.annual_heating_demand.value)),
                                       model.surfaceplant.annual_heating_demand.CurrentUnits.value))
        summary.append(OutputTableItem('Average Annual Geothermal Heat Production', '{0:10.2f}'.format(
            sum(model.surfaceplant.dh_geothermal_heating.value * 24) / model.surfaceplant.plant_lifetime.value / 1e3),
                                       model.surfaceplant.annual_heating_demand.CurrentUnits.value))
        summary.append(OutputTableItem('Average Annual Peaking Fuel Heat Production', '{0:10.2f}'.format(
            sum(model.surfaceplant.dh_natural_gas_heating.value * 24) / model.surfaceplant.plant_lifetime.value / 1e3),
                                       model.surfaceplant.annual_heating_demand.CurrentUnits.value))
    if model.surfaceplant.plant_type.value == PlantType.ABSORPTION_CHILLER:
        summary.append(OutputTableItem('Average Cooling Production',
                                       '{0:10.2f}'.format(np.average(model.surfaceplant.cooling_produced.value)),
                                       model.surfaceplant.cooling_produced.CurrentUnits.value))

    if model.surfaceplant.enduse_option.value in [EndUseOptions.ELECTRICITY]:
        summary.append(
            OutputTableItem('Electricity breakeven price', '{0:10.2f}'.format(model.economics.LCOE.value),
                            model.economics.LCOE.CurrentUnits.value))
    elif model.surfaceplant.enduse_option.value in [EndUseOptions.HEAT] and model.surfaceplant.plant_type.value not in [PlantType.ABSORPTION_CHILLER]:
        summary.append(OutputTableItem('Direct-Use heat breakeven price (LCOH)',
                                       '{0:10.2f}'.format(model.economics.LCOH.value),
                                       model.economics.LCOH.CurrentUnits.value))
    elif (model.surfaceplant.enduse_option.value in [EndUseOptions.HEAT] and
          model.surfaceplant.plant_type.value == PlantType.ABSORPTION_CHILLER):
        summary.append(OutputTableItem('Direct-Use Cooling Breakeven Price (LCOC)',
                                       '{0:10.2f}'.format(model.economics.LCOC.value),
                                       model.economics.LCOC.CurrentUnits.value))
    elif model.surfaceplant.enduse_option.value in [EndUseOptions.COGENERATION_TOPPING_EXTRA_HEAT,
                                                    EndUseOptions.COGENERATION_BOTTOMING_EXTRA_HEAT,
                                                    EndUseOptions.COGENERATION_PARALLEL_EXTRA_HEAT,
                                                    EndUseOptions.COGENERATION_TOPPING_EXTRA_ELECTRICITY,
                                                    EndUseOptions.COGENERATION_BOTTOMING_EXTRA_ELECTRICITY,
                                                    EndUseOptions.COGENERATION_PARALLEL_EXTRA_ELECTRICITY]:
        summary.append(
            OutputTableItem('Electricity breakeven price', '{0:10.2f}'.format(model.economics.LCOE.value),
                            model.economics.LCOE.CurrentUnits.value))
        summary.append(OutputTableItem('Direct-Use heat breakeven price (LCOH)',
                                       '{0:10.2f}'.format(model.economics.LCOH.value),
                                       model.economics.LCOH.CurrentUnits.value))

    summary.append(OutputTableItem('Number of production wells', '{0:10.0f}'.format(model.wellbores.nprod.value)))
    summary.append(OutputTableItem('Number of injection wells', '{0:10.0f}'.format(model.wellbores.ninj.value)))
    summary.append(
        OutputTableItem('Flowrate per production well', '{0:10.1f}'.format(model.wellbores.prodwellflowrate.value),
                        model.wellbores.prodwellflowrate.CurrentUnits.value))
    summary.append(OutputTableItem(VERTICAL_WELL_DEPTH_OUTPUT_NAME,
                                   '{0:10.1f}'.format(model.reserv.depth.value),
                                   model.reserv.depth.CurrentUnits.value))

    if model.reserv.numseg.value == 1:
        summary.append(OutputTableItem('Geothermal gradient', '{0:10.4g}'.format(model.reserv.gradient.value[0]),
                                       model.reserv.gradient.CurrentUnits.value))
    else:
        for i in range(1, model.reserv.numseg.value):
            summary.append(OutputTableItem(f'Segment {str(i)} Geothermal gradient',
                                           '{0:10.4g}'.format(model.reserv.gradient.value[i - 1]),
                                           model.reserv.gradient.CurrentUnits.value))
            summary.append(OutputTableItem(f'Segment {str(i)} Thickness',
                                           '{0:10.0f}'.format(model.reserv.layerthickness.value[i - 1]),
                                           model.reserv.layerthickness.CurrentUnits.value))
        summary.append(OutputTableItem(f'Segment {str(i + 1)} Geothermal gradient',
                                       '{0:10.4g}'.format(model.reserv.gradient.value[i]),
                                       model.reserv.gradient.CurrentUnits.value))

    if model.economics.DoCarbonCalculations.value:
        summary.append(OutputTableItem('Total Avoided Carbon Emissions', '{0:10.2f}'.format(
            model.economics.CarbonThatWouldHaveBeenProducedTotal.value),
                                       model.economics.CarbonThatWouldHaveBeenProducedTotal.CurrentUnits.value))

    if model.economics.econmodel.value == EconomicModel.FCR:
        economic_parameters.append(OutputTableItem('Economic Model', model.economics.econmodel.value.value))
        economic_parameters.append(
            OutputTableItem('Fixed Charge Rate (FCR)', '{0:10.2f}'.format(model.economics.FCR.value * 100.0),
                            model.economics.FCR.CurrentUnits.value))
    elif model.economics.econmodel.value == EconomicModel.STANDARDIZED_LEVELIZED_COST:
        economic_parameters.append(OutputTableItem('Economic Model', model.economics.econmodel.value.value))
        economic_parameters.append(
            OutputTableItem('Interest Rate', '{0:10.2f}'.format(model.economics.discountrate.value * 100.0),
                            model.economics.discountrate.CurrentUnits.value))
    elif model.economics.econmodel.value == EconomicModel.BICYCLE:
        economic_parameters.append(OutputTableItem('Economic Model', model.economics.econmodel.value.value))
    economic_parameters.append(OutputTableItem('Accrued financing during construction',
                                               '{0:10.2f}'.format(model.economics.inflrateconstruction.value * 100),
                                               model.economics.inflrateconstruction.CurrentUnits.value))
    economic_parameters.append(
        OutputTableItem('Project lifetime', '{0:10.0f}'.format(model.surfaceplant.plant_lifetime.value),
                        model.surfaceplant.plant_lifetime.CurrentUnits.value))
    economic_parameters.append(
        OutputTableItem('Capacity factor', '{0:10.1f}'.format(model.surfaceplant.utilization_factor.value * 100),
                        '%'))
    economic_parameters.append(OutputTableItem('Project NPV', '{0:10.2f}'.format(model.economics.ProjectNPV.value),
                                               model.economics.ProjectNPV.PreferredUnits.value))
    economic_parameters.append(OutputTableItem('Project IRR', '{0:10.2f}'.format(model.economics.ProjectIRR.value),
                                               model.economics.ProjectIRR.PreferredUnits.value))
    economic_parameters.append(
        OutputTableItem('Project VIR=PI=PIR', '{0:10.2f}'.format(model.economics.ProjectVIR.value)))
    economic_parameters.append(
        OutputTableItem('Project MOIC', '{0:10.2f}'.format(model.economics.ProjectMOIC.value)))

    payback_period_val = model.economics.ProjectPaybackPeriod.value
    project_payback_period_display = f'{payback_period_val:10.2f} {model.economics.ProjectPaybackPeriod.PreferredUnits.value}' \
        if payback_period_val > 0.0 else 'N/A'
    economic_parameters.append(OutputTableItem('Project Payback Period', project_payback_period_display))

    if model.surfaceplant.enduse_option.value in [EndUseOptions.COGENERATION_TOPPING_EXTRA_HEAT,
                                                  EndUseOptions.COGENERATION_BOTTOMING_EXTRA_HEAT,
                                                  EndUseOptions.COGENERATION_PARALLEL_EXTRA_HEAT,
                                                  EndUseOptions.COGENERATION_TOPPING_EXTRA_ELECTRICITY,
                                                  EndUseOptions.COGENERATION_BOTTOMING_EXTRA_ELECTRICITY,
                                                  EndUseOptions.COGENERATION_PARALLEL_EXTRA_ELECTRICITY]:
        economic_parameters.append(OutputTableItem('CHP: Percent cost allocation for electrical plant',
                                                   '{0:10.2f}'.format(
                                                       model.economics.CAPEX_heat_electricity_plant_ratio.value * 100.0),
                                                   '%'))

    engineering_parameters.append(
        OutputTableItem('Number of Production Wells', '{0:10.0f}'.format(model.wellbores.nprod.value)))
    engineering_parameters.append(
        OutputTableItem('Number of Injection Wells', '{0:10.0f}'.format(model.wellbores.ninj.value)))
    engineering_parameters.append(OutputTableItem(VERTICAL_WELL_DEPTH_OUTPUT_NAME,
                                                  '{0:10.1f}'.format(model.reserv.depth.value),
                                                  model.reserv.depth.CurrentUnits.value))
    engineering_parameters.append(
        OutputTableItem('Water loss rate', '{0:10.1f}'.format(model.reserv.waterloss.value * 100),
                        model.reserv.waterloss.CurrentUnits.value))
    engineering_parameters.append(
        OutputTableItem('Pump efficiency', '{0:10.1f}'.format(model.surfaceplant.pump_efficiency.value * 100),
                        model.surfaceplant.pump_efficiency.CurrentUnits.value))
    engineering_parameters.append(
        OutputTableItem('Injection temperature', '{0:10.1f}'.format(model.wellbores.Tinj.value),
                        model.wellbores.Tinj.CurrentUnits.value))
    if model.wellbores.rameyoptionprod.value:
        engineering_parameters.append(
            OutputTableItem('Production Wellbore heat transmission calculated with Rameys model'))
        engineering_parameters.append(OutputTableItem('Average production well temperature drop',
                                                      '{0:10.1f}'.format(
                                                          np.average(model.wellbores.ProdTempDrop.value)),
                                                      model.wellbores.ProdTempDrop.PreferredUnits.value))
    else:
        engineering_parameters.append(OutputTableItem('User-provided production well temperature drop'))
        engineering_parameters.append(OutputTableItem('Constant production well temperature drop',
                                                      '{0:10.1f}'.format(model.wellbores.tempdropprod.value),
                                                      model.wellbores.tempdropprod.PreferredUnits.value))
    engineering_parameters.append(
        OutputTableItem('Flowrate per production well', '{0:10.1f}'.format(model.wellbores.prodwellflowrate.value),
                        model.wellbores.prodwellflowrate.CurrentUnits.value))
    engineering_parameters.append(
        OutputTableItem('Injection well casing ID', '{0:10.3f}'.format(model.wellbores.injwelldiam.value),
                        model.wellbores.injwelldiam.CurrentUnits.value))
    engineering_parameters.append(
        OutputTableItem('Production well casing ID', '{0:10.3f}'.format(model.wellbores.prodwelldiam.value),
                        model.wellbores.prodwelldiam.CurrentUnits.value))
    engineering_parameters.append(
        OutputTableItem('Number of times redrilling', '{0:10.0f}'.format(model.wellbores.redrill.value)))
    if model.surfaceplant.enduse_option.value in [EndUseOptions.ELECTRICITY,
                                                  EndUseOptions.COGENERATION_TOPPING_EXTRA_HEAT,
                                                  EndUseOptions.COGENERATION_TOPPING_EXTRA_ELECTRICITY,
                                                  EndUseOptions.COGENERATION_BOTTOMING_EXTRA_ELECTRICITY,
                                                  EndUseOptions.COGENERATION_BOTTOMING_EXTRA_HEAT,
                                                  EndUseOptions.COGENERATION_PARALLEL_EXTRA_HEAT,
                                                  EndUseOptions.COGENERATION_PARALLEL_EXTRA_ELECTRICITY]:
        engineering_parameters.append(
            OutputTableItem('Power plant type', model.surfaceplant.plant_type.value.value))

        resource_characteristics.append(
            OutputTableItem('Maximum reservoir temperature', '{0:10.1f}'.format(model.reserv.Tmax.value),
                            model.reserv.Tmax.CurrentUnits.value))
        resource_characteristics.append(
            OutputTableItem('Number of segments', '{0:10.0f}'.format(model.reserv.numseg.value)))
        if model.reserv.numseg.value == 1:
            resource_characteristics.append(
                OutputTableItem('Geothermal gradient', '{0:10.4g}'.format(model.reserv.gradient.value[0]),
                                model.reserv.gradient.CurrentUnits.value))
        else:
            for i in range(1, model.reserv.numseg.value):
                resource_characteristics.append(OutputTableItem(f'Segment {str(i)} Geothermal gradient',
                                                                '{0:10.4g}'.format(
                                                                    model.reserv.gradient.value[i - 1]),
                                                                model.reserv.gradient.CurrentUnits.value))
                resource_characteristics.append(OutputTableItem(f'Segment {str(i)} Thickness', '{0:10.0f}'.format(
                    model.reserv.layerthickness.value[i - 1]), model.reserv.layerthickness.CurrentUnits.value))
            resource_characteristics.append(OutputTableItem(f'Segment {str(i + 1)} Geothermal gradient',
                                                            '{0:10.4g}'.format(model.reserv.gradient.value[i]),
                                                            model.reserv.gradient.CurrentUnits.value))
    if model.wellbores.IsAGS.value:
        reservoir_parameters.append(
            OutputTableItem('The AGS models contain an intrinsic reservoir model that doesn\'t expose values that can be used in extensive reporting.'))
    else:
        reservoir_parameters.append(
            OutputTableItem('Reservoir Model', str(model.reserv.resoption.value.value) + ' Model'))
        if model.reserv.resoption.value is ReservoirModel.SINGLE_FRACTURE:
            reservoir_parameters.append(
                OutputTableItem('m/A Drawdown Parameter', '{0:.5f}'.format(model.reserv.drawdp.value),
                                model.reserv.drawdp.CurrentUnits.value))
        elif model.reserv.resoption.value is ReservoirModel.ANNUAL_PERCENTAGE:
            reservoir_parameters.append(
                OutputTableItem('Annual Thermal Drawdown', '{0:.3f}'.format(model.reserv.drawdp.value * 100),
                                model.reserv.drawdp.CurrentUnits.value))
        reservoir_parameters.append(
            OutputTableItem('Bottom-hole temperature', '{0:10.2f}'.format(model.reserv.Trock.value),
                            model.reserv.Trock.CurrentUnits.value))
        if model.reserv.resoption.value in [ReservoirModel.ANNUAL_PERCENTAGE, ReservoirModel.USER_PROVIDED_PROFILE,
                                            ReservoirModel.TOUGH2_SIMULATOR]:
            reservoir_parameters.append(
                OutputTableItem('Warning: the reservoir dimensions and thermo-physical properties'))
            reservoir_parameters.append(
                OutputTableItem('listed below are default values if not provided by the user.'))
            reservoir_parameters.append(
                OutputTableItem('They are only used for calculating remaining heat content.'))

        if model.reserv.resoption.value in [ReservoirModel.MULTIPLE_PARALLEL_FRACTURES,
                                            ReservoirModel.LINEAR_HEAT_SWEEP]:
            reservoir_parameters.append(OutputTableItem('Fracture model', model.reserv.fracshape.value.value))
            if model.reserv.fracshape.value == FractureShape.CIRCULAR_AREA:
                reservoir_parameters.append(OutputTableItem('Well separation: fracture diameter',
                                                            '{0:10.2f}'.format(model.reserv.fracheightcalc.value),
                                                            model.reserv.fracheight.CurrentUnits.value))
            elif model.reserv.fracshape.value == FractureShape.CIRCULAR_DIAMETER:
                reservoir_parameters.append(OutputTableItem('Well separation: fracture diameter',
                                                            '{0:10.2f}'.format(model.reserv.fracheightcalc.value),
                                                            model.reserv.fracheight.CurrentUnits.value))
            elif model.reserv.fracshape.value == FractureShape.SQUARE:
                reservoir_parameters.append(OutputTableItem('Well separation: fracture height',
                                                            '{0:10.2f}'.format(model.reserv.fracheightcalc.value),
                                                            model.reserv.fracheight.CurrentUnits.value))
            elif model.reserv.fracshape.value == FractureShape.RECTANGULAR:
                reservoir_parameters.append(OutputTableItem('Well separation: fracture height',
                                                            '{0:10.2f}'.format(model.reserv.fracheightcalc.value),
                                                            model.reserv.fracheight.CurrentUnits.value))
                reservoir_parameters.append(
                    OutputTableItem('Fracture width', '{0:10.2f}'.format(model.reserv.fracwidthcalc.value),
                                    model.reserv.fracwidth.CurrentUnits.value))
            reservoir_parameters.append(
                OutputTableItem('Fracture area', '{0:10.2f}'.format(model.reserv.fracareacalc.value),
                                model.reserv.fracarea.CurrentUnits.value))
        if model.reserv.resvoloption.value == ReservoirVolume.FRAC_NUM_SEP:
            reservoir_parameters.append(
                OutputTableItem('Reservoir volume calculated with fracture separation and number of fractures as input'))
        elif model.reserv.resvoloption.value == ReservoirVolume.RES_VOL_FRAC_SEP:
            reservoir_parameters.append(
                OutputTableItem('Number of fractures calculated with reservoir volume and fracture separation as input'))
        elif model.reserv.resvoloption.value == ReservoirVolume.FRAC_NUM_SEP:
            reservoir_parameters.append(
                OutputTableItem('Fracture separation calculated with reservoir volume and number of fractures as input'))
        elif model.reserv.resvoloption.value == ReservoirVolume.RES_VOL_ONLY:
            reservoir_parameters.append(OutputTableItem('Reservoir volume provided as input'))
        if model.reserv.resvoloption.value in [ReservoirVolume.FRAC_NUM_SEP, ReservoirVolume.RES_VOL_FRAC_SEP,
                                               ReservoirVolume.FRAC_NUM_SEP]:
            reservoir_parameters.append(
                OutputTableItem('Number of fractures', '{0:10.2f}'.format(model.reserv.fracnumbcalc.value)))
            reservoir_parameters.append(
                OutputTableItem('Fracture separation', '{0:10.2f}'.format(model.reserv.fracsepcalc.value),
                                model.reserv.fracsep.CurrentUnits.value))
        reservoir_parameters.append(
            OutputTableItem('Reservoir volume', '{0:10.0f}'.format(model.reserv.resvolcalc.value),
                            model.reserv.resvol.CurrentUnits.value))
        if model.wellbores.impedancemodelused.value:
            reservoir_parameters.append(
                OutputTableItem('Reservoir impedance', '{0:10.2f}'.format(model.wellbores.impedance.value / 1000),
                                model.wellbores.impedance.CurrentUnits.value))
        else:
            reservoir_parameters.append(OutputTableItem('Average reservoir pressure',
                                                        '{0:10.2f}'.format(model.wellbores.average_production_reservoir_pressure.value),
                                                        model.wellbores.average_production_reservoir_pressure.CurrentUnits.value))
            reservoir_parameters.append(OutputTableItem('Plant outlet pressure', '{0:10.2f}'.format(
                model.surfaceplant.plant_outlet_pressure.value),
                                                        model.surfaceplant.plant_outlet_pressure.CurrentUnits.value))
            if model.wellbores.productionwellpumping.value:
                reservoir_parameters.append(OutputTableItem('Production wellhead pressure',
                                                            '{0:10.2f}'.format(model.wellbores.Pprodwellhead.value),
                                                            model.wellbores.Pprodwellhead.CurrentUnits.value))
                reservoir_parameters.append(
                    OutputTableItem('Productivity Index', '{0:10.2f}'.format(model.wellbores.PI.value),
                                    model.wellbores.PI.CurrentUnits.value))
            reservoir_parameters.append(
                OutputTableItem('Injectivity Index', '{0:10.2f}'.format(model.wellbores.II.value),
                                model.wellbores.II.CurrentUnits.value))
        reservoir_parameters.append(
            OutputTableItem('Reservoir density', '{0:10.2f}'.format(model.reserv.rhorock.value),
                            model.reserv.rhorock.CurrentUnits.value))
        if model.wellbores.rameyoptionprod.value or model.reserv.resoption.value in [
            ReservoirModel.MULTIPLE_PARALLEL_FRACTURES, ReservoirModel.LINEAR_HEAT_SWEEP,
            ReservoirModel.SINGLE_FRACTURE, ReservoirModel.TOUGH2_SIMULATOR]:
            reservoir_parameters.append(
                OutputTableItem('Reservoir thermal conductivity', '{0:10.2f}'.format(model.reserv.krock.value),
                                model.reserv.krock.CurrentUnits.value))
        reservoir_parameters.append(
            OutputTableItem('Reservoir heat capacity', '{0:10.2f}'.format(model.reserv.cprock.value),
                            model.reserv.cprock.CurrentUnits.value))
        if model.reserv.resoption.value is ReservoirModel.LINEAR_HEAT_SWEEP or (
            model.reserv.resoption.value is ReservoirModel.TOUGH2_SIMULATOR and model.reserv.usebuiltintough2model):
            reservoir_parameters.append(
                OutputTableItem('Reservoir porosity', '{0:10.2f}'.format(model.reserv.porrock.value * 100),
                                model.reserv.porrock.CurrentUnits.value))
        if model.reserv.resoption.value is ReservoirModel.TOUGH2_SIMULATOR and model.reserv.usebuiltintough2model:
            reservoir_parameters.append(
                OutputTableItem('Reservoir permeability', '{0:10.2E}'.format(model.reserv.permrock.value),
                                model.reserv.permrock.CurrentUnits.value))
            reservoir_parameters.append(
                OutputTableItem('Reservoir thickness', '{0:10.2f}'.format(model.reserv.resthickness.value),
                                model.reserv.resthickness.CurrentUnits.value))
            reservoir_parameters.append(
                OutputTableItem('Reservoir width', '{0:10.2f}'.format(model.reserv.reswidth.value),
                                model.reserv.reswidth.CurrentUnits.value))
            reservoir_parameters.append(
                OutputTableItem('Well separation', '{0:10.2f}'.format(model.wellbores.wellsep.value),
                                model.wellbores.wellsep.CurrentUnits.value))

    reservoir_stimulation_results.append(OutputTableItem('Maximum Production Temperature', '{0:10.1f}'.format(
        np.max(model.wellbores.ProducedTemperature.value)), model.wellbores.ProducedTemperature.PreferredUnits.value))
    reservoir_stimulation_results.append(OutputTableItem('Average Production Temperature', '{0:10.1f}'.format(
        np.average(model.wellbores.ProducedTemperature.value)), model.wellbores.ProducedTemperature.PreferredUnits.value))
    reservoir_stimulation_results.append(OutputTableItem('Minimum Production Temperature', '{0:10.1f}'.format(
        np.min(model.wellbores.ProducedTemperature.value)), model.wellbores.ProducedTemperature.PreferredUnits.value))
    reservoir_stimulation_results.append(OutputTableItem('Initial Production Temperature', '{0:10.1f}'.format(
        model.wellbores.ProducedTemperature.value[0]), model.wellbores.ProducedTemperature.PreferredUnits.value))
    if model.wellbores.IsAGS.value:
        reservoir_stimulation_results.append(
            OutputTableItem('The AGS models contain an intrinsic reservoir model that doesn\'t expose values that can be used in extensive reporting.'))
    else:
        reservoir_stimulation_results.append(OutputTableItem('Average Reservoir Heat Extraction',
                                                             '{0:10.2f}'.format(np.average(
                                                                 model.surfaceplant.HeatExtracted.value)),
                                                             model.surfaceplant.HeatExtracted.PreferredUnits.value))
        if model.wellbores.rameyoptionprod.value:
            reservoir_stimulation_results.append(
                OutputTableItem('Production Wellbore Heat Transmission Model', 'Ramey Model'))
            reservoir_stimulation_results.append(OutputTableItem('Average Production Well Temperature Drop',
                                                                 '{0:10.1f}'.format(np.average(
                                                                     model.wellbores.ProdTempDrop.value)),
                                                                 model.wellbores.ProdTempDrop.PreferredUnits.value))
        else:
            reservoir_stimulation_results.append(
                OutputTableItem('Wellbore Heat Transmission Model = Constant Temperature Drop',
                                '{0:10.1f}'.format(model.wellbores.tempdropprod.value),
                                model.wellbores.tempdropprod.PreferredUnits.value))
        if model.wellbores.impedancemodelused.value:
            reservoir_stimulation_results.append(OutputTableItem('Total Average Pressure Drop', '{0:10.1f}'.format(
                np.average(model.wellbores.DPOverall.value)), model.wellbores.DPOverall.PreferredUnits.value))
            reservoir_stimulation_results.append(OutputTableItem('Average Injection Well Pressure Drop',
                                                                 '{0:10.1f}'.format(
                                                                     np.average(model.wellbores.DPInjWell.value)),
                                                                 model.wellbores.DPInjWell.PreferredUnits.value))
            reservoir_stimulation_results.append(OutputTableItem('Average Reservoir Pressure Drop',
                                                                 '{0:10.1f}'.format(
                                                                     np.average(model.wellbores.DPReserv.value)),
                                                                 model.wellbores.DPReserv.PreferredUnits.value))
            reservoir_stimulation_results.append(OutputTableItem('Average Production Well Pressure Drop',
                                                                 '{0:10.1f}'.format(
                                                                     np.average(model.wellbores.DPProdWell.value)),
                                                                 model.wellbores.DPProdWell.PreferredUnits.value))
            reservoir_stimulation_results.append(OutputTableItem('Average Buoyancy Pressure Drop',
                                                                 '{0:10.1f}'.format(
                                                                     np.average(model.wellbores.DPBouyancy.value)),
                                                                 model.wellbores.DPBouyancy.PreferredUnits.value))
        else:
            reservoir_stimulation_results.append(OutputTableItem('Average Injection Well Pump Pressure Drop',
                                                                 '{0:10.1f}'.format(
                                                                     np.average(model.wellbores.DPInjWell.value)),
                                                                 model.wellbores.DPInjWell.PreferredUnits.value))
            if model.wellbores.productionwellpumping.value:
                reservoir_stimulation_results.append(OutputTableItem('Average Production Well Pump Pressure Drop',
                                                                     '{0:10.1f}'.format(np.average(
                                                                         model.wellbores.DPProdWell.value)),
                                                                     model.wellbores.DPProdWell.PreferredUnits.value))
    if not model.economics.totalcapcost.Valid:
        CAPEX.append(
            OutputTableItem('Drilling and completion costs', '{0:10.2f}'.format(model.economics.Cwell.value),
                            model.economics.Cwell.CurrentUnits.value))

        if model.economics.cost_one_production_well.value != model.economics.cost_one_injection_well.value and \
            model.economics.cost_one_injection_well.value != -1:
            CAPEX.append(OutputTableItem('Drilling and completion costs per production well',
                                         '{0:10.2f}'.format(model.economics.cost_one_production_well.value,
                                          model.economics.cost_one_production_well.CurrentUnits.value)))
            CAPEX.append(OutputTableItem('Drilling and completion costs per injection well, '
                                         '{0:10.2f}'.format(model.economics.cost_one_injection_well.value,
                                         model.economics.cost_one_injection_well.CurrentUnits.value)))
        else:
            CAPEX.append(OutputTableItem('Drilling and completion costs per well', '{0:10.2f}'.format(
                model.economics.Cwell.value / (model.wellbores.nprod.value + model.wellbores.ninj.value)),
                                         model.economics.Cwell.CurrentUnits.value))
        CAPEX.append(OutputTableItem('Stimulation costs', '{0:10.2f}'.format(model.economics.Cstim.value),
                                     model.economics.Cstim.CurrentUnits.value))
        CAPEX.append(OutputTableItem('Surface power plant costs', '{0:10.2f}'.format(model.economics.Cplant.value),
                                     model.economics.Cplant.CurrentUnits.value))
        if model.surfaceplant.plant_type.value == PlantType.ABSORPTION_CHILLER:
            CAPEX.append(
                OutputTableItem('Absorption Chiller Cost', '{0:10.2f}'.format(model.economics.chillercapex.value),
                                model.economics.Cplant.CurrentUnits.value))
        if model.surfaceplant.plant_type.value == PlantType.HEAT_PUMP:
            CAPEX.append(OutputTableItem('Heat Pump Cost', '{0:10.2f}'.format(model.economics.heatpumpcapex.value),
                                         model.economics.Cplant.CurrentUnits.value))
        if model.surfaceplant.plant_type.value == PlantType.DISTRICT_HEATING:
            CAPEX.append(
                OutputTableItem('Peaking Boiler Cost', '{0:10.2f}'.format(model.economics.peakingboilercost.value),
                                model.economics.peakingboilercost.CurrentUnits.value))
        CAPEX.append(
            OutputTableItem('Field gathering system costs', '{0:10.2f}'.format(model.economics.Cgath.value),
                            model.economics.Cgath.CurrentUnits.value))
        if model.surfaceplant.piping_length.value > 0:
            CAPEX.append(
                OutputTableItem('Transmission pipeline cost', '{0:10.2f}'.format(model.economics.Cpiping.value),
                                model.economics.Cpiping.CurrentUnits.value))
        if model.surfaceplant.plant_type.value == PlantType.DISTRICT_HEATING:
            CAPEX.append(OutputTableItem('District Heating System Cost',
                                         '{0:10.2f}'.format(model.economics.dhdistrictcost.value),
                                         model.economics.dhdistrictcost.CurrentUnits.value))
        CAPEX.append(OutputTableItem('Total surface equipment costs',
                                     '{0:10.2f}'.format(model.economics.Cplant.value + model.economics.Cgath.value),
                                     model.economics.Cplant.CurrentUnits.value))
        CAPEX.append(OutputTableItem('Exploration costs', '{0:10.2f}'.format(model.economics.Cexpl.value),
                                     model.economics.Cexpl.CurrentUnits.value))
    if model.economics.totalcapcost.Valid and model.wellbores.redrill.value > 0:
        CAPEX.append(OutputTableItem('Drilling and completion costs (for redrilling)',
                                     '{0:10.2f}'.format(model.economics.Cwell.value),
                                     model.economics.Cwell.CurrentUnits.value))
        CAPEX.append(OutputTableItem('Drilling and completion costs per redrilled well', '{0:10.2f}'.format(
            model.economics.Cwell.value / (model.wellbores.nprod.value + model.wellbores.ninj.value)),
                                     model.economics.Cwell.CurrentUnits.value))
        CAPEX.append(
            OutputTableItem('Stimulation costs (for redrilling)', '{0:10.2f}'.format(model.economics.Cstim.value),
                            model.economics.Cstim.CurrentUnits.value))
    if model.economics.RITC.Provided:
        CAPEX.append(
            OutputTableItem('Investment tax Credit', '{0:10.2f}'.format(-1 * model.economics.RITCValue.value),
                            model.economics.RITCValue.CurrentUnits.value))
    CAPEX.append(OutputTableItem('Total capital costs', '{0:10.2f}'.format(model.economics.CCap.value),
                                 model.economics.CCap.CurrentUnits.value))
    if model.economics.econmodel.value == EconomicModel.FCR:
        CAPEX.append(OutputTableItem('Annualized capital costs', '{0:10.2f}'.format(model.economics.CCap.value * (
                1 + model.economics.inflrateconstruction.value) * model.economics.FCR.value),
                                     model.economics.CCap.CurrentUnits.value))

    if not model.economics.oamtotalfixed.Valid:
        OPEX.append(
            OutputTableItem('Wellfield maintenance costs', '{0:10.2f}'.format(model.economics.Coamwell.value),
                            model.economics.Coamwell.CurrentUnits.value))
        OPEX.append(
            OutputTableItem('Power plant maintenance costs', '{0:10.2f}'.format(model.economics.Coamplant.value),
                            model.economics.Coamplant.CurrentUnits.value))
        OPEX.append(OutputTableItem('Water costs', '{0:10.2f}'.format(model.economics.Coamwater.value),
                                    model.economics.Coamwater.CurrentUnits.value))
        if model.surfaceplant.plant_type.value in [PlantType.INDUSTRIAL, PlantType.ABSORPTION_CHILLER,
                                                   PlantType.HEAT_PUMP, PlantType.DISTRICT_HEATING]:
            OPEX.append(OutputTableItem('Average Reservoir Pumping Cost',
                                        '{0:10.2f}'.format(model.economics.averageannualpumpingcosts.value),
                                        model.economics.averageannualpumpingcosts.CurrentUnits.value))
        if model.surfaceplant.plant_type.value == PlantType.ABSORPTION_CHILLER:
            OPEX.append(OutputTableItem('Absorption Chiller O&M Cost',
                                        '{0:10.2f}'.format(model.economics.chilleropex.value),
                                        model.economics.chilleropex.CurrentUnits.value))
        if model.surfaceplant.plant_type.value == PlantType.HEAT_PUMP:
            OPEX.append(OutputTableItem('Average Heat Pump Electricity Cost', '{0:10.2f}'.format(
                model.economics.averageannualheatpumpelectricitycost.value),
                                        model.economics.averageannualheatpumpelectricitycost.CurrentUnits.value))
        if model.surfaceplant.plant_type.value == PlantType.DISTRICT_HEATING:
            OPEX.append(OutputTableItem('Annual District Heating O&M Cost',
                                        '{0:10.2f}'.format(model.economics.dhdistrictoandmcost.value),
                                        model.economics.dhdistrictoandmcost.CurrentUnits.value))
            OPEX.append(OutputTableItem('Average Annual Peaking Fuel Cost',
                                        '{0:10.2f}'.format(model.economics.averageannualngcost.value),
                                        model.economics.averageannualngcost.CurrentUnits.value))
        OPEX.append(OutputTableItem('Total operating and maintenance costs', '{0:10.2f}'.format(
            model.economics.Coam.value + model.economics.averageannualpumpingcosts.value + model.economics.averageannualheatpumpelectricitycost.value),
                                    model.economics.Coam.CurrentUnits.value))
    else:
        OPEX.append(
            OutputTableItem('Total operating and maintenance costs', '{0:10.2f}'.format(model.economics.Coam.value),
                            model.economics.Coam.CurrentUnits.value))

    if model.surfaceplant.enduse_option.value in [EndUseOptions.ELECTRICITY,
                                                  EndUseOptions.COGENERATION_TOPPING_EXTRA_HEAT,
                                                  EndUseOptions.COGENERATION_TOPPING_EXTRA_ELECTRICITY,
                                                  EndUseOptions.COGENERATION_BOTTOMING_EXTRA_ELECTRICITY,
                                                  EndUseOptions.COGENERATION_BOTTOMING_EXTRA_HEAT,
                                                  EndUseOptions.COGENERATION_PARALLEL_EXTRA_HEAT,
                                                  EndUseOptions.COGENERATION_PARALLEL_EXTRA_ELECTRICITY]:  # there is an electricity componenent:
        surface_equipment_results.append(OutputTableItem('Initial geofluid availability', '{0:10.2f}'.format(
            model.surfaceplant.Availability.value[0]), model.surfaceplant.Availability.PreferredUnits.value))
        surface_equipment_results.append(OutputTableItem('Maximum Total Electricity Generation', '{0:10.2f}'.format(
            np.max(model.surfaceplant.ElectricityProduced.value)), model.surfaceplant.ElectricityProduced.PreferredUnits.value))
        surface_equipment_results.append(OutputTableItem('Average Total Electricity Generation', '{0:10.2f}'.format(
            np.average(model.surfaceplant.ElectricityProduced.value)), model.surfaceplant.ElectricityProduced.PreferredUnits.value))
        surface_equipment_results.append(OutputTableItem('Minimum Total Electricity Generation', '{0:10.2f}'.format(
            np.min(model.surfaceplant.ElectricityProduced.value)), model.surfaceplant.ElectricityProduced.PreferredUnits.value))
        surface_equipment_results.append(OutputTableItem('Initial Total Electricity Generation', '{0:10.2f}'.format(
            model.surfaceplant.ElectricityProduced.value[0]), model.surfaceplant.ElectricityProduced.PreferredUnits.value))
        surface_equipment_results.append(OutputTableItem('Maximum Net Electricity Generation', '{0:10.2f}'.format(
            np.max(model.surfaceplant.NetElectricityProduced.value)), model.surfaceplant.NetElectricityProduced.PreferredUnits.value))
        surface_equipment_results.append(OutputTableItem('Average Net Electricity Generation', '{0:10.2f}'.format(
            np.average(model.surfaceplant.NetElectricityProduced.value)), model.surfaceplant.NetElectricityProduced.PreferredUnits.value))
        surface_equipment_results.append(OutputTableItem('Minimum Net Electricity Generation', '{0:10.2f}'.format(
            np.min(model.surfaceplant.NetElectricityProduced.value)), model.surfaceplant.NetElectricityProduced.PreferredUnits.value))
        surface_equipment_results.append(OutputTableItem('Initial Net Electricity Generation', '{0:10.2f}'.format(
            model.surfaceplant.NetElectricityProduced.value[0]), model.surfaceplant.NetElectricityProduced.PreferredUnits.value))
        surface_equipment_results.append(OutputTableItem('Average Annual Total Electricity Generation',
                                                         f'{0:10.2f}'.format(np.average(model.surfaceplant.TotalkWhProduced.value / 1E6)),
                                                         f'GWh'))
        surface_equipment_results.append(OutputTableItem('Average Annual Net Electricity Generation',
                                                         f'{0:10.2f}'.format(np.average(model.surfaceplant.NetkWhProduced.value / 1E6)),
                                                         f'GWh'))

        if model.wellbores.PumpingPower.value[0] > 0.0:
            ipp_nip = model.wellbores.PumpingPower.value[0] / model.surfaceplant.NetElectricityProduced.value[0]
            surface_equipment_results.append(
                OutputTableItem('Initial pumping power/net installed power', '{0:10.2f}'.format(ipp_nip * 100),
                                '%'))

    if model.surfaceplant.enduse_option.value in [EndUseOptions.HEAT, PlantType.ABSORPTION_CHILLER,
                                                  PlantType.HEAT_PUMP,
                                                  EndUseOptions.COGENERATION_TOPPING_EXTRA_HEAT,
                                                  EndUseOptions.COGENERATION_TOPPING_EXTRA_ELECTRICITY,
                                                  EndUseOptions.COGENERATION_BOTTOMING_EXTRA_ELECTRICITY,
                                                  EndUseOptions.COGENERATION_BOTTOMING_EXTRA_HEAT,
                                                  EndUseOptions.COGENERATION_PARALLEL_EXTRA_HEAT,
                                                  EndUseOptions.COGENERATION_PARALLEL_EXTRA_ELECTRICITY]:  # geothermal heating component:
        surface_equipment_results.append(OutputTableItem('Maximum Net Heat Production', '{0:10.2f}'.format(
            np.max(model.surfaceplant.HeatProduced.value)), model.surfaceplant.HeatProduced.PreferredUnits.value))
        surface_equipment_results.append(OutputTableItem('Average Net Heat Production', '{0:10.2f}'.format(
            np.average(model.surfaceplant.HeatProduced.value)), model.surfaceplant.HeatProduced.PreferredUnits.value))
        surface_equipment_results.append(OutputTableItem('Minimum Net Heat Production', '{0:10.2f}'.format(
            np.min(model.surfaceplant.HeatProduced.value)), model.surfaceplant.HeatProduced.PreferredUnits.value))
        surface_equipment_results.append(OutputTableItem('Initial Net Heat Production', '{0:10.2f}'.format(
            model.surfaceplant.HeatProduced.value[0]), model.surfaceplant.HeatProduced.PreferredUnits.value))
        surface_equipment_results.append(OutputTableItem('Average Annual Heat Production', '{0:10.2f}'.format(
            np.average(model.surfaceplant.HeatkWhProduced.value / 1E6), 'GWh')))

    if model.surfaceplant.plant_type.value == PlantType.HEAT_PUMP:
        surface_equipment_results.append(OutputTableItem('Average Annual Heat Pump Electricity Use',
                                                         '{0:10.2f}'.format(np.average(model.surfaceplant.heat_pump_electricity_kwh_used.value / 1E6),
                                                                            'GWh/year')))
    if model.surfaceplant.plant_type.value == PlantType.ABSORPTION_CHILLER:
        surface_equipment_results.append(OutputTableItem('Maximum Cooling Production', '{0:10.2f}'.format(
            np.max(model.surfaceplant.cooling_produced.value)), model.surfaceplant.cooling_produced.PreferredUnits.value))
        surface_equipment_results.append(OutputTableItem('Average Cooling Production', '{0:10.2f}'.format(
            np.average(model.surfaceplant.cooling_produced.value)),
                                                         model.surfaceplant.cooling_produced.PreferredUnits.value))
        surface_equipment_results.append(OutputTableItem('Minimum Cooling Production', '{0:10.2f}'.format(
            np.min(model.surfaceplant.cooling_produced.value)),
                                                         model.surfaceplant.cooling_produced.PreferredUnits.value))
        surface_equipment_results.append(OutputTableItem('Initial Cooling Production', '{0:10.2f}'.format(
            model.surfaceplant.cooling_produced.value[0]),
                                                         model.surfaceplant.cooling_produced.PreferredUnits.value))
        surface_equipment_results.append(OutputTableItem('Average Annual Cooling Production', '{0:10.2f}'.format(
            np.average(model.surfaceplant.cooling_kWh_Produced.value / 1E6), 'GWh/year')))

    if model.surfaceplant.plant_type.value == PlantType.DISTRICT_HEATING:
        surface_equipment_results.append(OutputTableItem('Annual District Heating Demand', '{0:10.2f}'.format(
            model.surfaceplant.annual_heating_demand.value), model.surfaceplant.annual_heating_demand.PreferredUnits.value))
        surface_equipment_results.append(OutputTableItem('Maximum Daily District Heating Demand',
                                                         '{0:10.2f}'.format(np.max(model.surfaceplant.daily_heating_demand.value)),
                                                         model.surfaceplant.daily_heating_demand.PreferredUnits.value))
        surface_equipment_results.append(OutputTableItem('Average Daily District Heating Demand',
                                                         '{0:10.2f}'.format(np.average(model.surfaceplant.daily_heating_demand.value)),
                                                         model.surfaceplant.daily_heating_demand.PreferredUnits.value))
        surface_equipment_results.append(OutputTableItem('Minimum Daily District Heating Demand',
                                                         '{0:10.2f}'.format(np.min(model.surfaceplant.daily_heating_demand.value)),
                                                         model.surfaceplant.daily_heating_demand.PreferredUnits.value))
        surface_equipment_results.append(OutputTableItem('Maximum Geothermal Heating Production',
                                                         '{0:10.2f}'.format(np.max(model.surfaceplant.dh_geothermal_heating.value)),
                                                         model.surfaceplant.dh_geothermal_heating.PreferredUnits.value))
        surface_equipment_results.append(OutputTableItem('Average Geothermal Heating Production',
                                                         '{0:10.2f}'.format(np.average(model.surfaceplant.dh_geothermal_heating.value)),
                                                         model.surfaceplant.dh_geothermal_heating.PreferredUnits.value))
        surface_equipment_results.append(OutputTableItem('Minimum Geothermal Heating Production',
                                                         '{0:10.2f}'.format(np.min(model.surfaceplant.dh_geothermal_heating.value)),
                                                         model.surfaceplant.dh_geothermal_heating.PreferredUnits.value))
        surface_equipment_results.append(OutputTableItem('Maximum Peaking Boiler Heat Production',
                                                         '{0:10.2f}'.format(np.max(model.surfaceplant.dh_natural_gas_heating.value)),
                                                         model.surfaceplant.dh_natural_gas_heating.PreferredUnits.value))
        surface_equipment_results.append(OutputTableItem('Average Peaking Boiler Heat Production',
                                                         '{0:10.2f}'.format(np.average(model.surfaceplant.dh_natural_gas_heating.value)),
                                                         model.surfaceplant.dh_natural_gas_heating.PreferredUnits.value))
        surface_equipment_results.append(OutputTableItem('Minimum Peaking Boiler Heat Production',
                                                         '{0:10.2f}'.format(np.min(model.surfaceplant.dh_natural_gas_heating.value)),
                                                         model.surfaceplant.dh_natural_gas_heating.PreferredUnits.value))
    surface_equipment_results.append(
        OutputTableItem('Average Pumping Power', '{0:10.2f}'.format(np.average(model.wellbores.PumpingPower.value)),
                        model.wellbores.PumpingPower.CurrentUnits.value))

    # Build the data frame to hold the heating, cooling, and/or electricity production profile
    hce: pd.DataFrame = pd.DataFrame()

    # add the columns as needed based on the output.
    # Note that the correct format for that column is stashed in the title of that column
    # so that it can be used in the write statement.
    hce[f'Year|:2.0f'] = [i for i in range(1, (model.surfaceplant.plant_lifetime.value + 1))]
    short_pt = ShortenArrayToAnnual(model.wellbores.ProducedTemperature.value,
                                    model.surfaceplant.plant_lifetime.value,
                                    model.economics.timestepsperyear.value)
    hce[f'Thermal Drawdown (%)|:8.4f'] = short_pt / short_pt[0]

    hce[
        f'Geofluid Temperature ({model.wellbores.ProducedTemperature.CurrentUnits.value})|:8.2f'] = ShortenArrayToAnnual(
        model.wellbores.ProducedTemperature.value,
        model.surfaceplant.plant_lifetime.value, model.economics.timestepsperyear.value)
    hce[f'Pump Power ({model.wellbores.PumpingPower.CurrentUnits.value})|:8.4f'] = ShortenArrayToAnnual(
        model.wellbores.PumpingPower.value,
        model.surfaceplant.plant_lifetime.value, model.economics.timestepsperyear.value)

    # only electricity
    if model.surfaceplant.enduse_option.value == EndUseOptions.ELECTRICITY:
        hce[
            f'Net Power ({model.surfaceplant.NetElectricityProduced.CurrentUnits.value})|:8.4f'] = ShortenArrayToAnnual(
            model.surfaceplant.NetElectricityProduced.value,
            model.surfaceplant.plant_lifetime.value, model.economics.timestepsperyear.value)
        hce[f'First Law Efficiency (%)|:8.4f'] = ShortenArrayToAnnual(
            model.surfaceplant.FirstLawEfficiency.value * 100,
            model.surfaceplant.plant_lifetime.value, model.economics.timestepsperyear.value)

    # only direct-use
    elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT and \
        model.surfaceplant.plant_type.value not in \
        [PlantType.HEAT_PUMP, PlantType.DISTRICT_HEATING, PlantType.ABSORPTION_CHILLER]:
        hce[f'Net Heat ({model.surfaceplant.HeatProduced.CurrentUnits.value})|:8.4f'] = \
            ShortenArrayToAnnual(model.surfaceplant.HeatProduced.value,
                                 model.surfaceplant.plant_lifetime.value, model.economics.timestepsperyear.value)

    # heat pump
    elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT and \
        model.surfaceplant.plant_type.value in [PlantType.HEAT_PUMP]:
        hce[f'Net Heat ({model.surfaceplant.HeatProduced.CurrentUnits.value})|:8.4f'] = \
            ShortenArrayToAnnual(model.surfaceplant.HeatProduced.value,
                                 model.surfaceplant.plant_lifetime.value, model.economics.timestepsperyear.value)
        hce[
            f'Heat Pump Electricity Used ({model.surfaceplant.heat_pump_electricity_used.CurrentUnits.value}|:8.4f'] = \
            ShortenArrayToAnnual(model.surfaceplant.heat_pump_electricity_used.value,
                                 model.surfaceplant.plant_lifetime.value, model.economics.timestepsperyear.value)

    # district heating
    elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT \
        and model.surfaceplant.plant_type.value in [PlantType.DISTRICT_HEATING]:
        hce[f'Geothermal Heat Output ({model.surfaceplant.HeatProduced.CurrentUnits.value})|:8.4f'] = \
            ShortenArrayToAnnual(model.surfaceplant.HeatProduced.value,
                                 model.surfaceplant.plant_lifetime.value, model.economics.timestepsperyear.value)

    # absorption chiller
    elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT and \
        model.surfaceplant.plant_type.value in [PlantType.ABSORPTION_CHILLER]:
        hce[f'Net Heat ({model.surfaceplant.HeatProduced.CurrentUnits.value})|:8.4f'] = \
            ShortenArrayToAnnual(model.surfaceplant.HeatProduced.value,
                                 model.surfaceplant.plant_lifetime.value,
                                 model.economics.timestepsperyear.value)
        hce[f'Net Cooling ({model.surfaceplant.HeatProduced.CurrentUnits.value})|:8.4f'] = \
            ShortenArrayToAnnual(model.surfaceplant.cooling_produced.value,
                                 model.surfaceplant.plant_lifetime.value,
                                 model.economics.timestepsperyear.value)

    # co-generation
    elif model.surfaceplant.enduse_option.value in [EndUseOptions.COGENERATION_TOPPING_EXTRA_HEAT,
                                                    EndUseOptions.COGENERATION_TOPPING_EXTRA_ELECTRICITY,
                                                    EndUseOptions.COGENERATION_BOTTOMING_EXTRA_ELECTRICITY,
                                                    EndUseOptions.COGENERATION_BOTTOMING_EXTRA_HEAT,
                                                    EndUseOptions.COGENERATION_PARALLEL_EXTRA_HEAT,
                                                    EndUseOptions.COGENERATION_PARALLEL_EXTRA_ELECTRICITY]:
        hce[f'Net Power ({model.surfaceplant.NetElectricityProduced.CurrentUnits.value})|:8.4f'] = \
            ShortenArrayToAnnual(model.surfaceplant.NetElectricityProduced.value,
                                 model.surfaceplant.plant_lifetime.value,
                                 model.economics.timestepsperyear.value)
        hce[f'Net Heat ({model.surfaceplant.HeatProduced.CurrentUnits.value})|:8.4f'] = \
            ShortenArrayToAnnual(model.surfaceplant.HeatProduced.value, model.surfaceplant.plant_lifetime.value,
                                 model.economics.timestepsperyear.value)
        hce[f'First Law Efficiency (%)|:8.4f'] = ShortenArrayToAnnual(model.surfaceplant.FirstLawEfficiency.value,
                                                                      model.surfaceplant.plant_lifetime.value,
                                                                      model.economics.timestepsperyear.value) * 100
    hce = hce.reset_index()

    # Build the data frame to hold the annual heating, cooling, and/or electricity production profile
    ahce: pd.DataFrame = pd.DataFrame()

    # add the columns as needed based on the output.
    # Note that the correct format for that column is stashed in the title of that column
    # so that it can be used in the write statement.
    ahce[f'Year|:2.0f'] = [i for i in range(1, (model.surfaceplant.plant_lifetime.value + 1))]

    # only electricity
    if model.surfaceplant.enduse_option.value == EndUseOptions.ELECTRICITY:
        ahce[f'Electricity Provided ({model.surfaceplant.NetkWhProduced.CurrentUnits.value})|:8.1f'] = \
            model.surfaceplant.NetkWhProduced.value / 1E6

    # absorption chiller
    elif model.surfaceplant.plant_type.value == PlantType.ABSORPTION_CHILLER:
        ahce[f'Cooling Provided ({model.surfaceplant.cooling_kWh_Produced.CurrentUnits.value})|:8.1f'] = \
            ShortenArrayToAnnual(model.surfaceplant.cooling_kWh_Produced.value,
                                 model.surfaceplant.plant_lifetime.value,
                                 model.economics.timestepsperyear.value) / 1E6

    # heat pump
    elif model.surfaceplant.plant_type.value == PlantType.HEAT_PUMP:
        ahce[f'Heating Provided ({model.surfaceplant.HeatkWhProduced.CurrentUnits.value})|:8.1f'] = \
            ShortenArrayToAnnual(model.surfaceplant.HeatkWhProduced.value, model.surfaceplant.plant_lifetime.value,
                                 model.economics.timestepsperyear.value) / 1E6
        ahce[f'Reservoir Heat Extracted ({model.surfaceplant.HeatkWhExtracted.CurrentUnits.value})|:8.1f'] = \
            ShortenArrayToAnnual(model.surfaceplant.HeatkWhExtracted.value, model.surfaceplant.plant_lifetime.value,
                                 model.economics.timestepsperyear.value) / 1E6
        ahce[
            f'Heat Pump Electricity Used ({model.surfaceplant.heat_pump_electricity_kwh_used.CurrentUnits.value})|:8.1f'] = \
            ShortenArrayToAnnual(model.surfaceplant.heat_pump_electricity_kwh_used.value,
                                 model.surfaceplant.plant_lifetime.value,
                                 model.economics.timestepsperyear.value) / 1E6

    # co-generation
    elif model.surfaceplant.enduse_option.value in [EndUseOptions.COGENERATION_TOPPING_EXTRA_HEAT,
                                                    EndUseOptions.COGENERATION_TOPPING_EXTRA_ELECTRICITY,
                                                    EndUseOptions.COGENERATION_BOTTOMING_EXTRA_ELECTRICITY,
                                                    EndUseOptions.COGENERATION_BOTTOMING_EXTRA_HEAT,
                                                    EndUseOptions.COGENERATION_PARALLEL_EXTRA_HEAT,
                                                    EndUseOptions.COGENERATION_PARALLEL_EXTRA_ELECTRICITY]:
        ahce[f'Heating Provided ({model.surfaceplant.HeatkWhProduced.CurrentUnits.value})|:8.1f'] = \
            ShortenArrayToAnnual(model.surfaceplant.HeatkWhProduced.value,
                                 model.surfaceplant.plant_lifetime.value,
                                 model.economics.timestepsperyear.value) / 1E6
        ahce[f'Electricity Provided ({model.surfaceplant.NetkWhProduced.CurrentUnits.value})|:8.1f'] = \
            ShortenArrayToAnnual(model.surfaceplant.NetkWhProduced.value,
                                 model.surfaceplant.plant_lifetime.value,
                                 model.economics.timestepsperyear.value) / 1E6

    # district-heating
    elif model.surfaceplant.plant_type.value in [PlantType.DISTRICT_HEATING]:
        ahce[f'Electricity Provided ({model.surfaceplant.HeatkWhProduced.CurrentUnits.value})|:8.1f'] = \
            ShortenArrayToAnnual(model.surfaceplant.HeatkWhProduced.value,
                                 model.surfaceplant.plant_lifetime.value,
                                 model.economics.timestepsperyear.value) / 1E6
        ahce[f'Peaking Boiler Heat Provided ({model.surfaceplant.annual_ng_demand.CurrentUnits.value})|:8.1f'] = \
            ShortenArrayToAnnual(model.surfaceplant.annual_ng_demand.value,
                                 model.surfaceplant.plant_lifetime.value,
                                 model.economics.timestepsperyear.value) / 1E3

    elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT:  # only direct-use
        ahce[f'Heating Provided ({model.surfaceplant.HeatkWhProduced.CurrentUnits.value})|:8.1f'] = \
            ShortenArrayToAnnual(model.surfaceplant.HeatkWhProduced.value, model.surfaceplant.plant_lifetime.value,
                                 model.economics.timestepsperyear.value) / 1E6

    # three columns always at the end of each style of table
    ahce[f'Heat Extracted({model.surfaceplant.HeatkWhExtracted.CurrentUnits.value})|:8.2f'] = \
        model.surfaceplant.HeatkWhExtracted.value / 1E6
    ahce[f'Reservoir Heat Content ({model.surfaceplant.RemainingReservoirHeatContent.CurrentUnits.value})|:8.2f'] = \
        model.surfaceplant.RemainingReservoirHeatContent.value
    ahce[f'Percentage of Total Heat Mined (%)|:8.2f'] = \
        (
                model.reserv.InitialReservoirHeatContent.value - model.surfaceplant.RemainingReservoirHeatContent.value) * 100. \
        / model.reserv.InitialReservoirHeatContent.value
    ahce = ahce.reset_index()

    # Build the data frame to hold the revenue and cashflow profile
    econ: Economics = model.economics
    # create a Coam array and zero out the OPEX during construction years
    construction_years_zeros = np.zeros(model.surfaceplant.construction_years.value)
    Coam = np.zeros(model.surfaceplant.construction_years.value + model.surfaceplant.plant_lifetime.value)
    for ii in range(model.surfaceplant.construction_years.value, model.surfaceplant.plant_lifetime.value + 1):
        Coam[ii] = econ.Coam.value

    cashflow: pd.DataFrame = pd.DataFrame()

    # add the columns as needed based on the output.
    # Note that the correct format for that column is stashed in the title of that column
    # so that it can be used in the write statement.
    # note that the price arrays need to be extended by the number of construction years. with price = 0
    cashflow[f'Year|:3.0f'] = [i for i in range(1,
                                                model.surfaceplant.plant_lifetime.value + model.surfaceplant.construction_years.value + 1)]
    cashflow[f'Electricity:Price ({econ.ElecPrice.CurrentUnits.value})|:7.4f'] = econ.ElecPrice.value
    cashflow[f'Electricity:Ann. Rev. ({econ.ElecRevenue.CurrentUnits.value})|:5.2f'] = econ.ElecRevenue.value
    cashflow[
        f'Electricity:Cumm. Rev. ({econ.ElecCummRevenue.CurrentUnits.value})|:5.2f'] = econ.ElecCummRevenue.value
    cashflow[f'Heat:Price ({econ.HeatPrice.CurrentUnits.value})|:7.4f'] = econ.HeatPrice.value
    cashflow[f'Heat:Ann. Rev. ({econ.HeatRevenue.CurrentUnits.value})|:5.2f'] = econ.HeatRevenue.value
    cashflow[f'Heat:Cumm. Rev. ({econ.HeatCummRevenue.CurrentUnits.value})|:5.2f'] = econ.HeatCummRevenue.value
    cashflow[f'Cooling:Price ({econ.CoolingPrice.CurrentUnits.value})|:7.4f'] = econ.CoolingPrice.value
    cashflow[f'Cooling:Ann. Rev. ({econ.CoolingRevenue.CurrentUnits.value})|:5.2f'] = econ.CoolingRevenue.value
    cashflow[
        f'Cooling:Cumm. Rev. ({econ.CoolingCummRevenue.CurrentUnits.value})|:5.2f'] = econ.CoolingCummRevenue.value
    cashflow[f'Carbon:Price ({econ.CarbonPrice.CurrentUnits.value})|:7.4f'] = econ.CarbonPrice.value
    cashflow[f'Carbon:Ann. Rev. ({econ.CarbonRevenue.CurrentUnits.value})|:5.2f'] = econ.CarbonRevenue.value
    cashflow[
        f'Carbon:Cumm. Rev. ({econ.CarbonCummCashFlow.CurrentUnits.value})|:5.2f'] = econ.CarbonCummCashFlow.value
    cashflow[f'Project:OPEX ({econ.Coam.CurrentUnits.value})|:5.2f'] = Coam
    cashflow[f'Project:Net Rev. ({econ.TotalRevenue.CurrentUnits.value})|:5.2f'] = econ.TotalRevenue.value
    cashflow[
        f'Project:Net Cashflow ({econ.TotalCummRevenue.CurrentUnits.value})|:5.2f'] = econ.TotalCummRevenue.value
    cashflow = cashflow.reset_index()

    # Build the data frame to hold the pumping power profiles
    pumping_power_profiles: pd.DataFrame = pd.DataFrame()

    if model.wellbores.overpressure_percentage.Provided and model.wellbores.injection_reservoir_depth.Provided:
        # add the columns as needed based on the output.
        # Note that the correct format for that column is stashed in the title of that column
        # so that it can be used in the write statement.
        pumping_power_profiles[f'Year|:2.0f'] = [i for i in range(1, (model.surfaceplant.plant_lifetime.value + 1))]
        pumping_power_profiles[f'Prod Pump Power ({model.wellbores.PumpingPowerProd.CurrentUnits.value})|:8.4f'] = ShortenArrayToAnnual(
            model.wellbores.PumpingPowerProd.value,
            model.surfaceplant.plant_lifetime.value, model.economics.timestepsperyear.value)
        pumping_power_profiles[f'Inject Pump Power ({model.wellbores.PumpingPowerInj.CurrentUnits.value})|:8.4f'] = ShortenArrayToAnnual(
            model.wellbores.PumpingPowerInj.value,
            model.surfaceplant.plant_lifetime.value, model.economics.timestepsperyear.value)
        pumping_power_profiles[f'Pump Power ({model.wellbores.PumpingPower.CurrentUnits.value})|:8.4f'] = ShortenArrayToAnnual(
            model.wellbores.PumpingPower.value,
            model.surfaceplant.plant_lifetime.value, model.economics.timestepsperyear.value)

    pumping_power_profiles = pumping_power_profiles.reset_index()

    if text_output_file.Provided:
        Write_Text_Output(text_output_file.value, simulation_metadata, summary, economic_parameters,
                          engineering_parameters,
                          resource_characteristics, reservoir_parameters, reservoir_stimulation_results, CAPEX,
                          OPEX,
                          surface_equipment_results, sdac_results, addon_results, hce, ahce, cashflow,
                          pumping_power_profiles, sdac_df, addon_df)

        # Get rid of any trailing spaces in that output file - they are confusing the testing code
        with open(text_output_file.value, 'r+') as fp:
            lines = fp.readlines()
            fp.seek(0)
            fp.truncate()
            for line in lines:
                line = line.rstrip() + '\n'
                fp.write(line)

    # uncomment these to allow for testing of the HTML output
    #        self.html_output_file.value = 'd:\\temp\\test_table_geophires.html'
    #        self.html_output_file.Provided = True
    if html_output_file.Provided:
        Write_HTML_Output(html_output_file.value, simulation_metadata, summary, economic_parameters,
                          engineering_parameters, resource_characteristics, reservoir_parameters,
                          reservoir_stimulation_results, CAPEX, OPEX, surface_equipment_results, sdac_results,
                          addon_results, hce, ahce, cashflow, pumping_power_profiles, sdac_df, addon_df)

        Plot_Tables_Into_HTML(model.surfaceplant.enduse_option, model.surfaceplant.plant_type,
                              html_output_file.value, hce, ahce, cashflow, pumping_power_profiles, sdac_df,
                              addon_df)
        # make district heating plot
        if model.surfaceplant.plant_type.value == PlantType.DISTRICT_HEATING:
            MakeDistrictHeatingPlot(html_output_file.value, model.surfaceplant.dh_geothermal_heating.value,
                                    model.surfaceplant.daily_heating_demand.value)

def removeDisallowedFilenameChars(filename):
    """
     This function removes disallowed filename characters
     :param filename: the filename
     :type filename: str
     :return: the cleaned filename
     :rtype: str
     """
    cleanedFilename = unicodedata.normalize('NFKD', filename).encode('ASCII', 'ignore')
    return ''.join(chr(c) for c in cleanedFilename if chr(c) in validFilenameChars)


def ShortenArrayToAnnual(array_to_shorten: pd.array, new_length:int, time_steps_per_year: int) -> pd.array:
    """
    This function shortens the array to the number of years in the model
    :param array_to_shorten: the array to shorten
    :type array_to_shorten: pd.array
    :param new_length: the new length
    :type new_length: int
    :param time_steps_per_year: the number of time steps per year
    :type time_steps_per_year: int
    :return: the new array
    :rtype: pd.array
    """
    if len(array_to_shorten) == new_length:
        return array_to_shorten

    new_array = np.zeros(new_length)

    j = 0
    for i in range(0, len(array_to_shorten), time_steps_per_year):
        new_array[j] = array_to_shorten[i]
        j = j + 1

    return new_array


def Write_Simple_Text_Table(title: str, items: list, f) -> None:
    """
    This function writes out the simple tables as text
    :param title: the title of the table
    :type title: str
    :param items: the list of items to be written out
    :type items: list
    :param f: the file object
    :type f: file
    """
    f.write(f'{NL}')
    f.write(f'                           ***{title}***{NL}')
    f.write(f'{NL}')
    for item in items:
        f.write(f'      {item.parameter:<45}: {item.value:^10} {item.units}{NL}')


def Write_Complex_Text_table(title: str, df_table: pd.DataFrame, time_steps_per_year: int, f) -> None:
    """
    This function writes out the complex tables as text
    :param title: the title of the table
    :type title: str
    :param df_table: the dataframe to be written out
    :type df_table: pd.DataFrame
    :param time_steps_per_year: the number of time steps per year
    :type time_steps_per_year: int
    :param f: the file object
    :type f: file
    """
    f.write(f'{NL}')
    f.write(f'                            ***************************************************************{NL}')
    f.write(f'                            *{title:^58}*{NL}')
    f.write(f'                            ***************************************************************{NL}')
    column_fmt = []
    for col in df_table.columns:
        if col != 'index':
            pair = col.split('|')
            column_name = pair[0]
            column_fmt.append(pair[1])
            f.write(f'  {UpgradeSymbologyOfUnits(column_name):^29}   ')

    f.write(f'{NL}')
    for index, row in df_table.iterrows():
        # only print the number of rows implied by time_steps_per_year
        if int(index) % time_steps_per_year == 0:
            for i in range(1, len(row)):
                f.write(f'{render_default((df_table.at[index, row.index[i]]) / time_steps_per_year, "", column_fmt[i - 1]):^33} ')
            f.write(f'{NL}')


def Write_Text_Output(output_path: str, simulation_metadata: list, summary: list, economic_parameters: list,
                      engineering_parameters: list, resource_characteristics: list, reservoir_parameters: list,
                      reservoir_stimulation_results: list, CAPEX: list, OPEX: list, surface_equipment_results: list,
                      sdac_results: list, addon_results: list, hce: pd.DataFrame, ahce: pd.DataFrame,
                      cashflow: pd.DataFrame, sdac_df: pd.DataFrame, addon_df: pd.DataFrame) -> None:
    """
    This function writes out the text output
    :param output_path: the path to the output file
    :type output_path: str
    :param simulation_metadata: the simulation metadata
    :type simulation_metadata: list
    :param summary: the summary of results
    :type summary: list
    :param economic_parameters: the economic parameters
    :type economic_parameters: list
    :param engineering_parameters: the engineering parameters
    :type engineering_parameters: list
    :param resource_characteristics: the resource characteristics
    :type resource_characteristics: list
    :param reservoir_parameters: the reservoir parameters
    :type reservoir_parameters: list
    :param reservoir_stimulation_results: the reservoir stimulation results
    :type reservoir_stimulation_results: list
    :param CAPEX: the capital costs
    :type CAPEX: list
    :param OPEX: the operating and maintenance costs
    :type OPEX: list
    :param surface_equipment_results: the surface equipment simulation results
    :type surface_equipment_results: list
    :param sdac_results: the sdac results
    :type sdac_results: list
    :param hce: the heating, cooling and/or electricity production profile
    :type hce: pd.DataFrame
    :param cashflow: the revenue & cashflow profile
    :type cashflow: pd.DataFrame
    :param sdac_df: the sdac dataframe
    :type sdac_df: pd.DataFrame
    :return: None
    """
    with open(output_path, 'w', encoding='UTF-8') as f:
        f.write(f'                               *****************{NL}')
        f.write(f'                               ***CASE REPORT***{NL}')
        f.write(f'                               *****************{NL}')
        f.write(f'{NL}')

        # write out the simulation metadata
        f.write(f'Simulation Metadata{NL}')
        f.write(f'----------------------{NL}')
        for item in simulation_metadata:
            f.write(f'{item.parameter}: {item.value} {item.units}{NL}')

        # write the simple text tables
        Write_Simple_Text_Table('SUMMARY OF RESULTS', summary, f)
        Write_Simple_Text_Table('ECONOMIC PARAMETERS', economic_parameters, f)
        Write_Simple_Text_Table('ENGINEERING PARAMETERS', engineering_parameters, f)
        Write_Simple_Text_Table('RESOURCE CHARACTERISTICS', resource_characteristics, f)
        Write_Simple_Text_Table('RESERVOIR PARAMETERS', reservoir_parameters, f)
        Write_Simple_Text_Table('RESERVOIR STIMULATION RESULTS', reservoir_stimulation_results, f)
        Write_Simple_Text_Table('CAPITAL COSTS', CAPEX, f)
        Write_Simple_Text_Table('OPERATING AND MAINTENANCE COSTS', OPEX, f)
        Write_Simple_Text_Table('SURFACE EQUIPMENT SIMULATION RESULTS', surface_equipment_results, f)
        if len(addon_results) > 0:
            Write_Simple_Text_Table('ADD-ON ECONOMICS', addon_results, f)
        if len(sdac_results) > 0:
            Write_Simple_Text_Table('S_DAC_GT ECONOMICS', sdac_results, f)

        # write the complex text tables
        Write_Complex_Text_table('HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILE', hce, 1, f)
        Write_Complex_Text_table('ANNUAL HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILE', ahce, 1, f)
        Write_Complex_Text_table('REVENUE & CASHFLOW PROFILE', cashflow, 1, f)
        if len(addon_df) > 0:
            Write_Complex_Text_table('ADD-ON PROFILE', addon_df, 1, f)
        if len(sdac_df) > 0:
            Write_Complex_Text_table('S_DAC_GT PROFILE', sdac_df, 1, f)


def Write_Simple_HTML_Table(title: str, items: list, console: rich.console) -> None:
    """
    This function writes out the simple tables as HTML. The console object is used to write out the HTML.
    :param title: the title of the table
    :type title: str
    :param items: the list of items to be written out
    :type items: list
    :param console: the console object
    :type console: rich.Console
    """
    table = Table(title=title)
    table.add_column('Parameter', style='bold', no_wrap=True, justify='center')
    table.add_column('Value', style='bold', no_wrap=True, justify='center')
    table.add_column('Units', style='bold', no_wrap=True, justify='center')
    for item in items:
        table.add_row(str(item.parameter), str(item.value), str(item.units))
    console.print(table)


def Write_Complex_HTML_Table(title: str, df_table: pd.DataFrame, time_steps_per_year: int, console: rich.console)-> None:
    """
    This function writes out the complex tables
    :param title: the title of the table
    :type title: str
    :param df_table: the dataframe to be written out
    :type df_table: pd.DataFrame
    :param time_steps_per_year: the number of time steps per year
    :type time_steps_per_year: int
    :param console: the console object
    :type console: rich.Console
    """
    table = Table(title=title)
    column_fmt = []
    for col in df_table.columns:
        if col != 'index':
            pair = col.split('|')
            column_name=pair[0]
            column_fmt.append(pair[1])
            table.add_column(UpgradeSymbologyOfUnits(column_name), style='bold', no_wrap=True, justify='center')
    for index, row in df_table.iterrows():
        # only print the number of rows implied by time_steps_per_year
        if time_steps_per_year == 0 or int(index) % time_steps_per_year == 0:
            table.add_row(*[render_default((df_table.at[index, row.index[i]]) / time_steps_per_year, '', column_fmt[i - 1]) for i in range(1, len(row))])
    console.print(table)


def Write_HTML_Output(html_path: str, simulation_metadata: list, summary: list, economic_parameters: list,
                      engineering_parameters: list, resource_characteristics: list, reservoir_parameters: list,
                      reservoir_stimulation_results: list, CAPEX: list, OPEX: list, surface_equipment_results: list,
                      sdac_results: list, addon_results: list, hce: pd.DataFrame, ahce: pd.DataFrame,
                      cashflow: pd.DataFrame, pumping_power_profiles: pd.DataFrame,
                      sdac_df: pd.DataFrame, addon_df: pd.DataFrame) -> None:
    """
    This function writes out the HTML output
    :param html_path: the path to the HTML output file
    :type html_path: str
    :param simulation_metadata: the simulation metadata
    :type simulation_metadata: list
    :param summary: the summary of results
    :type summary: list
    :param economic_parameters: the economic parameters
    :type economic_parameters: list
    :param engineering_parameters: the engineering parameters
    :type engineering_parameters: list
    :param resource_characteristics: the resource characteristics
    :type resource_characteristics: list
    :param reservoir_parameters: the reservoir parameters
    :type reservoir_parameters: list
    :param reservoir_stimulation_results: the reservoir stimulation results
    :type reservoir_stimulation_results: list
    :param CAPEX: the capital costs
    :type CAPEX: list
    :param OPEX: the operating and maintenance costs
    :type OPEX: list
    :param surface_equipment_results: the surface equipment simulation results
    :type surface_equipment_results: list
    :param sdac_results: the sdac results
    :type sdac_results: list
    :param addon_results: the addon results
    :type addon_results: list
    :param hce: the heating, cooling and/or electricity production profile
    :type hce: pd.DataFrame
    :param ahce: the annual heating, cooling and/or electricity production profile
    :type ahce: pd.DataFrame
    :param cashflow: the revenue & cashflow profile
    :type cashflow: pd.DataFrame
    :param pumping_power_profiles: the pumping power profiles
    :type pd.DataFrame
    :param sdac_df: the sdac dataframe
    :type sdac_df: pd.DataFrame
    :param addon_df: the addon dataframe

    """

    console = Console(style='bold black on white', force_terminal=True, record=True, width=500)

    # write out the simulation metadata
    console.print('*****************')
    console.print('***CASE REPORT***')
    console.print('*****************')
    console.print('Simulation Metadata')
    console.print('----------------------')

    for item in simulation_metadata:
        console.print(f'{str(item.parameter)}: {str(item.value)} {str(item.units)}')

    # write out the simple tables
    Write_Simple_HTML_Table('SUMMARY OF RESULTS', summary, console)
    Write_Simple_HTML_Table('ECONOMIC PARAMETERS', economic_parameters, console)
    Write_Simple_HTML_Table('ENGINEERING PARAMETERS', engineering_parameters, console)
    Write_Simple_HTML_Table('RESOURCE CHARACTERISTICS', resource_characteristics, console)
    Write_Simple_HTML_Table('RESERVOIR PARAMETERS', reservoir_parameters, console)
    Write_Simple_HTML_Table('RESERVOIR STIMULATION RESULTS', reservoir_stimulation_results, console)
    Write_Simple_HTML_Table('CAPITAL COSTS', CAPEX, console)
    Write_Simple_HTML_Table('OPERATING AND MAINTENANCE COSTS', OPEX, console)
    Write_Simple_HTML_Table('SURFACE EQUIPMENT SIMULATION RESULTS', surface_equipment_results, console)
    if len(addon_results) > 0:
        Write_Simple_HTML_Table('ADD-ON ECONOMICS', addon_results, console)
    if len(sdac_results) > 0:
        Write_Simple_HTML_Table('S_DAC_GT ECONOMICS', sdac_results, console)

    # write out the complex tables
    Write_Complex_HTML_Table('HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILE', hce, 1, console)
    Write_Complex_HTML_Table('ANNUAL HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILE', ahce, 1, console)
    Write_Complex_HTML_Table('REVENUE & CASHFLOW PROFILE', cashflow, 1, console)
    if len(pumping_power_profiles) > 0:
        Write_Complex_HTML_Table('PUMPING POWER PROFILES', pumping_power_profiles, 1, console)
    if len(addon_df) > 0:
        Write_Complex_HTML_Table('ADD-ON PROFILE', addon_df, 1, console)
    if len(sdac_df) > 0:
        Write_Complex_HTML_Table('S_DAC_GT PROFILE', sdac_df, 1, console)

    # Save it all as HTML.
    console.save_html(html_path)


def profile_title_adjusted_for_figure(title:str) -> str:
    return title.replace('PROFILE: ', 'PROFILE:\n').replace('PROFILES: ', 'PROFILES:\n')


def Plot_Twin_Graph(title: str, html_path: str, x: pd.array, y1: pd.array, y2: pd.array,
                    x_label: str, y1_label: str, y2_label:str) -> None:
    """
    This function plots the twin graph
    :param title: the title of the graph
    :type title: str
    :param html_path: the path to the HTML output file
    :type html_path: str
    :param x: the x values
    :type x: pd.array
    :param y1: the y1 values
    :type y1: pd.array
    :param y2: the y2 values
    :type y2: pd.array
    :param x_label: the x label
    :type x_label: str
    :param y1_label: the y1 label
    :type y1_label: str
    :param y2_label: the y2 label
    :type y2_label: str
    """
    COLOR_TEMPERATURE = "#69b3a2"
    COLOR_PRICE = "#3399e6"

    fig, ax1 = plt_subplots(figsize=_GRAPH_FIGSIZE)

    ax1.plot(x, y1, label=UpgradeSymbologyOfUnits(y1_label), color=COLOR_PRICE, lw=3)
    ax1.set_xlabel(UpgradeSymbologyOfUnits(x_label), color = COLOR_PRICE, fontsize=14)
    ax1.set_ylabel(UpgradeSymbologyOfUnits(y1_label), color=COLOR_PRICE, fontsize=14)
    ax1.tick_params(axis="y", labelcolor=COLOR_PRICE)
    ax1.set_xlim(x.min(), x.max())
    ax1.legend(loc='lower left')

    ax2 = ax1.twinx()
    ax2.plot(x, y2, label=UpgradeSymbologyOfUnits(y2_label), color=COLOR_TEMPERATURE, lw=4)
    ax2.set_ylabel(UpgradeSymbologyOfUnits(y2_label), color=COLOR_TEMPERATURE, fontsize=14)
    ax2.tick_params(axis="y", labelcolor=COLOR_TEMPERATURE)
    ax2.legend(loc='best')

    fig.suptitle(profile_title_adjusted_for_figure(title), fontsize=20)

    full_names: set = set()
    short_names: set = set()
    title = removeDisallowedFilenameChars(title.replace(' ', '_'))
    save_path = Path(Path(html_path).parent, f'{title}.png')
    plt.savefig(save_path)
    short_names.add(title)
    full_names.add(save_path)

    InsertImagesIntoHTML(html_path, short_names, full_names)


def Plot_Single_Graph(title: str, html_path: str, x: pd.array, y: pd.array, x_label: str, y_label: str) -> None:
    """
    This function plots the single graph
    :param title: the title of the graph
    :type title: str
    :param html_path: the path to the HTML output file
    :type html_path: str
    :param x: the x values
    :type x: pd.array
    :param y: the y values
    :type y: pd.array
    :param x_label: the x label
    :type x_label: str
    :param y_label: the y label
    :type y_label: str
    """
    COLOR_PRICE = "#3399e6"

#    plt.plot(x, y, color=COLOR_PRICE)
    fig, ax = plt_subplots(figsize=_GRAPH_FIGSIZE)
    ax.plot(x, y, label=UpgradeSymbologyOfUnits(y_label), color=COLOR_PRICE)
    ax.set_xlabel(UpgradeSymbologyOfUnits(x_label), color = COLOR_PRICE, fontsize=14)
    ax.set_ylabel(UpgradeSymbologyOfUnits(y_label), color=COLOR_PRICE, fontsize=14)
    ax.tick_params(axis="y", labelcolor=COLOR_PRICE)
    ax.set_xlim(x.min(), x.max())
    ax.legend(loc='best')
    #plt.ylim(y.min(), y.max())
    #plt.gca().legend((UpgradeSymbologyOfUnits(x_label), UpgradeSymbologyOfUnits(y_label)), loc='best')
    fig.suptitle(profile_title_adjusted_for_figure(title), fontsize=20)

    full_names: set = set()
    short_names: set = set()
    title = removeDisallowedFilenameChars(title.replace(' ', '_'))
    save_path = Path(Path(html_path).parent, f'{title}.png')
    plt.savefig(save_path)
    short_names.add(title)
    full_names.add(save_path)

    InsertImagesIntoHTML(html_path, short_names, full_names)


def Plot_Tables_Into_HTML(enduse_option: intParameter, plant_type: intParameter, html_path: str,
                          hce: pd.DataFrame, ahce: pd.DataFrame, cashflow: pd.DataFrame, pumping_power_profiles: pd.DataFrame,
                          sdac_df: pd.DataFrame, addon_df: pd.DataFrame) -> None:
    """
    This function plots the tables into the HTML
    :param enduse_option: the end use option
    :type enduse_option: intParameter
    :param html_path: the path to the HTML output file
    :type html_path: str
    :param plant_type: the plant type
    :type plant_type: intParameter
    :param hce: the heating, cooling and/or electricity production profile
    :type hce: pd.DataFrame
    :param ahce: the annual heating, cooling and/or electricity production profile
    :type ahce: pd.DataFrame
    :param cashflow: the revenue & cashflow profile
    :type cashflow: pd.DataFrame
    :param pumping_power_profiles: The pumping power profiles
    :type pd.DataFrame
    :param sdac_df: the sdac dataframe
    :type sdac_df: pd.DataFrame
    :param addon_df: the addon dataframe
    :type addon_df: pd.DataFrame
    """

    # HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILES
    # Plot the three that appear for all end uses
    Plot_Single_Graph('HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILES: Thermal Drawdown',
                      html_path, hce.values[0:, 0], hce.values[0:, 1], hce.columns[0].split('|')[0], hce.columns[1].split('|')[0])
    Plot_Single_Graph('HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILES: Geofluid Temperature',
                      html_path, hce.values[0:, 0], hce.values[0:, 2], hce.columns[0].split('|')[0], hce.columns[2].split('|')[0])
    Plot_Single_Graph('HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILES: Pump Power',
                      html_path, hce.values[0:, 0], hce.values[0:, 3], hce.columns[0].split('|')[0], hce.columns[3].split('|')[0])
    if enduse_option.value == EndUseOptions.ELECTRICITY:
        # only electricity
        Plot_Single_Graph('HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILES: First Law Efficiency',
                        html_path, hce.values[0:, 0], hce.values[0:, 5], hce.columns[0].split('|')[0], hce.columns[5].split('|')[0])
        Plot_Single_Graph('HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILES: Net Power',
                        html_path, hce.values[0:, 0], hce.values[0:, 4], hce.columns[0].split('|')[0], hce.columns[4].split('|')[0])
    elif enduse_option.value == EndUseOptions.HEAT and plant_type.value not in [PlantType.HEAT_PUMP, PlantType.DISTRICT_HEATING, PlantType.ABSORPTION_CHILLER]:
        # only direct-use
        Plot_Single_Graph('HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILES: Net Heat',
                        html_path, hce.values[0:, 0], hce.values[0:, 4], hce.columns[0].split('|')[0], hce.columns[4].split('|')[0])
    elif enduse_option.value == EndUseOptions.HEAT and plant_type.value == PlantType.HEAT_PUMP:
        # heat pump
        Plot_Twin_Graph('HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILES: Net Heat & Heat Pump Electricity Use',
                        html_path, hce.values[0:, 0], hce.values[0:, 4], hce.values[0:, 5],
                        hce.columns[0].split('|')[0], hce.columns[4].split('|')[0], hce.columns[5].split('|')[0])
    elif enduse_option.value == EndUseOptions.HEAT and plant_type.value == PlantType.DISTRICT_HEATING:
        # district heating
        Plot_Single_Graph('HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILES: Geothermal Heat Output',
                        html_path, hce.values[0:, 0], hce.values[0:, 4], hce.columns[0].split('|')[0], hce.columns[4].split('|')[0])
    elif enduse_option.value == EndUseOptions.HEAT and plant_type.value == PlantType.ABSORPTION_CHILLER:
        # absorption chiller
        Plot_Twin_Graph('HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILES: Net Heat & Net Cooling',
                        html_path, hce.values[0:, 0], hce.values[0:, 4], hce.values[0:, 5],
                        hce.columns[0].split('|')[0], hce.columns[4].split('|')[0], hce.columns[5].split('|')[0])
    elif enduse_option.value in [EndUseOptions.COGENERATION_TOPPING_EXTRA_HEAT, EndUseOptions.COGENERATION_TOPPING_EXTRA_ELECTRICITY,
                                EndUseOptions.COGENERATION_BOTTOMING_EXTRA_ELECTRICITY, EndUseOptions.COGENERATION_BOTTOMING_EXTRA_HEAT,
                                EndUseOptions.COGENERATION_PARALLEL_EXTRA_HEAT, EndUseOptions.COGENERATION_PARALLEL_EXTRA_ELECTRICITY]:
        # co-gen
        Plot_Twin_Graph('HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILES: Net Power & Net Heat',
                        html_path, hce.values[0:, 0], hce.values[0:, 4], hce.values[0:, 5],
                        hce.columns[0].split('|')[0], hce.columns[4].split('|')[0], hce.columns[5].split('|')[0])
        Plot_Single_Graph('HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILES: First Law Efficiency',
                        html_path, hce.values[0:, 0], hce.values[0:, 6], hce.columns[0].split('|')[0], hce.columns[6].split('|')[0])

    # ANNUAL HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILE
    # plot the common graphs
    Plot_Twin_Graph('ANNUAL HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILE: Heat Extracted & Reservoir Heat Content',
                    html_path, ahce.values[0:, 0], ahce.values[0:, 2], ahce.values[0:, 3],
                    ahce.columns[0].split('|')[0], ahce.columns[2].split('|')[0], ahce.columns[3].split('|')[0])
    if plant_type.value in [PlantType.DISTRICT_HEATING]:
        # columns are in a different place for district heating
        Plot_Single_Graph('ANNUAL HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILE: Percentage of Total Heat Mined',
                          html_path, ahce.values[0:, 0], ahce.values[0:, 5], ahce.columns[0].split('|')[0], ahce.columns[5].split('|')[0])
    else:
        Plot_Single_Graph('ANNUAL HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILE: Percentage of Total Heat Mined',
                          html_path, ahce.values[0:, 0], ahce.values[0:, 4], ahce.columns[0].split('|')[0], ahce.columns[4].split('|')[0])

    if enduse_option.value == EndUseOptions.ELECTRICITY:
        # only electricity
        Plot_Single_Graph('ANNUAL HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILE: Electricity Provided',
                          html_path, ahce.values[0:, 0], ahce.values[0:, 1], ahce.columns[0].split('|')[0], ahce.columns[1].split('|')[0])
    elif plant_type.value == PlantType.ABSORPTION_CHILLER:
        # absorption chiller
        Plot_Single_Graph('ANNUAL HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILE: Cooling Provided',
                          html_path, ahce.values[0:, 0], ahce.values[0:, 1], ahce.columns[0].split('|')[0], ahce.columns[1].split('|')[0])
    elif plant_type.value in [PlantType.DISTRICT_HEATING]:
        # district-heating
        Plot_Twin_Graph('ANNUAL HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILE: Geothermal Heating Provided & Peaking Boiler Heating Provided',
                        html_path, ahce.values[0:, 0], ahce.values[0:, 1], ahce.values[0:, 2],
                        ahce.columns[0].split('|')[0], ahce.columns[1].split('|')[0], ahce.columns[2].split('|')[0])
    elif plant_type.value == PlantType.HEAT_PUMP:
        # heat pump
        Plot_Single_Graph('ANNUAL HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILE: Heating Provided',
                          html_path, ahce.values[0:, 0], ahce.values[0:, 1], ahce.columns[0].split('|')[0], ahce.columns[1].split('|')[0])
        Plot_Single_Graph('ANNUAL HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILE: Heat Pump Electricity Use',
                          html_path, ahce.values[0:, 0], ahce.values[0:, 3], ahce.columns[0].split('|')[0], ahce.columns[3].split('|')[0])
    elif enduse_option.value in [EndUseOptions.COGENERATION_TOPPING_EXTRA_HEAT, EndUseOptions.COGENERATION_TOPPING_EXTRA_ELECTRICITY,
                                                    EndUseOptions.COGENERATION_BOTTOMING_EXTRA_ELECTRICITY, EndUseOptions.COGENERATION_BOTTOMING_EXTRA_HEAT,
                                                    EndUseOptions.COGENERATION_PARALLEL_EXTRA_HEAT, EndUseOptions.COGENERATION_PARALLEL_EXTRA_ELECTRICITY]:
        # co-gen
        Plot_Twin_Graph('ANNUAL HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILE: Heat Provided & Electricity Provided',
                        html_path, ahce.values[0:, 0], ahce.values[0:, 1], ahce.values[0:, 2],
                        ahce.columns[0].split('|')[0], ahce.columns[1].split('|')[0], ahce.columns[2].split('|')[0])
    elif enduse_option.value == EndUseOptions.HEAT:
        # only direct-use
        Plot_Single_Graph('ANNUAL HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILE: Heat Provided',
                          html_path, ahce.values[0:, 0], ahce.values[0:, 1], ahce.columns[0].split('|')[0], ahce.columns[1].split('|')[0])

    # Cashflow Graphs
    Plot_Twin_Graph('REVENUE & CASHFLOW PROFILE: Electricity: Price & Cumulative Revenue',
                    html_path, cashflow.values[0:, 0], cashflow.values[0:, 1], cashflow.values[0:, 3],
                    cashflow.columns[0].split('|')[0], cashflow.columns[1].split('|')[0], cashflow.columns[3].split('|')[0])
    Plot_Twin_Graph('REVENUE & CASHFLOW PROFILE: Heat: Price & Cumulative Revenue',
                    html_path, cashflow.values[0:, 0], cashflow.values[0:, 4], cashflow.values[0:, 6],
                    cashflow.columns[0].split('|')[0], cashflow.columns[4].split('|')[0], cashflow.columns[6].split('|')[0])
    Plot_Twin_Graph('REVENUE & CASHFLOW PROFILE: Cooling: Price & Cumulative Revenue',
                    html_path, cashflow.values[0:, 0], cashflow.values[0:, 7], cashflow.values[0:, 9],
                    cashflow.columns[0].split('|')[0], cashflow.columns[7].split('|')[0], cashflow.columns[9].split('|')[0])
    Plot_Twin_Graph('REVENUE & CASHFLOW PROFILE: Carbon: Price & Cumulative Revenue',
                    html_path, cashflow.values[0:, 0], cashflow.values[0:, 10], cashflow.values[0:, 12],
                    cashflow.columns[0].split('|')[0], cashflow.columns[10].split('|')[0], cashflow.columns[12].split('|')[0])
    Plot_Twin_Graph('REVENUE & CASHFLOW PROFILE: Project: Net Revenue and cashflow',
                    html_path, cashflow.values[0:, 0], cashflow.values[0:, 14], cashflow.values[0:, 15],
                    cashflow.columns[0].split('|')[0], cashflow.columns[14].split('|')[0], cashflow.columns[15].split('|')[0])

    # Pumping Power Profiles Graphs
    if len(pumping_power_profiles) > 0:
        Plot_Twin_Graph('PUMPING POWER PROFILES: Production Pumping Power & Injection Pumping Power', html_path,
                        pumping_power_profiles.values[0:, 0], pumping_power_profiles.values[0:, 1], pumping_power_profiles.values[0:, 2],
                        pumping_power_profiles.columns[0].split('|')[0], pumping_power_profiles.columns[1].split('|')[0], pumping_power_profiles.columns[2].split('|')[0])
        Plot_Single_Graph('PUMPING POWER PROFILES: Pumping Power', html_path,
                            pumping_power_profiles.values[0:, 0], pumping_power_profiles.values[0:, 3], pumping_power_profiles.columns[0].split('|')[0],
                            pumping_power_profiles.columns[3].split('|')[0])

    if len (addon_df) > 0:
        Plot_Twin_Graph('ADD-ON PROFILE: Electricity Annual Price vs. Revenue',
                        html_path, addon_df.values[0:, 0], addon_df.values[0:, 1], addon_df.values[0:, 2],
                        addon_df.columns[0].split('|')[0], addon_df.columns[1].split('|')[0], addon_df.columns[2].split('|')[0])
        Plot_Twin_Graph('ADD-ON PROFILE: Heat Annual Price vs. Revenue',
                        html_path, addon_df.values[0:, 0], addon_df.values[0:, 3], addon_df.values[0:, 4],
                        addon_df.columns[0].split('|')[0], addon_df.columns[3].split('|')[0], addon_df.columns[4].split('|')[0])
        Plot_Twin_Graph('ADD-ON PROFILE: Add-On Net Revenue & Annual Cashflow',
                        html_path, addon_df.values[0:, 0], addon_df.values[0:, 5], addon_df.values[0:, 6],
                        addon_df.columns[0].split('|')[0], addon_df.columns[5].split('|')[0], addon_df.columns[6].split('|')[0])
        Plot_Single_Graph('ADD-ON PROFILE: Add-On Cumulative Cashflow',
                        html_path, addon_df.values[0:, 0], addon_df.values[0:, 7],  addon_df.columns[0].split('|')[0],
                          addon_df.columns[7].split('|')[0])
        Plot_Twin_Graph('ADD-ON PROFILE: Project Cashflow vs. Cumulative Cashflow',
                        html_path, addon_df.values[0:, 0], addon_df.values[0:, 8], addon_df.values[0:, 9],
                        addon_df.columns[0].split('|')[0], addon_df.columns[8].split('|')[0], addon_df.columns[9].split('|')[0])
    if len(sdac_df) > 0:
        Plot_Twin_Graph('S_DAC_GT PROFILE: Annual vs Cumulative Carbon Captured',
                        html_path, sdac_df.values[0:, 0], sdac_df.values[0:, 1], sdac_df.values[0:, 2],
                        sdac_df.columns[0].split('|')[0], sdac_df.columns[1].split('|')[0], sdac_df.columns[2].split('|')[0])
        Plot_Twin_Graph('S_DAC_GT PROFILE: Annual Cost vs Cumulative Cost',
                        html_path, sdac_df.values[0:, 0], sdac_df.values[0:, 3], sdac_df.values[0:, 4],
                        sdac_df.columns[0].split('|')[0], sdac_df.columns[3].split('|')[0], sdac_df.columns[4].split('|')[0])
        Plot_Single_Graph('S_DAC_GT PROFILE: Cumulative Capture Cost per Tonne',
                        html_path, sdac_df.values[0:, 0], sdac_df.values[0:, 5], sdac_df.columns[0].split('|')[0],
                          sdac_df.columns[5].split('|')[0])


def MakeDistrictHeatingPlot(html_path: str, dh_geothermal_heating: pd.array, daily_heating_demand: pd.array) -> None:
    """"
    Make a plot of the district heating system
    :param html_path: the path to the HTML output file
    :type html_path: str
    :param dh_geothermal_heating: the geothermal heating
    :type dh_geothermal_heating: pd.array
    :param daily_heating_demand: the daily heating demand
    :type daily_heating_demand: pd.array
    """
    plt.close('all')
    year_day = np.arange(1, 366, 1)  # make an array of days for plot x-axis
    plt.plot(year_day, daily_heating_demand, label='District Heating Demand')
    plt.fill_between(year_day, 0, dh_geothermal_heating[0:365] * 24, color='g', alpha=0.5,
                     label='Geothermal Heat Supply')
    plt.fill_between(year_day, dh_geothermal_heating[0:365] * 24,
                     daily_heating_demand, color='r', alpha=0.5,
                     label='Natural Gas Heat Supply')
    plt.xlabel('Ordinal Day')
    plt.ylabel('Heating Demand/Supply [MWh/day]')
    plt.ylim([0, max(daily_heating_demand) * 1.05])
    plt.legend()
    plt.title('Geothermal district heating system with peaking boilers')
    full_names: set = set()
    short_names: set = set()
    title = removeDisallowedFilenameChars('Geothermal district heating system with peaking boilers'.replace(' ', '_'))
    save_path = Path(Path(html_path).parent, f'{title}.png')
    plt.savefig(save_path)
    short_names.add(title)
    full_names.add(save_path)

    InsertImagesIntoHTML(html_path, short_names, full_names)


