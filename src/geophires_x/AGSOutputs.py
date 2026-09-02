import datetime
import time
import sys
import traceback

import geophires_x

from geophires_x.OptionList import EndUseOptions, EconomicModel

import geophires_x.Model as Model
import geophires_x.Outputs as Outputs
import numpy as np

from geophires_x.Units import TemperatureUnit

NL = "\n"


class AGSOutputs(Outputs.Outputs):
    """
    Handles the display of AGS data
    """

    def PrintOutputs(self, model: Model):
        """
        Print the outputs to the screen and to the output file
        :param model: the model object
        :type model: :class:`~geophires_x.Model.Model`
        :return: None
        """
        model.logger.info(f'Init {str(__class__)}: {sys._getframe().f_code.co_name}')

        self._convert_units(model)

        # ---------------------------------------
        # write results to output file and screen
        # ---------------------------------------
        try:
            if model.wellbores.IsAGS:  # do a classical output display
                import scipy
                # Need to do some interpolating to get the arrays to be the right size for output
                if len(model.wellbores.PumpingPower.value) != len(model.wellbores.ProducedTemperature.value):
                    f = scipy.interpolate.interp1d(np.arange(0, len(model.wellbores.PumpingPower.value)),
                                                   model.wellbores.PumpingPower.value, fill_value="extrapolate")
                    model.wellbores.PumpingPower.value = f(np.arange(0, len(model.wellbores.ProducedTemperature.value), 1.0))
                if model.surfaceplant.enduse_option.value is not EndUseOptions.HEAT:
                    if len(model.wellbores.PumpingPower.value) != len(model.wellbores.ProducedTemperature.value):
                        f = scipy.interpolate.interp1d(np.arange(0, len(model.wellbores.PumpingPower.value)),
                                                       model.wellbores.PumpingPower.value, fill_value="extrapolate")
                        model.wellbores.PumpingPower.value = f(np.arange(0, len(model.wellbores.ProducedTemperature.value), 1.0))

                    if len(model.surfaceplant.NetElectricityProduced.value) != len(model.wellbores.ProducedTemperature.value):
                        f = scipy.interpolate.interp1d(np.arange(0, len(model.surfaceplant.NetElectricityProduced.value)),
                                                       model.surfaceplant.NetElectricityProduced.value, fill_value="extrapolate")
                        model.surfaceplant.NetElectricityProduced.value = f(np.arange(0, len(model.wellbores.ProducedTemperature.value), 1.0))

            if model.economics.econmodel.value is not EconomicModel.CLGS:
                super().PrintOutputs(model)
            else:
                with open(self.output_file, 'w', encoding='UTF-8') as f:
                    f.write('                               *****************\n')
                    f.write('                               ***CASE REPORT***\n')
                    f.write('                               *****************\n')
                    f.write(NL)
                    f.write("Simulation Metadata\n")
                    f.write("----------------------\n")
                    f.write(f' GEOPHIRES Version: {geophires_x.__version__}\n')
                    f.write(" Simulation Date: " + datetime.datetime.now().strftime("%Y-%m-%d\n"))
                    f.write(" Simulation Time:  " + datetime.datetime.now().strftime("%H:%M\n"))
                    f.write(" Calculation Time: " + "{0:10.3f}".format((time.time() - model.tic)) + " sec\n")

                    f.write(NL)
                    f.write(NL)
                    f.write('                           ***AGS/CLGS STYLE OUTPUT***\n')
                    f.write(NL)
                    f.write('### Configuration ###' + NL)
                    f.write('      End-Use: ' + str(model.surfaceplant.End_use.value) + NL)
                    f.write('      Fluid: ' + str(model.wellbores.Fluid.value.value) + NL)
                    f.write('      Design: ' + str(model.wellbores.Configuration.value.value) + NL)

                    # Print conditions
                    f.write(f"      Flow rate:                                             " + "{0:.1f}".format((
                        model.wellbores.prodwellflowrate.value)) + " " + model.wellbores.prodwellflowrate.CurrentUnits.value + NL)
                    f.write("      Lateral Length:                                      " + str(round(
                        model.wellbores.Nonvertical_length.value)) + " " + model.wellbores.Nonvertical_length.CurrentUnits.value + NL)
                    f.write("      Vertical Depth:                                      " + str(
                        round(model.reserv.InputDepth.value)) + " " + model.reserv.InputDepth.CurrentUnits.value + NL)
                    f.write(f"      Geothermal Gradient:                                   " + "{0:.4f}".format(
                        (model.reserv.gradient.value[0])) + " " + model.reserv.gradient.CurrentUnits.value + NL)
                    f.write(f"      Wellbore Diameter:                                      " + "{0:.4f}".format((
                        model.wellbores.prodwelldiam.value)) + " " + model.wellbores.prodwelldiam.CurrentUnits.value + NL)
                    f.write(f"      Injection Temperature:                                 " + "{0:.1f}".format(
                        model.wellbores.Tinj.value) + " " + TemperatureUnit.CELSIUS.value + NL)
                    f.write(f"      Thermal Conductivity:                                   " + "{0:.2f}".format(
                        model.reserv.krock.value) + " " + model.reserv.krock.CurrentUnits.value + NL)

                    f.write(" ")
                    f.write('### Reservoir Simulation Results ###' + NL)
                    f.write(f"      Average Production Temperature:                       " + "{0:.1f}".format((
                        model.surfaceplant.AveProductionTemperature.value)) + " " + model.surfaceplant.AveProductionTemperature.CurrentUnits.value + NL)
                    f.write(f"      Average Production Pressure:                          " + "{0:.1f}".format((
                        model.surfaceplant.AveProductionPressure.value)) + " " + model.surfaceplant.AveProductionPressure.CurrentUnits.value + NL)
                    f.write(f"      Average Heat Production:                             " + "{0:.1f}".format((
                        model.surfaceplant.AveInstHeatProduction.value)) + " " + model.surfaceplant.AveInstHeatProduction.CurrentUnits.value + NL)
                    f.write(f"      First Year Heat Production:                         " + "{0:.1f}".format((
                        model.surfaceplant.FirstYearHeatProduction.value / 1e3)) + " " + model.surfaceplant.FirstYearHeatProduction.CurrentUnits.value + NL)

                    # Print results for heating or electricity
                    if model.surfaceplant.End_use == EndUseOptions.ELECTRICITY:
                        f.write(f"      Average Net Electricity Production:                   " + "{0:.1f}".format((
                            model.surfaceplant.AveInstNetElectricityProduction.value)) + " " + model.surfaceplant.AveInstNetElectricityProduction.CurrentUnits.value + NL)
                        f.write(f"      First Year Electricity Production:                   " + "{0:.1f}".format((
                            model.surfaceplant.FirstYearElectricityProduction.value / 1e3)) + " " + model.surfaceplant.FirstYearElectricityProduction.CurrentUnits.value + NL)

                    f.write(" ")
                    f.write('### Cost Results ###' + NL)
                    f.write(f"      Total CAPEX:                                           " + "{0:.1f}".format(
                        model.economics.CCap.value) + " " + model.economics.CCap.CurrentUnits.value + NL)
                    f.write(f"      Drilling Cost:                                         " + "{0:.1f}".format(
                        model.economics.Cwell.value) + " " + model.economics.Cwell.CurrentUnits.value + NL)
                    f.write(f"      Surface Plant Cost:                                     " + "{0:.1f}".format(
                        model.economics.Cplant.value) + " " + model.economics.Cplant.CurrentUnits.value + NL)
                    f.write(f"      OPEX:                                                  " + "{0:.1f}".format(
                        model.economics.Coam.value) + " " + model.economics.Coam.CurrentUnits.value + NL)
                    if model.surfaceplant.End_use == EndUseOptions.HEAT:
                        f.write(f"      LCOH:                                                 " + "{0:.1f}".format(
                            model.economics.LCOH.value) + " " + model.economics.LCOH.CurrentUnits.value + NL)
                    else:
                        f.write(f"      LCOE:                                                 " + "{0:.1f}".format(
                            model.economics.LCOE.value) + " " + model.economics.LCOE.CurrentUnits.value + NL)

                    f.write(NL)
                    f.write('                                        ******************************\n')
                    f.write('                                        *  POWER GENERATION PROFILE  *\n')
                    f.write('                                        ******************************\n')
                    if model.surfaceplant.enduse_option.value == EndUseOptions.ELECTRICITY:  # only electricity
                        pump_units = f'({model.wellbores.PumpingPower.CurrentUnits.value})'
                        net_units = f'({model.surfaceplant.NetElectricityProduced.CurrentUnits.value})'
                        f.write(
                            '  YEAR       THERMAL               GEOFLUID               PUMP               NET               FIRST LAW\n')
                        f.write(
                            '             DRAWDOWN             TEMPERATURE             POWER             POWER              EFFICIENCY\n')
                        f.write(
                            '                                     '
                            f'({model.wellbores.ProducedTemperature.CurrentUnits.value})'
                            f'{pump_units:>19}{net_units:>18}' + f'{"(%)":>21}' + NL)
                        for i in range(0, model.surfaceplant.plant_lifetime.value):
                            f.write(
                                '  {0:2.0f}         {1:8.4f}              {2:8.2f}             {3:8.4f}          {4:8.4f}              {5:8.4f}'.format(
                                    i + 1,
                                    model.wellbores.ProducedTemperature.value[i * model.economics.timestepsperyear.value] /\
                                    model.wellbores.ProducedTemperature.value[0],
                                    model.wellbores.ProducedTemperature.value[i],
                                    model.wellbores.PumpingPower.value[i],
                                    model.surfaceplant.NetElectricityProduced.value[i],
                                    model.surfaceplant.FirstLawEfficiency.value[i] * 100) + NL)
                    elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT:  # only direct-use
                        f.write('  YEAR       THERMAL               GEOFLUID               PUMP               NET\n')
                        f.write('             DRAWDOWN             TEMPERATURE             POWER              HEAT\n')
                        pump_units = f'({model.wellbores.PumpingPower.CurrentUnits.value})'
                        heat_units = f'({model.surfaceplant.HeatProduced.CurrentUnits.value})'
                        f.write('                                   (deg C)'
                                f'{pump_units:>20}{heat_units:>19}' + NL)
                        for i in range(0, model.surfaceplant.plant_lifetime.value - 1):
                            f.write(
                                '  {0:2.0f}         {1:8.4f}              {2:8.2f}             {3:8.4f}          {4:8.4f}'.format(
                                    i,
                                    model.wellbores.ProducedTemperature.value[i * model.economics.timestepsperyear.value] /\
                                    model.wellbores.ProducedTemperature.value[0],
                                    model.wellbores.ProducedTemperature.value[i * model.economics.timestepsperyear.value],
                                    model.wellbores.PumpingPower.value[i],
                                    model.surfaceplant.HeatProduced.value[i]) + NL)

                    f.write(NL)
                    f.write(
                        '                              ***************************************************************\n')
                    f.write(
                        '                              *  HEAT AND/OR ELECTRICITY EXTRACTION AND GENERATION PROFILE  *\n')
                    f.write(
                        '                              ***************************************************************\n')
                    if model.surfaceplant.enduse_option.value == EndUseOptions.ELECTRICITY:  # only electricity
                        f.write(
                            '  YEAR             ELECTRICITY                   HEAT                RESERVOIR            PERCENTAGE OF\n')
                        f.write(
                            '                    PROVIDED                   EXTRACTED            HEAT CONTENT        TOTAL HEAT MINED\n')
                        f.write(
                            '                   (GWh/year)                  (GWh/year)            (10^15 J)                 (%)\n')
                        for i in range(0, model.surfaceplant.plant_lifetime.value):
                            f.write(
                                '  {0:2.0f}              {1:8.1f}                    {2:8.1f}              {3:8.2f}               {4:8.2f}'.format(
                                    i + 1,
                                    model.surfaceplant.NetkWhProduced.value[i] / 1E6,
                                    model.surfaceplant.HeatkWhExtracted.value[i] / 1E6,
                                    model.surfaceplant.RemainingReservoirHeatContent.value[i],
                                    (model.reserv.InitialReservoirHeatContent.value - model.surfaceplant.RemainingReservoirHeatContent.value[i]) * 100 / model.reserv.InitialReservoirHeatContent.value) + NL)
                    elif model.surfaceplant.enduse_option.value == EndUseOptions.HEAT:  # only direct-use
                        f.write(
                            '  YEAR               HEAT                       HEAT                RESERVOIR           CUM PERCENTAGE OF\n')
                        f.write(
                            '                    PROVIDED                   EXTRACTED            HEAT CONTENT        TOTAL HEAT MINED\n')
                        f.write(
                            '                   (GWh/year)                  (GWh/year)            (10^15 J)                 (%)\n')
                        for i in range(0, model.surfaceplant.plant_lifetime.value - 1):
                            f.write(
                                '  {0:2.0f}              {1:8.1f}                    {2:8.1f}              {3:8.2f}               {4:8.2f}'.format(
                                    i + 1,
                                    model.surfaceplant.HeatkWhProduced.value[i] / 1E6,
                                    model.surfaceplant.HeatkWhExtracted.value[i] / 1E6,
                                    model.surfaceplant.RemainingReservoirHeatContent.value[i],
                                    (model.reserv.InitialReservoirHeatContent.value - model.surfaceplant.RemainingReservoirHeatContent.value[i]) * 100 / model.reserv.InitialReservoirHeatContent.value) + NL)

        except BaseException as ex:
            tb = sys.exc_info()[2]
            msg = "Error: GEOPHIRES Failed to write the output file.  Exiting....Line %i" % tb.tb_lineno
            print(str(ex))
            print(msg)
            model.logger.critical(str(ex))
            model.logger.critical(msg)
            traceback.print_exc()
            raise RuntimeError(msg)

        model.logger.info(f'Complete {str(__class__)}: {sys._getframe().f_code.co_name}')
