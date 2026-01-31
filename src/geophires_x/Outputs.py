from __future__ import annotations

import datetime
import math
import time
import sys
from io import TextIOWrapper
from pathlib import Path

# noinspection PyPackageRequirements
import numpy as np
import pandas as pd

import geophires_x
import geophires_x.Model as Model
from geophires_x.Economics import Economics
from geophires_x.EconomicsSam import get_sam_cash_flow_profile_tabulated_output
from geophires_x.OutputsRich import print_outputs_rich
from geophires_x.Parameter import ConvertUnitsBack, ConvertOutputUnits, LookupUnits, strParameter, boolParameter, \
    OutputParameter, ReadParameter, ParameterEntry
from geophires_x.OptionList import EndUseOptions, EconomicModel, ReservoirModel, FractureShape, ReservoirVolume, \
    PlantType
from geophires_x.Parameter import Parameter

NL = '\n'


class Outputs:
    """
    This class handles all the outputs for the GEOPHIRESv3 model.
    """

    VERTICAL_WELL_DEPTH_OUTPUT_NAME = 'Well depth'

    def __init__(self, model: Model, output_file: str = 'HDR.out'):
        model.logger.info(f'Init {__class__!s}: {__name__}')

        self.output_file = output_file

        self.ParameterDict = {}
        self.OutputParameterDict = {}
        self.filepath_parameter_names = []

        def filepath_parameter(p: Parameter) -> Parameter:
            self.filepath_parameter_names.append(p.Name)
            return p

        self.text_output_file = self.ParameterDict[self.text_output_file.Name] = filepath_parameter(strParameter(
                'Improved Text Output File',
                DefaultValue='GEOPHIRES_Text.html',
                Required=False,
                Provided=False,
                ErrMessage='assume no improved text output',
                ToolTipText='Provide a improved text output name if you want to have improved text output (no output if not provided)',
        ))

        self.html_output_file = self.ParameterDict[self.html_output_file.Name] = filepath_parameter(strParameter(
                'HTML Output File',
                DefaultValue='GEOPHIRES.html',
                Required=False,
                Provided=False,
                ErrMessage='assume no HTML output',
                ToolTipText='Provide a HTML output name if you want to have HTML output (no output if not provided)',
        ))

        # noinspection SpellCheckingInspection
        self.printoutput = self.ParameterDict[self.printoutput.Name] = boolParameter(
                'Print Output to Console',
                DefaultValue=True,
                Required=False,
                Provided=False,
                ErrMessage='assume no output to console',
                ToolTipText='Provide a 0 if you do not want to print output to the console',
            )

        model.logger.info(f'Complete {__class__!s}: {__name__}')

    def __str__(self):
        return 'Outputs'

    def read_parameters(self, model: Model, default_output_path: Path = None) -> None:
        """
        The read_parameters function reads in the parameters from a dictionary and stores them in the parameters.
        It also handles special cases that need to be handled after a value has been read in and checked.
        If you choose to subclass this master class, you can also choose to override this method (or not), and if you do
        Deal with all the parameter values that the user has provided.  They should really only provide values that
        they want to change from the default values, but they can provide a value that is already set because it is a
        default value set in __init__.  It will ignore those.
        This also deals with all the special cases that need to be taken care of after a value has been read in
        and checked.
        If you choose to subclass this master class, you can also choose to override this method (or not),
        and if you do, do it before or after you call you own version of this method.  If you do, you can also choose
        to call this method from you class, which can effectively modify all these superclass parameters in your class.
        :param model: The container class of the application, giving access to everything else, including the logger
        :type model: :class:`~geophires_x.Model.Model`
        :param default_output_path: Relative path for non-absolute output path parameters
        :type default_output_path: pathlib.Path
        :return: None
        """
        model.logger.info(f'Init {__class__!s}: {__name__}')
        if len(model.InputParameters) > 0:
            # loop through all the parameters that the user wishes to set, looking for parameters that match this object
            for item in self.ParameterDict.items():
                ParameterToModify = item[1]
                key = ParameterToModify.Name.strip()
                if key in model.InputParameters:
                    ParameterReadIn: ParameterEntry = model.InputParameters[key]

                    if key in self.filepath_parameter_names:
                        if not Path(ParameterReadIn.sValue).is_absolute() and default_output_path is not None:
                            original_val = ParameterReadIn.sValue
                            ParameterReadIn.sValue = str(
                                default_output_path.joinpath(Path(ParameterReadIn.sValue)).absolute())
                            model.logger.info(f'Adjusted {key} path to {ParameterReadIn.sValue} because original value '
                                              f'({original_val}) was not an absolute path.')

                    # this should handle all the non-special cases
                    ReadParameter(ParameterReadIn, ParameterToModify, model)

        # handle the special cases
        if len(model.InputParameters) > 0:
            # loop through all the parameters that the user wishes to set, looking for parameters that contain the
            # prefix "Units:" - that means we want to set a special case for converting this
            # output parameter to new units
            for key in model.InputParameters.keys():
                if key.startswith('Units:'):
                    self.ParameterDict[key.replace('Units:', '')] = LookupUnits(model.InputParameters[key].sValue)[0]

        model.logger.info(f'Complete {__class__!s}: {__name__}')

    def _convert_units(self, model: Model):
        # Deal with converting Units back to PreferredUnits, if required.
        # before we write the outputs, we go thru all the parameters for all of the objects and set the values back
        # to the units that the user entered the data in
        # We do this because the value may be displayed in the output, and we want the user to recginze their value,
        # not some converted value
        for obj in [model.reserv, model.wellbores, model.surfaceplant, model.economics]:
            for key in obj.ParameterDict:
                param = obj.ParameterDict[key]
                if not param.UnitsMatch:
                    ConvertUnitsBack(param, model)

        # now we need to loop through all the output parameters to update their units to
        # whatever units the user has specified.
        # i.e., they may have specified that all LENGTH results must be in feet, so we need to convert those
        # from whatever LENGTH unit they are to feet.
        # same for all the other classes of units (TEMPERATURE, DENSITY, etc).

        for obj in [model.reserv, model.wellbores, model.surfaceplant, model.economics]:
            for key in obj.OutputParameterDict:
                output_param:OutputParameter = obj.OutputParameterDict[key]
                if key in self.ParameterDict:
                    if self.ParameterDict[key] != output_param.CurrentUnits:
                        ConvertOutputUnits(output_param, self.ParameterDict[key], model)
                elif not output_param.UnitsMatch:
                    obj.OutputParameterDict[key] = output_param.with_preferred_units()

    def PrintOutputs(self, model: Model):
        """
        PrintOutputs writes the standard outputs to the output file.
        :param model: The container class of the application, giving access to everything else, including the logger
        :type model: :class:`~geophires_x.Model.Model`
        :return: None
        """
        model.logger.info(f'Init {str(__class__)}: {sys._getframe().f_code.co_name}')

        self._convert_units(model)

        # write results to output file and screen
        try:
            with open(self.output_file, 'w', encoding='UTF-8') as f:

                econ: Economics = model.economics
                is_sam_econ_model = econ.econmodel.value == EconomicModel.SAM_SINGLE_OWNER_PPA

                f.write('                               *****************\n')
                f.write('                               ***CASE REPORT***\n')
                f.write('                               *****************\n')
                f.write(NL)
                f.write('Simulation Metadata\n')
                f.write('----------------------\n')
                f.write(f' GEOPHIRES Version: {geophires_x.__version__}\n')
                f.write(' Simulation Date: '+ datetime.datetime.now().strftime('%Y-%m-%d\n'))
                f.write(' Simulation Time:  '+ datetime.datetime.now().strftime('%H:%M\n'))
                f.write(' Calculation Time: '+'{0:10.3f}'.format((time.time()-model.tic)) + ' sec\n')

                f.write(NL)
                f.write('                           ***SUMMARY OF RESULTS***\n')
                f.write(NL)
                f.write(f'      {model.surfaceplant.enduse_option_output.display_name}: '
                        f'{model.surfaceplant.enduse_option_output.value}\n')
                if model.surfaceplant.plant_type.value in [PlantType.ABSORPTION_CHILLER, PlantType.HEAT_PUMP, PlantType.DISTRICT_HEATING]:
                    f.write('      Surface Application: ' + str(model.surfaceplant.plant_type.value.value) + NL)
                if model.surfaceplant.enduse_option.value in [EndUseOptions.ELECTRICITY, EndUseOptions.COGENERATION_TOPPING_EXTRA_HEAT, EndUseOptions.COGENERATION_TOPPING_EXTRA_ELECTRICITY, EndUseOptions.COGENERATION_BOTTOMING_EXTRA_ELECTRICITY, EndUseOptions.COGENERATION_BOTTOMING_EXTRA_HEAT, EndUseOptions.COGENERATION_PARALLEL_EXTRA_HEAT, EndUseOptions.COGENERATION_PARALLEL_EXTRA_ELECTRICITY]: # there is an electricity component
                    f.write(f'      Average Net Electricity Production:               {np.average(model.surfaceplant.NetElectricityProduced.value):10.2f} ' + model.surfaceplant.NetElectricityProduced.CurrentUnits.value + NL)
                if model.surfaceplant.enduse_option.value is not EndUseOptions.ELECTRICITY:
                    # there is a direct-use component
                    f.write(f'      Average Direct-Use Heat Production:               {np.average(model.surfaceplant.HeatProduced.value):10.2f} '+ model.surfaceplant.HeatProduced.CurrentUnits.value + NL)
                if model.surfaceplant.plant_type.value == PlantType.DISTRICT_HEATING:
                    f.write(f'      Annual District Heating Demand:                   {np.average(model.surfaceplant.annual_heating_demand.value):10.2f} ' + model.surfaceplant.annual_heating_demand.CurrentUnits.value + NL)
                    f.write(f'      Average Annual Geothermal Heat Production:        {sum(model.surfaceplant.dh_geothermal_heating.value * 24) / model.surfaceplant.plant_lifetime.value / 1e3:10.2f} ' + model.surfaceplant.annual_heating_demand.CurrentUnits.value + NL)
                    f.write(f'      Average Annual Peaking Fuel Heat Production:      {sum(model.surfaceplant.dh_natural_gas_heating.value * 24) / model.surfaceplant.plant_lifetime.value / 1e3:10.2f} ' + model.surfaceplant.annual_heating_demand.CurrentUnits.value + NL)
                if model.surfaceplant.plant_type.value == PlantType.ABSORPTION_CHILLER:
                    f.write(f'      Average Cooling Production:                       {np.average(model.surfaceplant.cooling_produced.value):10.2f} ' + model.surfaceplant.cooling_produced.CurrentUnits.value + NL)

                if model.surfaceplant.enduse_option.value in [EndUseOptions.ELECTRICITY]:
                    f.write(f'      {model.economics.LCOE.display_name}:                      {model.economics.LCOE.value:10.2f} {model.economics.LCOE.CurrentUnits.value}\n')
                elif model.surfaceplant.enduse_option.value in [EndUseOptions.HEAT] and \
                        model.surfaceplant.plant_type.value not in [PlantType.ABSORPTION_CHILLER]:
                    f.write(f'      {model.economics.LCOH.display_name}:            {model.economics.LCOH.value:10.2f} {model.economics.LCOH.CurrentUnits.value}\n')
                elif model.surfaceplant.enduse_option.value in [EndUseOptions.HEAT] and model.surfaceplant.plant_type.value == PlantType.ABSORPTION_CHILLER:
                    f.write(f'      {model.economics.LCOC.display_name}:         {model.economics.LCOC.value:10.2f} {model.economics.LCOC.CurrentUnits.value}\n')
                elif model.surfaceplant.enduse_option.value in [EndUseOptions.COGENERATION_TOPPING_EXTRA_HEAT,
                                                              EndUseOptions.COGENERATION_BOTTOMING_EXTRA_HEAT,
                                                              EndUseOptions.COGENERATION_PARALLEL_EXTRA_HEAT,
                                                              EndUseOptions.COGENERATION_TOPPING_EXTRA_ELECTRICITY,
                                                              EndUseOptions.COGENERATION_BOTTOMING_EXTRA_ELECTRICITY,
                                                              EndUseOptions.COGENERATION_PARALLEL_EXTRA_ELECTRICITY]:
                    f.write(f'      {model.economics.LCOE.display_name}:                      {model.economics.LCOE.value:10.2f} {model.economics.LCOE.CurrentUnits.value}\n')
                    f.write(f'      {model.economics.LCOH.display_name}:           {model.economics.LCOH.value:10.2f} {model.economics.LCOH.CurrentUnits.value}\n')

                if is_sam_econ_model:
                    f.write(f'      {Outputs._field_label(econ.capex_total.display_name, 50)}{econ.capex_total.value:10.2f} {econ.capex_total.CurrentUnits.value}\n')

                f.write(f'      Number of production wells:                    {model.wellbores.nprod.value:10.0f}'+NL)
                f.write(f'      Number of injection wells:                     {model.wellbores.ninj.value:10.0f}'+NL)
                f.write(f'      Flowrate per production well:                    {model.wellbores.prodwellflowrate.value:10.1f} '  + model.wellbores.prodwellflowrate.CurrentUnits.value + NL)
                f.write(f'      {Outputs._field_label(Outputs.VERTICAL_WELL_DEPTH_OUTPUT_NAME, 49)}{model.reserv.depth.value:10.1f} ' + model.reserv.depth.CurrentUnits.value + NL)

                if model.reserv.numseg.value == 1:
                    f.write(f'      Geothermal gradient:                             {model.reserv.gradient.value[0]:10.4g} ' + model.reserv.gradient.CurrentUnits.value + NL)
                else:
                    for i in range(1, model.reserv.numseg.value):
                        f.write(f'      Segment {str(i):s}   Geothermal gradient:                    {model.reserv.gradient.value[i-1]:10.4g} ' + model.reserv.gradient.CurrentUnits.value +NL)
                        f.write(f'      Segment {str(i):s}   Thickness:                         {round(model.reserv.layerthickness.value[i-1], 10)} {model.reserv.layerthickness.CurrentUnits.value}\n')
                    f.write(f'      Segment {str(i+1):s}   Geothermal gradient:                    {model.reserv.gradient.value[i]:10.4g} ' + model.reserv.gradient.CurrentUnits.value + NL)
                if model.economics.DoCarbonCalculations.value:
                    f.write(f'      {model.economics.CarbonThatWouldHaveBeenProducedTotal.display_name}:'
                            f'                       {model.economics.CarbonThatWouldHaveBeenProducedTotal.value:10.2f}'
                            f' {model.economics.CarbonThatWouldHaveBeenProducedTotal.CurrentUnits.value}\n')

                f.write(NL)
                f.write(NL)
                f.write('                           ***ECONOMIC PARAMETERS***\n')
                f.write(NL)
                if model.economics.econmodel.value == EconomicModel.FCR:
                    f.write(f'      Economic Model = {model.economics.econmodel.value.value}\n')
                    f.write(f'      Fixed Charge Rate (FCR):                          {model.economics.FCR.value*100.0:10.2f} {model.economics.FCR.CurrentUnits.value}\n')
                elif model.economics.econmodel.value == EconomicModel.STANDARDIZED_LEVELIZED_COST:
                    f.write(f'      Economic Model = {model.economics.econmodel.value.value}\n')
                    # TODO disambiguate interest rate for all economic models - see
                    #  https://github.com/softwareengineerprogrammer/GEOPHIRES/commit/535c02d4adbeeeca553b61e9b996fccf00016529
                    f.write(f'      {model.economics.interest_rate.Name}:                                    {model.economics.interest_rate.value:10.2f} {model.economics.interest_rate.CurrentUnits.value}\n')

                elif is_sam_econ_model or model.economics.econmodel.value == EconomicModel.BICYCLE:
                    f.write(f'      Economic Model = {model.economics.econmodel.value.value}\n')

                if is_sam_econ_model:
                    sam_econ_fields: list[OutputParameter] = [
                        econ.real_discount_rate,
                        econ.nominal_discount_rate,
                        econ.wacc,
                    ]

                    for field in sam_econ_fields:
                        label = Outputs._field_label(field.Name, 49)
                        f.write(f'      {label}{field.value:10.2f} {field.CurrentUnits.value}\n')

                if econ.RITCValue.value and is_sam_econ_model:
                    # Non-SAM-EMs (inaccurately) treat ITC as a capital cost and thus are displayed in the capital
                    # costs category rather than here.
                    f.write(
                        f'      {econ.RITCValue.display_name}:                           {abs(econ.RITCValue.value):10.2f} {econ.RITCValue.CurrentUnits.value}\n')

                if not is_sam_econ_model:  # (parameter is ambiguous to the point of meaninglessness for SAM-EM)
                    acf: OutputParameter = econ.accrued_financing_during_construction_percentage
                    acf_label = Outputs._field_label(acf.display_name, 49)
                    f.write(f'      {acf_label}{acf.value:10.2f} {acf.CurrentUnits.value}\n')

                display_inflation_costs_in_economic_parameters: bool = (
                    econ.econmodel.value in [EconomicModel.BICYCLE,
                                             EconomicModel.FCR,
                                             EconomicModel.STANDARDIZED_LEVELIZED_COST]
                    and
                    econ.inflation_cost_during_construction.value != 0.
                )
                if display_inflation_costs_in_economic_parameters:
                    # Inflation cost is displayed here for economic models that don't treat inflation cost as a
                    # capital cost
                    icc: OutputParameter = econ.inflation_cost_during_construction
                    icc_label = Outputs._field_label(icc.display_name, 49)
                    f.write(f'      {icc_label}{icc.value:10.2f} {icc.CurrentUnits.value}\n')

                f.write(f'      Project lifetime:                              {model.surfaceplant.plant_lifetime.value:10.0f} {model.surfaceplant.plant_lifetime.CurrentUnits.value}\n')
                f.write(f'      Capacity factor:                                 {model.surfaceplant.utilization_factor.value * 100:10.1f} %\n')

                e_npv: OutputParameter = model.economics.ProjectNPV
                npv_field_label = Outputs._field_label(e_npv.display_name, 49)
                # TODO should use CurrentUnits instead of PreferredUnits
                f.write(f'      {npv_field_label}{e_npv.value:10.2f} {e_npv.PreferredUnits.value}\n')

                irr_output_param: OutputParameter = econ.ProjectIRR \
                    if not is_sam_econ_model else econ.after_tax_irr
                irr_field_label = Outputs._field_label(irr_output_param.display_name, 49)
                irr_display_value = f'{irr_output_param.value:10.2f}' \
                    if not math.isnan(irr_output_param.value) else 'NaN'
                f.write(f'      {irr_field_label}{irr_display_value} {irr_output_param.CurrentUnits.value}\n')

                f.write(f'      {econ.ProjectVIR.display_name}:                              {econ.ProjectVIR.value:10.2f}\n')
                f.write(f'      {econ.ProjectMOIC.display_name}:                                    {econ.ProjectMOIC.value:10.2f}\n')

                payback_period_val = model.economics.ProjectPaybackPeriod.value
                project_payback_period_display = (f'{payback_period_val:10.2f} '
                                                  f'{econ.ProjectPaybackPeriod.PreferredUnits.value}') \
                    if payback_period_val > 0.0 else 'N/A'
                project_payback_period_label = Outputs._field_label(model.economics.ProjectPaybackPeriod.display_name, 56)
                f.write(f'      {project_payback_period_label}{project_payback_period_display}\n')

                if model.surfaceplant.enduse_option.value in [EndUseOptions.COGENERATION_TOPPING_EXTRA_HEAT,
                                                              EndUseOptions.COGENERATION_BOTTOMING_EXTRA_HEAT,
                                                              EndUseOptions.COGENERATION_PARALLEL_EXTRA_HEAT,
                                                              EndUseOptions.COGENERATION_TOPPING_EXTRA_ELECTRICITY,
                                                              EndUseOptions.COGENERATION_BOTTOMING_EXTRA_ELECTRICITY,
                                                              EndUseOptions.COGENERATION_PARALLEL_EXTRA_ELECTRICITY]:
                    f.write(f'      CHP: Percent cost allocation for electrical plant: {model.economics.CAPEX_heat_electricity_plant_ratio.value*100.0:10.2f} %\n')

                if model.surfaceplant.enduse_option.value in [EndUseOptions.ELECTRICITY]:
                    f.write(f'      Estimated Jobs Created:                                 {model.economics.jobs_created.value}\n')

                f.write(NL)
                f.write('                          ***ENGINEERING PARAMETERS***\n')
                f.write(NL)
                f.write(f'      Number of Production Wells:                    {model.wellbores.nprod.value:10.0f}' + NL)
                f.write(f'      Number of Injection Wells:                     {model.wellbores.ninj.value:10.0f}' + NL)
                f.write(f'      {Outputs._field_label(Outputs.VERTICAL_WELL_DEPTH_OUTPUT_NAME, 49)}{model.reserv.depth.value:10.1f} ' + model.reserv.depth.CurrentUnits.value + NL)
                f.write(f'      Water loss rate:                                 {model.reserv.waterloss.value:10.1f} {model.reserv.waterloss.CurrentUnits.value}\n')
                f.write(f'      Pump efficiency:                                 {model.surfaceplant.pump_efficiency.value:10.1f} ' + model.surfaceplant.pump_efficiency.CurrentUnits.value + NL)
                f.write(f'      Injection temperature:                           {model.wellbores.Tinj.value:10.1f} ' + model.wellbores.Tinj.CurrentUnits.value + NL)
                if model.wellbores.rameyoptionprod.value:
                    f.write('      Production Wellbore heat transmission calculated with Ramey\'s model\n')
                    f.write(f'      Average production well temperature drop:        {np.average(model.wellbores.ProdTempDrop.value):10.1f} ' + model.wellbores.ProdTempDrop.PreferredUnits.value + NL)
                else:
                    f.write('      User-provided production well temperature drop\n')
                    f.write(f'      Constant production well temperature drop:       {model.wellbores.tempdropprod.value:10.1f} ' + model.wellbores.tempdropprod.PreferredUnits.value + NL)
                f.write(f'      Flowrate per production well:                    {model.wellbores.prodwellflowrate.value:10.1f} ' + model.wellbores.prodwellflowrate.CurrentUnits.value + NL)
                f.write(f'      {model.wellbores.injection_well_casing_inner_diameter.display_name}:                          {model.wellbores.injection_well_casing_inner_diameter.value:10.3f} {model.wellbores.injection_well_casing_inner_diameter.CurrentUnits.value}\n')
                f.write(f'      {model.wellbores.production_well_casing_inner_diameter.display_name}:                         {model.wellbores.production_well_casing_inner_diameter.value:10.3f} {model.wellbores.production_well_casing_inner_diameter.CurrentUnits.value}\n')
                f.write(f'      {model.wellbores.redrill.display_name}:                    {model.wellbores.redrill.value:10.0f}\n')
                if model.surfaceplant.enduse_option.value in [EndUseOptions.ELECTRICITY, EndUseOptions.COGENERATION_TOPPING_EXTRA_HEAT, EndUseOptions.COGENERATION_TOPPING_EXTRA_ELECTRICITY, EndUseOptions.COGENERATION_BOTTOMING_EXTRA_ELECTRICITY, EndUseOptions.COGENERATION_BOTTOMING_EXTRA_HEAT, EndUseOptions.COGENERATION_PARALLEL_EXTRA_HEAT, EndUseOptions.COGENERATION_PARALLEL_EXTRA_ELECTRICITY]:
                    f.write('      Power plant type:                                       ' + str(model.surfaceplant.plant_type.value.value) + NL)
                f.write(NL)
                f.write(NL)
                f.write('                         ***RESOURCE CHARACTERISTICS***\n')
                f.write(NL)
                f.write(f'      Maximum reservoir temperature:                   {model.reserv.Tmax.value:10.1f} {model.reserv.Tmax.CurrentUnits.value}\n')
                f.write(f'      Number of segments:                            {model.reserv.numseg.value:10.0f}\n')
                if model.reserv.numseg.value == 1:
                    f.write(f'      Geothermal gradient:                                {model.reserv.gradient.value[0]:10.4g} {model.reserv.gradient.CurrentUnits.value}\n')
                else:
                    for i in range(1, model.reserv.numseg.value):
                        f.write(f'      Segment {str(i):s}   Geothermal gradient:                    {model.reserv.gradient.value[i-1]:10.4g} {model.reserv.gradient.CurrentUnits.value}\n')
                        f.write(f'      Segment {str(i):s}   Thickness:                         {round(model.reserv.layerthickness.value[i-1], 10)} {model.reserv.layerthickness.CurrentUnits.value}\n')
                    f.write(f'      Segment {str(i+1):s}   Geothermal gradient:                    {model.reserv.gradient.value[i]:10.4g} {model.reserv.gradient.CurrentUnits.value}\n')

                f.write(NL)
                f.write(NL)
                f.write('                           ***RESERVOIR PARAMETERS***\n')
                f.write(NL)
                if model.wellbores.IsAGS.value:
                    f.write('The AGS models contain an intrinsic reservoir model that doesn\'t expose values that can be used in extensive reporting.\n')
                else:
                    f.write(f'      Reservoir Model = {model.reserv.resoption.value.display_name}\n')
                    if model.reserv.resoption.value is ReservoirModel.SINGLE_FRACTURE:
                        f.write(f'      m/A Drawdown Parameter:                                 {model.reserv.drawdp.value:.5f} ' + model.reserv.drawdp.CurrentUnits.value + NL)
                    elif model.reserv.resoption.value is ReservoirModel.ANNUAL_PERCENTAGE:
                        f.write(f'      Annual Thermal Drawdown:                                {model.reserv.drawdp.value*100:.3f} ' + model.reserv.drawdp.CurrentUnits.value + NL)
                    f.write(f'      Bottom-hole temperature:                          {model.reserv.Trock.value:10.2f} {model.reserv.Trock.CurrentUnits.value}\n')
                    if model.reserv.resoption.value in [ReservoirModel.ANNUAL_PERCENTAGE, ReservoirModel.USER_PROVIDED_PROFILE, ReservoirModel.TOUGH2_SIMULATOR]:
                        f.write('      Warning: the reservoir dimensions and thermo-physical properties \n')
                        f.write('               listed below are default values if not provided by the user.   \n')
                        f.write('               They are only used for calculating remaining heat content.  \n')
                        # TODO parse this note in GeophiresXResult

                    if model.reserv.resoption.value in [ReservoirModel.MULTIPLE_PARALLEL_FRACTURES, ReservoirModel.LINEAR_HEAT_SWEEP]:
                        f.write(f'      Fracture model = {model.reserv.fracshape.value.value}\n')
                        if model.reserv.fracshape.value == FractureShape.CIRCULAR_AREA:
                            f.write(f'      Well separation: fracture diameter:               {model.reserv.fracheightcalc.value:10.2f} ' + model.reserv.fracheight.CurrentUnits.value + NL)
                        elif model.reserv.fracshape.value == FractureShape.CIRCULAR_DIAMETER:
                            f.write(f'      Well separation: fracture diameter:               {model.reserv.fracheightcalc.value:10.2f} ' + model.reserv.fracheight.CurrentUnits.value + NL)
                        elif model.reserv.fracshape.value == FractureShape.SQUARE:
                            f.write(f'      Well separation: fracture height:                 {model.reserv.fracheightcalc.value:10.2f} ' + model.reserv.fracheight.CurrentUnits.value + NL)
                        elif model.reserv.fracshape.value == FractureShape.RECTANGULAR:
                            f.write(f'      Well separation: fracture height:                 {model.reserv.fracheightcalc.value:10.2f} ' + model.reserv.fracheight.CurrentUnits.value + NL)
                            f.write(f'      {model.reserv.fracwidthcalc.display_name}:                                             {model.reserv.fracwidthcalc.value:10.2f} {model.reserv.fracwidth.CurrentUnits.value }\n')
                        f.write(f'      {model.reserv.fracareacalc.display_name}:                                    {model.reserv.fracareacalc.value:10.2f} {model.reserv.fracarea.CurrentUnits.value}\n')
                    if model.reserv.resvoloption.value == ReservoirVolume.FRAC_NUM_SEP:
                        f.write('      Reservoir volume calculated with fracture separation and number of fractures as input\n')
                    elif model.reserv.resvoloption.value == ReservoirVolume.RES_VOL_FRAC_SEP:
                        f.write('      Number of fractures calculated with reservoir volume and fracture separation as input\n')
                    elif model.reserv.resvoloption.value == ReservoirVolume.FRAC_NUM_SEP:
                        f.write('      Fracture separation calculated with reservoir volume and number of fractures as input\n')
                    elif model.reserv.resvoloption.value == ReservoirVolume.RES_VOL_ONLY:
                        f.write('      Reservoir volume provided as input\n')
                    if model.reserv.resvoloption.value in [ReservoirVolume.FRAC_NUM_SEP, ReservoirVolume.RES_VOL_FRAC_SEP, ReservoirVolume.FRAC_NUM_SEP]:
                        frac_num_label = Outputs._field_label(model.reserv.fracnumbcalc.display_name, 56)
                        f.write(f'      {frac_num_label}{math.ceil(model.reserv.fracnumbcalc.value)}\n')
                        f.write(f'      {model.reserv.fracsepcalc.display_name}:                              {model.reserv.fracsepcalc.value:10.2f} {model.reserv.fracsep.CurrentUnits.value}\n')
                    f.write(f'      Reservoir volume:                              {model.reserv.resvolcalc.value:10.0f} {model.reserv.resvol.CurrentUnits.value}\n')

                    if model.wellbores.impedancemodelused.value:
                        # See note re: unit conversion:
                        # https://github.com/NREL/GEOPHIRES-X/blob/d51eb8d1dc8b21c7a79c4d35f296d740347658e0/src/geophires_x/WellBores.py#L1280-L1282
                        f.write(f'      Reservoir impedance:                              {model.wellbores.impedance.value/1000:10.4f} {model.wellbores.impedance.CurrentUnits.value}\n')
                    else:
                        if model.wellbores.overpressure_percentage.Provided:
                            # write the reservoir pressure as an average in the overpressure case
                            f.write(f'      {model.wellbores.average_production_reservoir_pressure.display_name}:                       {model.wellbores.average_production_reservoir_pressure.value:10.2f} {model.wellbores.average_production_reservoir_pressure.CurrentUnits.value}\n')
                        else:
                            # write the reservoir pressure as a single value
                            f.write(f'      Reservoir hydrostatic pressure:                       {model.wellbores.production_reservoir_pressure.value[0]:10.2f} ' + model.wellbores.production_reservoir_pressure.CurrentUnits.value + NL)
                        f.write(f'      Plant outlet pressure:                            {model.surfaceplant.plant_outlet_pressure.value:10.2f} ' + model.surfaceplant.plant_outlet_pressure.CurrentUnits.value + NL)
                        if model.wellbores.productionwellpumping.value:
                            f.write(f'      Production wellhead pressure:                     {model.wellbores.Pprodwellhead.value:10.2f} ' + model.wellbores.Pprodwellhead.CurrentUnits.value + NL)
                            f.write(f'      Productivity Index:                               {model.wellbores.PI.value:10.2f} ' + model.wellbores.PI.CurrentUnits.value + NL)
                        f.write(f'      Injectivity Index:                                {model.wellbores.II.value:10.2f} ' + model.wellbores.II.CurrentUnits.value + NL)

                    f.write(f'      Reservoir density:                                {model.reserv.rhorock.value:10.2f} ' + model.reserv.rhorock.CurrentUnits.value + NL)
                    if model.wellbores.rameyoptionprod.value or model.reserv.resoption.value in [ReservoirModel.MULTIPLE_PARALLEL_FRACTURES, ReservoirModel.LINEAR_HEAT_SWEEP, ReservoirModel.SINGLE_FRACTURE, ReservoirModel.TOUGH2_SIMULATOR]:
                        f.write(f'      Reservoir thermal conductivity:                   {model.reserv.krock.value:10.2f} {model.reserv.krock.CurrentUnits.value}{NL}')
                    f.write(f'      Reservoir heat capacity:                          {model.reserv.cprock.value:10.2f} ' + model.reserv.cprock.CurrentUnits.value + NL)
                    if model.reserv.resoption.value is ReservoirModel.LINEAR_HEAT_SWEEP or (model.reserv.resoption.value is ReservoirModel.TOUGH2_SIMULATOR and model.reserv.usebuiltintough2model):
                        f.write(f'      Reservoir porosity:                               {model.reserv.porrock.value*100:10.2f} ' + model.reserv.porrock.CurrentUnits.value + NL)
                    if model.reserv.resoption.value is ReservoirModel.TOUGH2_SIMULATOR and model.reserv.usebuiltintough2model:
                        f.write(f'      Reservoir permeability:                           {model.reserv.permrock.value:10.2E} ' + model.reserv.permrock.CurrentUnits.value + NL)
                        f.write(f'      Reservoir thickness:                              {model.reserv.resthickness.value:10.2f} ' + model.reserv.resthickness.CurrentUnits.value + NL)
                        f.write(f'      Reservoir width:                                  {model.reserv.reswidth.value:10.2f} ' + model.reserv.reswidth.CurrentUnits.value + NL)
                        f.write(f'      Well separation:                                  {model.wellbores.wellsep.value:10.2f} ' + model.wellbores.wellsep.CurrentUnits.value + NL)

                f.write(NL)
                f.write(NL)
                f.write('                           ***RESERVOIR SIMULATION RESULTS***\n')
                f.write(NL)
                f.write(f'      Maximum Production Temperature:                  {np.max(model.wellbores.ProducedTemperature.value):10.1f} ' + model.wellbores.ProducedTemperature.PreferredUnits.value + NL)
                f.write(f'      Average Production Temperature:                  {np.average(model.wellbores.ProducedTemperature.value):10.1f} ' + model.wellbores.ProducedTemperature.PreferredUnits.value + NL)
                f.write(f'      Minimum Production Temperature:                  {np.min(model.wellbores.ProducedTemperature.value):10.1f} ' + model.wellbores.ProducedTemperature.PreferredUnits.value + NL)
                f.write(f'      Initial Production Temperature:                  {model.wellbores.ProducedTemperature.value[0]:10.1f} ' + model.wellbores.ProducedTemperature.PreferredUnits.value + NL)
                if model.wellbores.IsAGS.value:
                    f.write('The AGS models contain an intrinsic reservoir model that doesn\'t expose values that can be used in extensive reporting.\n')
                else:
                    f.write(f'      Average Reservoir Heat Extraction:                {np.average(model.surfaceplant.HeatExtracted.value):10.2f} ' + model.surfaceplant.HeatExtracted.PreferredUnits.value + NL)
                    if model.wellbores.rameyoptionprod.value:
                        f.write('      Production Wellbore Heat Transmission Model = Ramey Model\n')
                        f.write(f'      Average Production Well Temperature Drop:        {np.average(model.wellbores.ProdTempDrop.value):10.1f} ' + model.wellbores.ProdTempDrop.PreferredUnits.value + NL)
                    else:
                        f.write(f'      Wellbore Heat Transmission Model = Constant Temperature Drop:{model.wellbores.tempdropprod.value:10.1f} ' + model.wellbores.tempdropprod.PreferredUnits.value + NL)
                    if model.wellbores.impedancemodelused.value:
                        f.write(f'      Total Average Pressure Drop:                     {np.average(model.wellbores.DPOverall.value):10.1f} ' + model.wellbores.DPOverall.PreferredUnits.value + NL)
                        f.write(f'      Average Injection Well Pressure Drop:            {np.average(model.wellbores.DPInjWell.value):10.1f} ' + model.wellbores.DPInjWell.PreferredUnits.value + NL)
                        f.write(f'      Average Reservoir Pressure Drop:                 {np.average(model.wellbores.DPReserv.value):10.1f} ' + model.wellbores.DPReserv.PreferredUnits.value + NL)
                        f.write(f'      Average Production Well Pressure Drop:           {np.average(model.wellbores.DPProdWell.value):10.1f} ' + model.wellbores.DPProdWell.PreferredUnits.value + NL)
                        f.write(f'      Average Buoyancy Pressure Drop:                  {np.average(model.wellbores.DPBouyancy.value):10.1f} ' + model.wellbores.DPBouyancy.PreferredUnits.value + NL)
                    else:
                        f.write(f'      Average Injection Well Pump Pressure Drop:       {np.average(model.wellbores.DPInjWell.value):10.1f} ' + model.wellbores.DPInjWell.PreferredUnits.value + NL)
                        if model.wellbores.productionwellpumping.value:
                            f.write(f'      Average Production Well Pump Pressure Drop:      {np.average(model.wellbores.DPProdWell.value):10.1f} ' + model.wellbores.DPProdWell.PreferredUnits.value + NL)

                f.write(NL)
                f.write(NL)
                f.write('                          ***CAPITAL COSTS (M$)***\n')
                f.write(NL)
                if not model.economics.totalcapcost.Valid:
                    f.write(f'         {model.economics.Cwell.display_name}:                 {model.economics.Cwell.value:10.2f} {model.economics.Cwell.CurrentUnits.value}\n')
                    if econ.cost_lateral_section.value > 0.0:
                        f.write(f'             Drilling and completion costs per vertical production well:   {econ.cost_one_production_well.value:10.2f} ' + econ.cost_one_production_well.CurrentUnits.value + NL)
                        f.write(f'             Drilling and completion costs per vertical injection well:    {econ.cost_one_injection_well.value:10.2f} ' + econ.cost_one_injection_well.CurrentUnits.value + NL)
                        f.write(f'             {econ.cost_per_lateral_section.Name}:       {econ.cost_per_lateral_section.value:10.2f} {econ.cost_lateral_section.CurrentUnits.value}\n')
                    elif round(econ.cost_one_production_well.value, 4) != round(econ.cost_one_injection_well.value, 4) \
                        and model.economics.cost_one_injection_well.value != -1:
                        f.write(f'             Drilling and completion costs per production well:   {econ.cost_one_production_well.value:10.2f} ' + econ.cost_one_production_well.CurrentUnits.value + NL)
                        f.write(f'             Drilling and completion costs per injection well:    {econ.cost_one_injection_well.value:10.2f} ' + econ.cost_one_injection_well.CurrentUnits.value + NL)
                    else:
                        cpw_label = Outputs._field_label(econ.drilling_and_completion_costs_per_well.display_name, 47)
                        f.write(f'         {cpw_label}{econ.drilling_and_completion_costs_per_well.value:10.2f} {econ.Cwell.CurrentUnits.value}\n')
                    f.write(f'         {econ.Cstim.display_name}:                             {econ.Cstim.value:10.2f} {econ.Cstim.CurrentUnits.value}\n')
                    f.write(f'         {econ.Cplant.display_name}:                     {econ.Cplant.value:10.2f} {econ.Cplant.CurrentUnits.value}\n')
                    if model.surfaceplant.plant_type.value == PlantType.ABSORPTION_CHILLER:
                        f.write(f'            of which Absorption Chiller Cost:           {model.economics.chillercapex.value:10.2f} ' + model.economics.Cplant.CurrentUnits.value + NL)
                    if model.surfaceplant.plant_type.value == PlantType.HEAT_PUMP:
                        f.write(f'            of which Heat Pump Cost:                    {model.economics.heatpumpcapex.value:10.2f} ' + model.economics.Cplant.CurrentUnits.value + NL)
                    if model.surfaceplant.plant_type.value == PlantType.DISTRICT_HEATING:
                        f.write(f'            of which Peaking Boiler Cost:               {model.economics.peakingboilercost.value:10.2f} ' + model.economics.peakingboilercost.CurrentUnits.value + NL)
                    f.write(f'         {model.economics.Cgath.display_name}:                  {model.economics.Cgath.value:10.2f} {model.economics.Cgath.CurrentUnits.value}\n')
                    if model.surfaceplant.piping_length.value > 0:
                        f.write(f'         {model.economics.Cpiping.display_name}:                    {model.economics.Cpiping.value:10.2f} {model.economics.Cpiping.CurrentUnits.value}\n')
                    if model.surfaceplant.plant_type.value == PlantType.DISTRICT_HEATING:
                        f.write(f'         District Heating System Cost:                  {model.economics.dhdistrictcost.value:10.2f} {model.economics.dhdistrictcost.CurrentUnits.value}\n')
                    f.write(f'         Total surface equipment costs:                 {(model.economics.Cplant.value+model.economics.Cgath.value):10.2f} ' + model.economics.Cplant.CurrentUnits.value + NL)
                    f.write(f'         {model.economics.Cexpl.display_name}:                             {model.economics.Cexpl.value:10.2f} {model.economics.Cexpl.CurrentUnits.value}\n')

                if model.economics.totalcapcost.Valid and model.wellbores.redrill.value > 0:
                    f.write(f'         Drilling and completion costs (for redrilling):{econ.Cwell.value:10.2f} {econ.Cwell.CurrentUnits.value}\n')
                    f.write(f'      Drilling and completion costs per redrilled well: {(econ.Cwell.value/(model.wellbores.nprod.value+model.wellbores.ninj.value)):10.2f} {econ.Cwell.CurrentUnits.value}\n')
                    f.write(f'         Stimulation costs (for redrilling):            {econ.Cstim.value:10.2f} {econ.Cstim.CurrentUnits.value}\n')

                if model.economics.RITCValue.value and not is_sam_econ_model:
                    # Note ITC is in ECONOMIC PARAMETERS category for SAM-EM (not capital costs)
                    f.write(f'         {econ.RITCValue.display_name}:                         {-1 * econ.RITCValue.value:10.2f} {econ.RITCValue.CurrentUnits.value}\n')

                display_occ_and_inflation_during_construction_in_capital_costs = is_sam_econ_model
                if display_occ_and_inflation_during_construction_in_capital_costs:
                    occ_label = Outputs._field_label(econ.overnight_capital_cost.display_name, 47)
                    f.write(
                        f'         {occ_label}{econ.overnight_capital_cost.value:10.2f} {econ.overnight_capital_cost.CurrentUnits.value}\n')

                display_idc_in_capital_costs = is_sam_econ_model \
                                                       and model.surfaceplant.construction_years.value > 1
                if display_idc_in_capital_costs:
                    idc_label = Outputs._field_label(econ.interest_during_construction.display_name, 47)
                    f.write(
                        f'         {idc_label}{econ.interest_during_construction.value:10.2f} {econ.interest_during_construction.CurrentUnits.value}\n')

                if display_occ_and_inflation_during_construction_in_capital_costs:
                    icc_label = Outputs._field_label(econ.inflation_cost_during_construction.display_name, 47)
                    f.write(f'         {icc_label}{econ.inflation_cost_during_construction.value:10.2f} {econ.inflation_cost_during_construction.CurrentUnits.value}\n')

                if is_sam_econ_model and econ.DoAddOnCalculations.value:
                    # Non-SAM econ models print this in Extended Economics profile
                    aoc_label = Outputs._field_label(model.addeconomics.AddOnCAPEXTotal.display_name, 47)
                    f.write(f'         {aoc_label}{model.addeconomics.AddOnCAPEXTotal.value:10.2f} {model.addeconomics.AddOnCAPEXTotal.CurrentUnits.value}\n')

                capex_param = econ.CCap if not is_sam_econ_model else econ.capex_total
                capex_label = Outputs._field_label(capex_param.display_name, 50)
                f.write(f'      {capex_label}{capex_param.value:10.2f} {capex_param.CurrentUnits.value}\n')

                if model.economics.econmodel.value == EconomicModel.FCR:
                    f.write(f'      Annualized capital costs:                         {(model.economics.CCap.value*(1+model.economics.inflrateconstruction.value)*model.economics.FCR.value):10.2f} ' + model.economics.CCap.CurrentUnits.value + NL)

                f.write(NL)
                f.write(NL)
                f.write('                ***OPERATING AND MAINTENANCE COSTS (M$/yr)***\n')
                f.write(NL)
                if not model.economics.oamtotalfixed.Valid:
                    f.write(f'         {model.economics.Coamwell.display_name}:                   {model.economics.Coamwell.value:10.2f} {model.economics.Coamwell.CurrentUnits.value}\n')
                    f.write(f'         {model.economics.Coamplant.display_name}:                 {model.economics.Coamplant.value:10.2f} {model.economics.Coamplant.CurrentUnits.value}\n')
                    f.write(f'         {model.economics.Coamwater.display_name}:                                   {model.economics.Coamwater.value:10.2f} {model.economics.Coamwater.CurrentUnits.value}\n')
                    if model.surfaceplant.plant_type.value in [PlantType.INDUSTRIAL, PlantType.ABSORPTION_CHILLER, PlantType.HEAT_PUMP, PlantType.DISTRICT_HEATING]:
                        f.write(f'         Average Reservoir Pumping Cost:                {model.economics.averageannualpumpingcosts.value:10.2f} {model.economics.averageannualpumpingcosts.CurrentUnits.value}\n')
                    if model.surfaceplant.plant_type.value == PlantType.ABSORPTION_CHILLER:
                        f.write(f'         Absorption Chiller O&M Cost:                   {model.economics.chilleropex.value:10.2f} {model.economics.chilleropex.CurrentUnits.value}\n')
                    if model.surfaceplant.plant_type.value == PlantType.HEAT_PUMP:
                        f.write(f'         Average Heat Pump Electricity Cost:            {model.economics.averageannualheatpumpelectricitycost.value:10.2f} {model.economics.averageannualheatpumpelectricitycost.CurrentUnits.value}\n')
                    if model.surfaceplant.plant_type.value == PlantType.DISTRICT_HEATING:
                        f.write(f'         Annual District Heating O&M Cost:              {model.economics.dhdistrictoandmcost.value:10.2f} {model.economics.dhdistrictoandmcost.CurrentUnits.value}\n')
                        f.write(f'         Average Annual Peaking Fuel Cost:              {model.economics.averageannualngcost.value:10.2f} {model.economics.averageannualngcost.CurrentUnits.value}\n')

                    if model.wellbores.redrill.value > 0:
                        redrill_label = Outputs._field_label(econ.redrilling_annual_cost.display_name, 47)
                        f.write(f'         {redrill_label}{econ.redrilling_annual_cost.value:10.2f} {econ.redrilling_annual_cost.CurrentUnits.value}\n')

                    if econ.DoAddOnCalculations.value and is_sam_econ_model:
                        # Non-SAM econ models print this in Extended Economics profile
                        aoc_label = Outputs._field_label(model.addeconomics.AddOnOPEXTotalPerYear.display_name, 47)
                        f.write(f'         {aoc_label}{model.addeconomics.AddOnOPEXTotalPerYear.value:10.2f} {model.addeconomics.AddOnOPEXTotalPerYear.CurrentUnits.value}\n')

                    if econ.royalty_rate.Provided:
                        royalties_label = Outputs._field_label(econ.royalties_average_annual_cost.display_name, 47)
                        f.write(f'         {royalties_label}{econ.royalties_average_annual_cost.value:10.2f} {econ.royalties_average_annual_cost.CurrentUnits.value}\n')

                    f.write(f'      {econ.Coam.display_name}:            {(econ.Coam.value + econ.averageannualpumpingcosts.value + econ.averageannualheatpumpelectricitycost.value):10.2f} {econ.Coam.CurrentUnits.value}\n')
                else:
                    f.write(f'      {econ.Coam.display_name}:            {econ.Coam.value:10.2f} {econ.Coam.CurrentUnits.value}\n')

                f.write(NL)
                f.write(NL)
                f.write('                           ***SURFACE EQUIPMENT SIMULATION RESULTS***\n')
                f.write(NL)
                if model.surfaceplant.enduse_option.value in [EndUseOptions.ELECTRICITY, EndUseOptions.COGENERATION_TOPPING_EXTRA_HEAT, EndUseOptions.COGENERATION_TOPPING_EXTRA_ELECTRICITY, EndUseOptions.COGENERATION_BOTTOMING_EXTRA_ELECTRICITY, EndUseOptions.COGENERATION_BOTTOMING_EXTRA_HEAT, EndUseOptions.COGENERATION_PARALLEL_EXTRA_HEAT, EndUseOptions.COGENERATION_PARALLEL_EXTRA_ELECTRICITY]: # there is an electricity componenent:
                    f.write(f'      Initial geofluid availability:                    {model.surfaceplant.Availability.value[0]:10.2f} ' + model.surfaceplant.Availability.PreferredUnits.value + NL)
                    f.write(f'      Maximum Total Electricity Generation:             {np.max(model.surfaceplant.ElectricityProduced.value):10.2f} ' + model.surfaceplant.ElectricityProduced.PreferredUnits.value + NL)
                    f.write(f'      Average Total Electricity Generation:             {np.average(model.surfaceplant.ElectricityProduced.value):10.2f} ' + model.surfaceplant.ElectricityProduced.PreferredUnits.value + NL)
                    f.write(f'      Minimum Total Electricity Generation:             {np.min(model.surfaceplant.ElectricityProduced.value):10.2f} ' + model.surfaceplant.ElectricityProduced.PreferredUnits.value + NL)
                    f.write(f'      Initial Total Electricity Generation:             {model.surfaceplant.ElectricityProduced.value[0]:10.2f} ' + model.surfaceplant.ElectricityProduced.PreferredUnits.value + NL)
                    f.write(f'      Maximum Net Electricity Generation:               {np.max(model.surfaceplant.NetElectricityProduced.value):10.2f} ' + model.surfaceplant.NetElectricityProduced.PreferredUnits.value + NL)
                    f.write(f'      Average Net Electricity Generation:               {np.average(model.surfaceplant.NetElectricityProduced.value):10.2f} ' + model.surfaceplant.NetElectricityProduced.PreferredUnits.value + NL)
                    f.write(f'      Minimum Net Electricity Generation:               {np.min(model.surfaceplant.NetElectricityProduced.value):10.2f} ' + model.surfaceplant.NetElectricityProduced.PreferredUnits.value + NL)
                    f.write(f'      Initial Net Electricity Generation:               {model.surfaceplant.NetElectricityProduced.value[0]:10.2f} ' + model.surfaceplant.NetElectricityProduced.PreferredUnits.value + NL)
                    f.write(f'      Average Annual Total Electricity Generation:      {np.average(model.surfaceplant.TotalkWhProduced.value/1E6):10.2f} GWh' + NL)
                    f.write(f'      Average Annual Net Electricity Generation:        {np.average(model.surfaceplant.NetkWhProduced.value/1E6):10.2f} GWh' + NL)

                    if model.wellbores.PumpingPower.value[0] > 0.0:
                        ipp_nip = model.wellbores.PumpingPower.value[0] / model.surfaceplant.NetElectricityProduced.value[0]
                        f.write(f'      Initial pumping power/net installed power:        {(ipp_nip*100):10.2f} %\n')

                if model.surfaceplant.enduse_option.value in [EndUseOptions.HEAT, PlantType.ABSORPTION_CHILLER, PlantType.HEAT_PUMP, EndUseOptions.COGENERATION_TOPPING_EXTRA_HEAT, EndUseOptions.COGENERATION_TOPPING_EXTRA_ELECTRICITY, EndUseOptions.COGENERATION_BOTTOMING_EXTRA_ELECTRICITY, EndUseOptions.COGENERATION_BOTTOMING_EXTRA_HEAT, EndUseOptions.COGENERATION_PARALLEL_EXTRA_HEAT, EndUseOptions.COGENERATION_PARALLEL_EXTRA_ELECTRICITY]: # geothermal heating component:
                    f.write(f'      Maximum Net Heat Production:                      {np.max(model.surfaceplant.HeatProduced.value):10.2f} ' + model.surfaceplant.HeatProduced.PreferredUnits.value + NL)
                    f.write(f'      Average Net Heat Production:                      {np.average(model.surfaceplant.HeatProduced.value):10.2f} ' + model.surfaceplant.HeatProduced.PreferredUnits.value + NL)
                    f.write(f'      Minimum Net Heat Production:                      {np.min(model.surfaceplant.HeatProduced.value):10.2f} ' + model.surfaceplant.HeatProduced.PreferredUnits.value + NL)
                    f.write(f'      Initial Net Heat Production:                      {model.surfaceplant.HeatProduced.value[0]:10.2f} ' + model.surfaceplant.HeatProduced.PreferredUnits.value + NL)
                    f.write(f'      Average Annual Heat Production:                   {np.average(model.surfaceplant.HeatkWhProduced.value/1E6):10.2f} GWh' + NL)

                if model.surfaceplant.plant_type.value == PlantType.HEAT_PUMP:
                    f.write(f'      Average Annual Heat Pump Electricity Use:         {np.average(model.surfaceplant.heat_pump_electricity_kwh_used.value / 1E6):10.2f} ' + 'GWh/year' + NL)
                if model.surfaceplant.plant_type.value == PlantType.ABSORPTION_CHILLER:
                    f.write(f'      Maximum Cooling Production:                       {np.max(model.surfaceplant.cooling_produced.value):10.2f} ' + model.surfaceplant.cooling_produced.PreferredUnits.value + NL)
                    f.write(f'      Average Cooling Production:                       {np.average(model.surfaceplant.cooling_produced.value):10.2f} ' + model.surfaceplant.cooling_produced.PreferredUnits.value + NL)
                    f.write(f'      Minimum Cooling Production:                       {np.min(model.surfaceplant.cooling_produced.value):10.2f} ' + model.surfaceplant.cooling_produced.PreferredUnits.value + NL)
                    f.write(f'      Initial Cooling Production:                       {model.surfaceplant.cooling_produced.value[0]:10.2f} ' + model.surfaceplant.cooling_produced.PreferredUnits.value + NL)
                    f.write(f'      Average Annual Cooling Production:                {np.average(model.surfaceplant.cooling_kWh_Produced.value / 1E6):10.2f} ' + 'GWh/year' + NL)

                if model.surfaceplant.plant_type.value == PlantType.DISTRICT_HEATING:
                    f.write(f'      Annual District Heating Demand:                   {model.surfaceplant.annual_heating_demand.value:10.2f} ' + model.surfaceplant.annual_heating_demand.PreferredUnits.value + NL)
                    f.write(f'      Maximum Daily District Heating Demand:            {np.max(model.surfaceplant.daily_heating_demand.value):10.2f} ' + model.surfaceplant.daily_heating_demand.PreferredUnits.value + NL)
                    f.write(f'      Average Daily District Heating Demand:            {np.average(model.surfaceplant.daily_heating_demand.value):10.2f} ' + model.surfaceplant.daily_heating_demand.PreferredUnits.value + NL)
                    f.write(f'      Minimum Daily District Heating Demand:            {np.min(model.surfaceplant.daily_heating_demand.value):10.2f} ' + model.surfaceplant.daily_heating_demand.PreferredUnits.value + NL)
                    f.write(f'      Maximum Geothermal Heating Production:            {np.max(model.surfaceplant.dh_geothermal_heating.value):10.2f} ' + model.surfaceplant.dh_geothermal_heating.PreferredUnits.value + NL)
                    f.write(f'      Average Geothermal Heating Production:            {np.average(model.surfaceplant.dh_geothermal_heating.value):10.2f} ' + model.surfaceplant.dh_geothermal_heating.PreferredUnits.value + NL)
                    f.write(f'      Minimum Geothermal Heating Production:            {np.min(model.surfaceplant.dh_geothermal_heating.value):10.2f} ' + model.surfaceplant.dh_geothermal_heating.PreferredUnits.value + NL)
                    f.write(f'      Maximum Peaking Boiler Heat Production:           {np.max(model.surfaceplant.dh_natural_gas_heating.value):10.2f} ' + model.surfaceplant.dh_natural_gas_heating.PreferredUnits.value + NL)
                    f.write(f'      Average Peaking Boiler Heat Production:           {np.average(model.surfaceplant.dh_natural_gas_heating.value):10.2f} ' + model.surfaceplant.dh_natural_gas_heating.PreferredUnits.value + NL)
                    f.write(f'      Minimum Peaking Boiler Heat Production:           {np.min(model.surfaceplant.dh_natural_gas_heating.value):10.2f} ' + model.surfaceplant.dh_natural_gas_heating.PreferredUnits.value + NL)

                f.write(f'      Average Pumping Power:                            {np.average(model.wellbores.PumpingPower.value):10.2f} {model.wellbores.PumpingPower.CurrentUnits.value}{NL}')

                if model.surfaceplant.heat_to_power_conversion_efficiency.value is not None:
                    hpce = model.surfaceplant.heat_to_power_conversion_efficiency
                    f.write(f'      {Outputs._field_label(hpce.Name, 50)}'
                            f'{hpce.value:10.2f} {model.surfaceplant.heat_to_power_conversion_efficiency.CurrentUnits.value}\n')

                f.write(NL)
                f.write('                            ************************************************************\n')
                f.write('                            *  HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILE  *\n')
                f.write('                            ************************************************************\n')
                if model.surfaceplant.enduse_option.value == EndUseOptions.ELECTRICITY: # only electricity
                    f.write('  YEAR       THERMAL               GEOFLUID               PUMP               NET               FIRST LAW\n')
                    f.write('             DRAWDOWN             TEMPERATURE             POWER             POWER              EFFICIENCY\n')
                    f.write('                                     (' + model.wellbores.ProducedTemperature.CurrentUnits.value+')               (' + model.wellbores.PumpingPower.CurrentUnits.value + ')              (' + model.surfaceplant.NetElectricityProduced.CurrentUnits.value + ')                  (%)\n')
                    for i in range(0, model.surfaceplant.plant_lifetime.value):
                        f.write('  {0:2.0f}         {1:8.4f}              {2:8.2f}             {3:8.4f}          {4:8.4f}              {5:8.4f}'.format(i+1,
                                                model.wellbores.ProducedTemperature.value[i*model.economics.timestepsperyear.value]/model.wellbores.ProducedTemperature.value[0],
                                                                        model.wellbores.ProducedTemperature.value[i*model.economics.timestepsperyear.value],
                                                                                                        model.wellbores.PumpingPower.value[i*model.economics.timestepsperyear.value],
                                                                                                                            model.surfaceplant.NetElectricityProduced.value[i*model.economics.timestepsperyear.value],
                                                                                                                                                        model.surfaceplant.FirstLawEfficiency.value[i*model.economics.timestepsperyear.value]*100)+NL)
                elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT and model.surfaceplant.plant_type.value not in [PlantType.HEAT_PUMP, PlantType.DISTRICT_HEATING, PlantType.ABSORPTION_CHILLER]: # only direct-use
                    f.write('  YEAR       THERMAL               GEOFLUID               PUMP               NET\n')
                    f.write('             DRAWDOWN             TEMPERATURE             POWER              HEAT\n')
                    f.write('                                   (deg C)                (MW)               (MW)\n')
                    for i in range(0, model.surfaceplant.plant_lifetime.value):
                        f.write('  {0:2.0f}         {1:8.4f}              {2:8.2f}             {3:8.4f}          {4:8.4f}'.format(i,
                                                model.wellbores.ProducedTemperature.value[i*model.economics.timestepsperyear.value]/model.wellbores.ProducedTemperature.value[0],
                                                                        model.wellbores.ProducedTemperature.value[i*model.economics.timestepsperyear.value],
                                                                                                        model.wellbores.PumpingPower.value[i*model.economics.timestepsperyear.value],
                                                                                                                                model.surfaceplant.HeatProduced.value[i*model.economics.timestepsperyear.value])+NL)

                elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT and model.surfaceplant.plant_type.value in [PlantType.HEAT_PUMP]: # heat pump
                    f.write('  YEAR         THERMAL              GEOFLUID               PUMP               NET             HEAT PUMP\n')
                    f.write('               DRAWDOWN            TEMPERATURE             POWER              HEAT         ELECTRICITY USE\n')
                    f.write('                                    (deg C)                (MWe)              (MWt)             (MWe)\n')
                    for i in range(0, model.surfaceplant.plant_lifetime.value):
                        f.write('  {0:2.0f}          {1:8.4f}             {2:8.2f}              {3:8.4f}           {4:8.4f}          {5:8.4f}'.format(i,
                                                                                                                                                      model.wellbores.ProducedTemperature.value[i*model.economics.timestepsperyear.value] / model.wellbores.ProducedTemperature.value[0],
                                                                                                                                                      model.wellbores.ProducedTemperature.value[i*model.economics.timestepsperyear.value],
                                                                                                                                                      model.wellbores.PumpingPower.value[i*model.economics.timestepsperyear.value],
                                                                                                                                                      model.surfaceplant.HeatProduced.value[i*model.economics.timestepsperyear.value], model.surfaceplant.heat_pump_electricity_used.value[i * model.economics.timestepsperyear.value]) + NL)

                elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT and model.surfaceplant.plant_type.value in [PlantType.DISTRICT_HEATING]: # district heating
                    f.write('  YEAR         THERMAL              GEOFLUID               PUMP              GEOTHERMAL\n')
                    f.write('               DRAWDOWN            TEMPERATURE             POWER            HEAT OUTPUT\n')
                    f.write('                                    (deg C)                (MWe)               (MWt)\n')
                    for i in range(0, model.surfaceplant.plant_lifetime.value):
                        f.write('  {0:2.0f}          {1:8.4f}             {2:8.2f}              {3:8.4f}            {4:8.4f}'.format(i,
                                                model.wellbores.ProducedTemperature.value[i*model.economics.timestepsperyear.value]/model.wellbores.ProducedTemperature.value[0],
                                                                        model.wellbores.ProducedTemperature.value[i*model.economics.timestepsperyear.value],
                                                                                                        model.wellbores.PumpingPower.value[i*model.economics.timestepsperyear.value],
                                                                                                                                model.surfaceplant.HeatProduced.value[i*model.economics.timestepsperyear.value])+NL)

                elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT and model.surfaceplant.plant_type.value in [PlantType.ABSORPTION_CHILLER]: # absorption chiller
                    f.write('  YEAR         THERMAL              GEOFLUID               PUMP               NET              NET\n')
                    f.write('               DRAWDOWN            TEMPERATURE             POWER              HEAT             COOLING\n')
                    f.write('                                    (deg C)                (MWe)              (MWt)            (MWt)\n')
                    for i in range(0, model.surfaceplant.plant_lifetime.value):
                        f.write('  {0:2.0f}          {1:8.4f}             {2:8.2f}              {3:8.4f}           {4:8.4f}         {5:8.4f}'.format(i,
                                                                                                                                                     model.wellbores.ProducedTemperature.value[i*model.economics.timestepsperyear.value] / model.wellbores.ProducedTemperature.value[0],
                                                                                                                                                     model.wellbores.ProducedTemperature.value[i*model.economics.timestepsperyear.value],
                                                                                                                                                     model.wellbores.PumpingPower.value[i*model.economics.timestepsperyear.value],
                                                                                                                                                     model.surfaceplant.HeatProduced.value[i*model.economics.timestepsperyear.value], model.surfaceplant.cooling_produced.value[i * model.economics.timestepsperyear.value], ) + NL)

                elif model.surfaceplant.enduse_option.value in [EndUseOptions.COGENERATION_TOPPING_EXTRA_HEAT, EndUseOptions.COGENERATION_TOPPING_EXTRA_ELECTRICITY, EndUseOptions.COGENERATION_BOTTOMING_EXTRA_ELECTRICITY, EndUseOptions.COGENERATION_BOTTOMING_EXTRA_HEAT, EndUseOptions.COGENERATION_PARALLEL_EXTRA_HEAT, EndUseOptions.COGENERATION_PARALLEL_EXTRA_ELECTRICITY]:  # co-gen
                    f.write('  YEAR     THERMAL             GEOFLUID             PUMP             NET              NET             FIRST LAW\n')
                    f.write('           DRAWDOWN           TEMPERATURE           POWER           POWER             HEAT            EFFICIENCY\n')
                    f.write('                                (deg C)             (MW)            (MW)              (MW)               (%)\n')
                    for i in range(0, model.surfaceplant.plant_lifetime.value):
                        f.write('  {0:2.0f}       {1:8.4f}            {2:8.2f}           {3:8.4f}        {4:8.4f}            {5:8.4f}             {6:8.4f}'.format(i,
                                                model.wellbores.ProducedTemperature.value[i*model.economics.timestepsperyear.value]/model.wellbores.ProducedTemperature.value[0],
                                                                        model.wellbores.ProducedTemperature.value[i*model.economics.timestepsperyear.value],
                                                                                                    model.wellbores.PumpingPower.value[i*model.economics.timestepsperyear.value],
                                                                                                                            model.surfaceplant.NetElectricityProduced.value[i*model.economics.timestepsperyear.value],
                                                                                                                                                    model.surfaceplant.HeatProduced.value[i*model.economics.timestepsperyear.value],
                                                                                                                                                                                model.surfaceplant.FirstLawEfficiency.value[i*model.economics.timestepsperyear.value]*100)+NL)
                f.write(NL)
                f.write(NL)

                f.write('                              *******************************************************************\n')
                f.write('                              *  ANNUAL HEATING, COOLING AND/OR ELECTRICITY PRODUCTION PROFILE  *\n')
                f.write('                              *******************************************************************\n')
                if model.surfaceplant.enduse_option.value == EndUseOptions.ELECTRICITY:  # only electricity
                    f.write('  YEAR             ELECTRICITY                   HEAT                RESERVOIR            PERCENTAGE OF\n')
                    f.write('                    PROVIDED                   EXTRACTED            HEAT CONTENT        TOTAL HEAT MINED\n')
                    f.write('                   (GWh/year)                  (GWh/year)            (10^15 J)                 (%)\n')
                    for i in range(0, model.surfaceplant.plant_lifetime.value):
                        f.write('  {0:2.0f}              {1:8.1f}                    {2:8.1f}              {3:8.2f}               {4:8.2f}'.format(i+1,
                                                model.surfaceplant.NetkWhProduced.value[i]/1E6,
                                                                            model.surfaceplant.HeatkWhExtracted.value[i]/1E6,
                                                                                                    model.surfaceplant.RemainingReservoirHeatContent.value[i],
                                                                                                                            (model.reserv.InitialReservoirHeatContent.value-model.surfaceplant.RemainingReservoirHeatContent.value[i])*100/model.reserv.InitialReservoirHeatContent.value)+NL)
                elif model.surfaceplant.plant_type.value == PlantType.ABSORPTION_CHILLER: # absorption chiller
                    f.write('  YEAR              COOLING                 HEAT                RESERVOIR            PERCENTAGE OF\n')
                    f.write('                    PROVIDED              EXTRACTED            HEAT CONTENT        TOTAL HEAT MINED\n')
                    f.write('                   (GWh/year)             (GWh/year)            (10^15 J)                 (%)\n')
                    for i in range(0, model.surfaceplant.plant_lifetime.value):
                        f.write('  {0:2.0f}              {1:8.1f}               {2:8.1f}              {3:8.2f}               {4:8.2f}'.format(i + 1,
                                                                                                                                              model.surfaceplant.cooling_kWh_Produced.value[i] / 1E6,
                                                                                                                                              model.surfaceplant.HeatkWhExtracted.value[i] / 1E6,
                                                                                                                                              model.surfaceplant.RemainingReservoirHeatContent.value[i],
                                                                                                                                              (model.reserv.InitialReservoirHeatContent.value-model.surfaceplant.RemainingReservoirHeatContent.value[i]) * 100 / model.reserv.InitialReservoirHeatContent.value)+NL)

                elif model.surfaceplant.plant_type.value == PlantType.HEAT_PUMP: # heat pump
                    f.write('  YEAR              HEATING             RESERVOIR HEAT          HEAT PUMP          RESERVOIR           PERCENTAGE OF\n')
                    f.write('                    PROVIDED              EXTRACTED          ELECTRICITY USE      HEAT CONTENT        TOTAL HEAT MINED\n')
                    f.write('                   (GWh/year)             (GWh/year)           (GWh/year)           (10^15 J)                (%)\n')
                    for i in range(0, model.surfaceplant.plant_lifetime.value):
                        f.write('  {0:2.0f}              {1:8.1f}               {2:8.1f}             {3:8.2f}             {4:8.2f}              {5:8.2f}'.format(i + 1,
                                                                                                                                                                 model.surfaceplant.HeatkWhProduced.value[i] / 1E6,
                                                                                                                                                                 model.surfaceplant.HeatkWhExtracted.value[i] / 1E6, model.surfaceplant.heat_pump_electricity_kwh_used.value[i] / 1E6,
                                                                                                                                                                 model.surfaceplant.RemainingReservoirHeatContent.value[i],
                                                                                                                                                                 (model.reserv.InitialReservoirHeatContent.value-model.surfaceplant.RemainingReservoirHeatContent.value[i]) * 100 / model.reserv.InitialReservoirHeatContent.value)+NL)

                elif model.surfaceplant.enduse_option.value in [EndUseOptions.COGENERATION_TOPPING_EXTRA_HEAT, EndUseOptions.COGENERATION_TOPPING_EXTRA_ELECTRICITY, EndUseOptions.COGENERATION_BOTTOMING_EXTRA_ELECTRICITY, EndUseOptions.COGENERATION_BOTTOMING_EXTRA_HEAT, EndUseOptions.COGENERATION_PARALLEL_EXTRA_HEAT, EndUseOptions.COGENERATION_PARALLEL_EXTRA_ELECTRICITY]: #co-gen
                    f.write('  YEAR             HEAT                 ELECTRICITY                HEAT              RESERVOIR        PERCENTAGE OF\n')
                    f.write('                  PROVIDED               PROVIDED                EXTRACTED          HEAT CONTENT    TOTAL HEAT MINED\n')
                    f.write('                 (GWh/year)             (GWh/year)               (GWh/year)          (10^15 J)           (%)\n')
                    for i in range(0, model.surfaceplant.plant_lifetime.value):
                        f.write('  {0:2.0f}            {1:8.1f}               {2:8.1f}                  {3:8.2f}            {4:8.2f}             {5:8.2f}'.format(i+1,
                                            model.surfaceplant.HeatkWhProduced.value[i]/1E6,
                                                                        model.surfaceplant.NetkWhProduced.value[i]/1E6,
                                                                                                    model.surfaceplant.HeatkWhExtracted.value[i]/1E6,
                                                                                                                            model.surfaceplant.RemainingReservoirHeatContent.value[i],
                                                                                                                                                (model.reserv.InitialReservoirHeatContent.value-model.surfaceplant.RemainingReservoirHeatContent.value[i])*100/model.reserv.InitialReservoirHeatContent.value)+NL)

                elif model.surfaceplant.plant_type.value in [PlantType.DISTRICT_HEATING]: # district-heating
                    f.write('  YEAR           GEOTHERMAL          PEAKING BOILER       RESERVOIR HEAT          RESERVOIR         PERCENTAGE OF\n')
                    f.write('              HEATING PROVIDED      HEATING PROVIDED        EXTRACTED            HEAT CONTENT     TOTAL HEAT MINED\n')
                    f.write('                 (GWh/year)            (GWh/year)           (GWh/year)            (10^15 J)              (%)\n')
                    for i in range(0, model.surfaceplant.plant_lifetime.value):
                        f.write('  {0:2.0f}            {1:8.1f}              {2:8.1f}              {3:8.2f}             {4:8.2f}            {5:8.2f}'.format(i + 1,
                                                                                                                                                             model.surfaceplant.HeatkWhProduced.value[i] / 1E6,
                                                                                                                                                             model.surfaceplant.annual_ng_demand.value[i] / 1E3,
                                                                                                                                                             model.surfaceplant.HeatkWhExtracted.value[i] / 1E6,
                                                                                                                                                             model.surfaceplant.RemainingReservoirHeatContent.value[i],
                                                                                                                                                             (model.reserv.InitialReservoirHeatContent.value-model.surfaceplant.RemainingReservoirHeatContent.value[i]) * 100 / model.reserv.InitialReservoirHeatContent.value)+NL)
                elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT: # only direct-use
                    f.write('  YEAR               HEAT                       HEAT                RESERVOIR            PERCENTAGE OF\n')
                    f.write('                    PROVIDED                   EXTRACTED            HEAT CONTENT        TOTAL HEAT MINED\n')
                    f.write('                   (GWh/year)                  (GWh/year)            (10^15 J)                 (%)\n')
                    for i in range(0, model.surfaceplant.plant_lifetime.value):
                        f.write('  {0:2.0f}              {1:8.1f}                    {2:8.1f}              {3:8.2f}               {4:8.2f}'.format(i+1,
                                                model.surfaceplant.HeatkWhProduced.value[i]/1E6,
                                                                            model.surfaceplant.HeatkWhExtracted.value[i]/1E6,
                                                                                                    model.surfaceplant.RemainingReservoirHeatContent.value[i],
                                                                                                                            (model.reserv.InitialReservoirHeatContent.value-model.surfaceplant.RemainingReservoirHeatContent.value[i])*100/model.reserv.InitialReservoirHeatContent.value)+NL)

                if not is_sam_econ_model:
                    self.write_revenue_and_cashflow_profile_output(model, f)

                if is_sam_econ_model:
                    f.write(self.get_sam_cash_flow_profile_output(model))

                # if we are dealing with overpressure and two different reservoirs, show a table reporting the values
                if model.wellbores.overpressure_percentage.Provided:
                    f.write(NL)
                    f.write('                            ***************************************\n')
                    f.write('                            *  RESERVOIR POWER REQUIRED PROFILES  *\n')
                    f.write('                            ***************************************\n')
                    f.write('  YEAR     PROD PUMP     INJECT PUMP     TOTAL PUMP\n')
                    f.write('             POWER          POWER           POWER\n')
                    f.write(
                        '             (' + model.wellbores.PumpingPowerProd.CurrentUnits.value + ')           (' + model.wellbores.PumpingPowerInj.CurrentUnits.value + ')            (' + model.surfaceplant.NetElectricityProduced.CurrentUnits.value + ')                  \n')
                    for i in range(0, model.surfaceplant.plant_lifetime.value):
                        f.write('  {0:2.0f}     {1:8.4f}        {2:8.4f}       {3:8.4f}'.format(i + 1,
                                                                                                model.wellbores.PumpingPowerProd.value[
                                                                                                    i * model.economics.timestepsperyear.value],
                                                                                                model.wellbores.PumpingPowerInj.value[
                                                                                                    i * model.economics.timestepsperyear.value],
                                                                                                model.wellbores.PumpingPower.value[
                                                                                                    i * model.economics.timestepsperyear.value]))
                        f.write(NL)
                    f.write(NL)

            addon_df = pd.DataFrame()
            addon_results = []
            extended_economics_header_printed = False
            if model.economics.DoAddOnCalculations.value and not is_sam_econ_model:
                # SAM econ models incorporate add-on economics into main economics, not as separate extended economics.
                addon_df, addon_results = model.addoutputs.PrintOutputs(model)
                extended_economics_header_printed = True

            if econ.royalty_rate.Provided:
                with open(self.output_file, 'a', encoding='UTF-8') as f_:
                    if not extended_economics_header_printed:
                        self._print_extended_economics_header(f_)

                    for royalty_output in [
                        econ.royalty_holder_npv,
                        econ.royalty_holder_annual_revenue,
                        econ.royalty_holder_total_revenue
                    ]:
                        label = Outputs._field_label(royalty_output.display_name, 49)
                        f_.write(
                            f'      {label}{royalty_output.value:10.2f} {royalty_output.CurrentUnits.value}\n')

            sdac_df = pd.DataFrame()
            sdac_results = []
            if model.economics.DoSDACGTCalculations.value:
                sdac_df, sdac_results = model.sdacgtoutputs.PrintOutputs(model)

        except BaseException as ex:
            tb = sys.exc_info()[2]
            msg = 'Error: GEOPHIRES Failed to write the output file. Exiting....Line %i' % tb.tb_lineno
            print(str(ex))
            print(msg)
            model.logger.critical(str(ex))
            model.logger.critical(msg)
            raise RuntimeError(msg) from ex

        print_outputs_rich(
            self.text_output_file,
            self.html_output_file,
            model,
            sdac_results,
            addon_results,
            sdac_df,
            addon_df
        )

        model.logger.info(f'Complete {__class__!s}: {sys._getframe().f_code.co_name}')

    # noinspection PyMethodMayBeStatic
    def write_revenue_and_cashflow_profile_output(self, model, f):
        econ: Economics = model.economics

        f.write(NL)
        f.write(NL)
        f.write('                             ********************************\n')
        f.write('                             *  REVENUE & CASHFLOW PROFILE  *\n')
        f.write('                             ********************************\n')
        f.write(
            'Year            Electricity             |            Heat                  |           Cooling                 |         Carbon                    |          Project' + NL)
        f.write(
            'Since     Price   Ann. Rev.  Cumm. Rev. |   Price   Ann. Rev.   Cumm. Rev. |  Price   Ann. Rev.   Cumm. Rev.   |   Price   Ann. Rev.   Cumm. Rev.  | OPEX    Net Rev.      Net Cashflow' + NL)

        def o(output_param: OutputParameter):
            # TODO generalize this and/or FIXME make it unnecessary
            if output_param.Name in econ.OutputParameterDict:
                return econ.OutputParameterDict[output_param.Name]
            else:
                return output_param

        f.write('Start    ('
                + o(econ.ElecPrice).CurrentUnits.value +
                ')(' + o(econ.ElecRevenue).CurrentUnits.value +
                ') (' + o(econ.ElecCummRevenue).CurrentUnits.value +
                ')    |(' + o(econ.HeatPrice).CurrentUnits.value +
                ') (' + o(econ.HeatRevenue).CurrentUnits.value +
                ')    (' + o(econ.HeatCummRevenue).CurrentUnits.value +
                ')   |(' + o(econ.CoolingPrice).CurrentUnits.value +
                ') (' + o(econ.CoolingRevenue).CurrentUnits.value +
                ')    (' + o(econ.CoolingCummRevenue).CurrentUnits.value +
                ')    |(' + o(econ.CarbonPrice).CurrentUnits.value +
                ')    (' + o(econ.CarbonRevenue).CurrentUnits.value +
                ')    (' + o(econ.CarbonCummCashFlow).CurrentUnits.value +
                ')    |(' + o(econ.Coam).CurrentUnits.value +
                ') (' + o(econ.TotalRevenue).CurrentUnits.value +
                ')    (' + o(econ.TotalCummRevenue).CurrentUnits.value + ')\n')
        f.write(
            '________________________________________________________________________________________________________________________________________________________________________________________' + NL)
        # running years...
        for ii in range(0, (
            model.surfaceplant.construction_years.value + model.surfaceplant.plant_lifetime.value), 1):
            if ii < model.surfaceplant.construction_years.value:
                opex = 0.0  # zero out the OPEX during construction years
            else:
                opex = o(econ.Coam).value
            f.write(
                f'{ii:3.0f}     {o(econ.ElecPrice).value[ii]:5.2f}          {o(econ.ElecRevenue).value[ii]:5.2f}  {o(econ.ElecCummRevenue).value[ii]:5.2f}     |   {o(econ.HeatPrice).value[ii]:5.2f}    {o(econ.HeatRevenue).value[ii]:5.2f}        {o(econ.HeatCummRevenue).value[ii]:5.2f}    |   {o(econ.CoolingPrice).value[ii]:5.2f}    {o(econ.CoolingRevenue).value[ii]:5.2f}        {o(econ.CoolingCummRevenue).value[ii]:5.2f}     |   {o(econ.CarbonPrice).value[ii]:5.2f}    {o(econ.CarbonRevenue).value[ii]:5.2f}        {o(econ.CarbonCummCashFlow).value[ii]:5.2f}     | {opex:5.2f}     {o(econ.TotalRevenue).value[ii]:5.2f}     {o(econ.TotalCummRevenue).value[ii]:5.2f}\n')
        f.write(NL)

    # noinspection PyMethodMayBeStatic
    def get_sam_cash_flow_profile_output(self, model):
        ret = '\n'
        ret += '                            ***************************\n'
        ret += '                            *  SAM CASH FLOW PROFILE  *\n'
        ret += '                            ***************************\n'

        cfp_o: str = get_sam_cash_flow_profile_tabulated_output(model)

        # Ideally the separator line would be exactly the print width of the widest column, but the actual print width
        # of tabs varies (at least according to https://stackoverflow.com/a/7643592). 4 spaces seems to be the minimum
        # number that results in a separator line at least as wide as the table (narrower would be unsightly).
        spaces_per_tab = 4

        # The tabulate library has native separating line functionality (per https://pypi.org/project/tabulate/) but
        # I wasn't able to get it to replicate the formatting as coded below.
        separator_line = len(cfp_o.split('\n')[0].replace('\t', ' ' * spaces_per_tab)) * '-'

        ret += separator_line + '\n'
        ret += cfp_o
        ret += '\n' + separator_line

        ret += '\n'

        return ret

    def _print_extended_economics_header(self, f_output_file: TextIOWrapper | None = None) -> None:
        """
        Header may be printed by either OutputsAddOns, or parent class if royalties are calculated and add-ons are not.
        """

        close_f = False
        if f_output_file is None:
            f_output_file = open(self.output_file, 'a', encoding='UTF-8')
            close_f = True

        f_output_file.write(NL)
        f_output_file.write(NL)
        f_output_file.write("                                ***EXTENDED ECONOMICS***\n")
        f_output_file.write(NL)

        if close_f:
            f_output_file.close()

    @staticmethod
    def _field_label(field_name: str, print_width_before_value: int) -> str:
        return f'{field_name}:{" " * (print_width_before_value - len(field_name) - 1)}'

