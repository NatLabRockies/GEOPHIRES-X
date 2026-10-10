# copyright, 2023, Malcolm I Ross

from enum import Enum


class GeophiresInputEnum(str, Enum):
    """
    Input enums have a name, integer input value, and string value

    TODO implement from_int/from_input_string here instead of child classes
    """

    def __new__(cls, *args, **kwds):
        obj = str.__new__(cls)
        obj._value_ = args[1]
        return obj

    def __init__(self, int_value: int, _: str):
        self.int_value = int_value

    def __eq__(self, other):
        return str(self) == str(other)

    def __ne__(self, other):
        return str(self) != str(other)


_EXTRA_HEAT_SNIPPET = 'Heat sales considered as extra income'
_EXTRA_ELECTRICITY_SNIPPET = 'Electricity sales considered as extra income'


class EndUseOptions(GeophiresInputEnum):
    ELECTRICITY = 1, 'Electricity'
    HEAT = 2, 'Direct-Use Heat'
    COGENERATION_TOPPING_EXTRA_HEAT = 31, f'Cogeneration Topping Cycle, {_EXTRA_HEAT_SNIPPET}'
    COGENERATION_TOPPING_EXTRA_ELECTRICITY = 32, f'Cogeneration Topping Cycle, {_EXTRA_ELECTRICITY_SNIPPET}'
    COGENERATION_BOTTOMING_EXTRA_HEAT = 41, f'Cogeneration Bottoming Cycle, {_EXTRA_HEAT_SNIPPET}'
    COGENERATION_BOTTOMING_EXTRA_ELECTRICITY = 42, f'Cogeneration Bottoming Cycle, {_EXTRA_ELECTRICITY_SNIPPET}'
    COGENERATION_PARALLEL_EXTRA_HEAT = 51, f'Cogeneration Parallel Cycle, {_EXTRA_HEAT_SNIPPET}'
    COGENERATION_PARALLEL_EXTRA_ELECTRICITY = 52, f'Cogeneration Parallel Cycle, {_EXTRA_ELECTRICITY_SNIPPET}'

    @property
    def is_cogeneration_end_use_option(self) -> bool:
        return self.name.startswith('COGENERATION')

    @property
    def has_electricity_component(self) -> bool:
        return self == self.ELECTRICITY or self.is_cogeneration_end_use_option

    @property
    def has_direct_use_heat_component(self) -> bool:
        return self == self.HEAT or self.is_cogeneration_end_use_option

    @staticmethod
    def from_input_string(input_string: str) -> 'EndUseOptions':
        """
        :rtype: EndUseOptions
        """

        for member in __class__:
            if input_string == str(member.int_value):
                return member

        raise ValueError(f'Unknown End-Use Option input value: {input_string}')

    @staticmethod
    def from_int(int_val: int) -> 'EndUseOptions':
        """
        :rtype: EndUseOptions
        """

        for member in __class__:
            if member.int_value == int_val:
                return member

        raise ValueError(f'Unknown End-Use Option integer input value: {int_val}')


class PlantType(GeophiresInputEnum):
    SUB_CRITICAL_ORC = 1, "Subcritical ORC"
    SUPER_CRITICAL_ORC = 2, "Supercritical ORC"
    SINGLE_FLASH = 3, "Single-Flash"
    DOUBLE_FLASH = 4, "Double-Flash"
    ABSORPTION_CHILLER = 5, "Absorption Chiller"
    HEAT_PUMP = 6, "Heat Pump"
    DISTRICT_HEATING = 7, "District Heating"
    RTES = 8, "Reservoir Thermal Energy Storage"
    INDUSTRIAL = 9, "Industrial"

    @staticmethod
    def from_input_string(input_string: str):
        """
        :rtype: PlantType
        """

        for member in __class__:
            if input_string == str(member.int_value):
                return member

        raise ValueError(f'Unknown Power Plant Type input value: {input_string}')

    @staticmethod
    def from_int(int_val):
        for member in __class__:
            if member.int_value == int_val:
                return member


class EconomicModel(GeophiresInputEnum):
    FCR = 1, "Fixed Charge Rate (FCR)"
    STANDARDIZED_LEVELIZED_COST = 2, "Standard Levelized Cost"
    BICYCLE = 3, "BICYCLE"
    CLGS = 4, "Simple (CLGS)"
    SAM_SINGLE_OWNER_PPA = 5, "SAM Single Owner PPA"

    @staticmethod
    def from_int(int_val):
        for member in __class__:
            if member.int_value == int_val:
                return member

    @staticmethod
    def from_input_string(input_string: str):
        for member in __class__:
            if input_string == str(member.int_value):
                return member

        raise ValueError(f'Unknown Economic Model input value: {input_string}')


class ReservoirModel(GeophiresInputEnum):
    CYLINDRICAL = 0, "Simple cylindrical"
    MULTIPLE_PARALLEL_FRACTURES = 1, "Multiple Parallel Fractures (Gringarten)"
    LINEAR_HEAT_SWEEP = 2, "1-D Linear Heat Sweep"
    SINGLE_FRACTURE = 3, "Single Fracture m/A Thermal Drawdown"
    ANNUAL_PERCENTAGE = 4, "Annual Percentage Thermal Drawdown"
    USER_PROVIDED_PROFILE = 5, "User-Provided Temperature Profile"
    TOUGH2_SIMULATOR = 6, "TOUGH2 Simulator"
    SUTRA = 7, "SUTRA"
    SBT = 8, "SBT"

    @staticmethod
    def get_reservoir_model_from_input_string(input_string: str):
        """
        :rtype: ReservoirModel
        """

        for model in ReservoirModel:
            if input_string == str(model.int_value):
                return model

        raise ValueError(f'Unknown Reservoir Model input value: {input_string}')

    @staticmethod
    def from_int(int_val):
        for member in __class__:
            if member.int_value == int_val:
                return member

    @property
    def display_name(self) -> str:
        """
        Returns a formatted string for display purposes.
        Format: "<value> Model <(suffix)>"
        """
        val_str = self.value

        if '(' in val_str:
            index = val_str.find('(')
            base_name = val_str[:index].strip()
            suffix = val_str[index:].strip()
            return f'{base_name} Model {suffix}'
        else:
            # No suffix is present
            return f'{val_str} Model'


class ReservoirVolume(GeophiresInputEnum):
    """
    TODO should probably be renamed to ReservoirVolumeOption
    """

    FRAC_NUM_SEP = 1, "Specify number of fractures and fracture separation"
    RES_VOL_FRAC_SEP = 2, "Specify reservoir volume and fracture separation"
    RES_VOL_FRAC_NUM = 3, "Specify reservoir volume and number of fractures"
    RES_VOL_ONLY = 4, "Specify reservoir volume only"

    @staticmethod
    def from_int(int_val):
        for member in __class__:
            if member.int_value == int_val:
                return member

    @staticmethod
    def from_input_string(input_string: str):
        for member in __class__:
            if input_string == str(member.int_value):
                return member

        raise ValueError(f'Unknown Reservoir Volume input value: {input_string}')


class _WellDrillingCostCorrelationCitation(str, Enum):
    """
    Values are abbreviated citations used in tooltip text.
    Commented full citations are present in CHANGELOG and could also be used in future documentation.
    """

    NREL_COST_CURVE_2025 = 'NREL\'s 2025 cost curve update'
    # ('Akindipe, D. and Witter. E. 2025. '
    #       '"2025 Geothermal Drilling Cost Curves Update". '
    #       'https://pangea.stanford.edu/ERE/db/GeoConf/papers/SGW/2025/Akindipe.pdf?t=1740084555')

    SIMPLE = 'Based on Fervo Project Cape cost per meter (~$1846/m)'

    GEOVISION = 'GeoVision'
    # ('DOE 2019. '
    #   '"GeoVision" p. 163. '
    #   'https://www.energy.gov/sites/prod/files/2019/06/f63/GeoVision-full-report-opt.pdf')


class WellDrillingCostCorrelation(GeophiresInputEnum):
    """
    Akindipe, D. and Witter. E. 2025.
        "2025 Geothermal Drilling Cost Curves Update".
        https://pangea.stanford.edu/ERE/db/GeoConf/papers/SGW/2025/Akindipe.pdf?t=1740084555

    Robins, J.C., Kesseli, D., Witter, E. and Rhodes, G. 2022.
        "2022 GETEM Geothermal Drilling Cost Curve Update."
        https://www.nrel.gov/docs/fy23osti/82771.pdf

    Note: order should be retained since input is read as an int; first int arg is duplicative of order
    """

    VERTICAL_SMALL = 1, "vertical small diameter, baseline", 0.258496, 357.967, 738531.58, \
        _WellDrillingCostCorrelationCitation.NREL_COST_CURVE_2025
    DEVIATED_SMALL = 2, "deviated small diameter, baseline", 0.240624, 646.1621, 503625.06, \
        _WellDrillingCostCorrelationCitation.NREL_COST_CURVE_2025
    VERTICAL_LARGE = 3, "vertical large diameter, baseline", 0.248458, 935.8985, 626586.68, \
        _WellDrillingCostCorrelationCitation.NREL_COST_CURVE_2025
    DEVIATED_LARGE = 4, "deviated large diameter, baseline", 0.217333, 1362.93, 301066.16, \
        _WellDrillingCostCorrelationCitation.NREL_COST_CURVE_2025

    SIMPLE = 5, "Simple (per-meter cost)", 0, 1846 * 1E6, 0, \
        _WellDrillingCostCorrelationCitation.SIMPLE

    VERTICAL_SMALL_INT1 = 6, "vertical small diameter, intermediate1", 0.13710, 129.61033, 1205587.57100, \
        _WellDrillingCostCorrelationCitation.GEOVISION
    VERTICAL_SMALL_INT2 = 7, "vertical small diameter, intermediate2", 0.00804, 455.60507, 921007.68680, \
        _WellDrillingCostCorrelationCitation.GEOVISION
    DEVIATED_SMALL_INT1 = 8, "deviated small diameter, intermediate1", 0.15340, 120.31700, 1431801.54400, \
        _WellDrillingCostCorrelationCitation.GEOVISION
    DEVIATED_SMALL_INT2 = 9, "deviated small diameter, intermediate2", 0.00854, 506.08357, 1057330.39000, \
        _WellDrillingCostCorrelationCitation.GEOVISION
    VERTICAL_LARGE_INT1 = 10, "vertical large diameter, intermediate1", 0.18927, 293.45174, 1326526.31300, \
        _WellDrillingCostCorrelationCitation.GEOVISION
    VERTICAL_LARGE_INT2 = 11, "vertical large diameter, intermediate2", 0.00315, 782.69676, 983620.25270, \
        _WellDrillingCostCorrelationCitation.GEOVISION
    DEVIATED_LARGE_INT1 = 12, "deviated large diameter, intermediate1", 0.19950, 296.13011, 1697867.70900, \
        _WellDrillingCostCorrelationCitation.GEOVISION
    DEVIATED_LARGE_INT2 = 13, "deviated large diameter, intermediate2", 0.00380, 838.90249, 1181947.04400, \
        _WellDrillingCostCorrelationCitation.GEOVISION
    VERTICAL_SMALL_IDEAL = 14, "vertical open-hole, small diameter, ideal", 0.00252, 439.44503, 590611.90110, \
        _WellDrillingCostCorrelationCitation.GEOVISION
    DEVIATED_SMALL_IDEAL = 15, "deviated liner, small diameter, ideal", 0.00719, 455.85233, 753377.73080, \
        _WellDrillingCostCorrelationCitation.GEOVISION
    VERTICAL_LARGE_IDEAL = 16, "vertical open-hole, large diameter, ideal", -0.00240, 752.93946, 524337.65380, \
        _WellDrillingCostCorrelationCitation.GEOVISION
    DEVIATED_LARGE_IDEAL = 17, "deviated liner, large diameter, ideal", 0.00376, 762.52696, 765103.07690, \
        _WellDrillingCostCorrelationCitation.GEOVISION

    def __init__(self, int_value: int, _: str, c2: float, c1: float, c0: float,
                 citation: _WellDrillingCostCorrelationCitation):
        self._c2 = c2
        self._c1 = c1
        self._c0 = c0
        self.citation: _WellDrillingCostCorrelationCitation = citation
        super().__init__(int_value, _)

    def calculate_cost_MUSD(self, meters) -> float:
        return (self._c2 * meters ** 2 + self._c1 * meters + self._c0) * 1E-6

    @staticmethod
    def from_input_string(input_string: str):
        for member in __class__:
            if input_string == str(member.int_value):
                return member

        raise ValueError(f'Unknown Well Drilling Cost Correlation input value: {input_string}')

    @staticmethod
    def from_int(int_val):
        for member in __class__:
            if member.int_value == int_val:
                return member


class FractureShape(GeophiresInputEnum):
    CIRCULAR_AREA = 1, "Circular fracture with known area"
    CIRCULAR_DIAMETER = 2, "Circular fracture with known diameter"
    SQUARE = 3, "Square"
    RECTANGULAR = 4, "Rectangular"

    @staticmethod
    def from_int(int_val):
        for member in __class__:
            if member.int_value == int_val:
                return member

    @staticmethod
    def from_input_string(input_string: str):
        for member in __class__:
            if input_string == str(member.int_value):
                return member

        raise ValueError(f'Unknown Fracture Shape input value: {input_string}')


class WorkingFluid(GeophiresInputEnum):
    WATER = 1, "water"
    SCO2 = 2, "sCO2"

    @staticmethod
    def from_int(int_val):
        for member in __class__:
            if member.int_value == int_val:
                return member

    @staticmethod
    def from_input_string(input_string: str):
        for member in __class__:
            if input_string == str(member.int_value):
                return member

        raise ValueError(f'Unknown Working Fluid input value: {input_string}')


class Configuration(GeophiresInputEnum):
    ULOOP = 1, "utube"
    COAXIAL = 2, "coaxial"
    VERTICAL = 3, "vertical"
    L = 4, "L"
    EAVORLOOP = 5, "EavorLoop"

    @staticmethod
    def from_int(int_val):
        for member in __class__:
            if member.int_value == int_val:
                return member

    @staticmethod
    def from_input_string(input_string: str):
        for member in __class__:
            if input_string == str(member.int_value):
                return member

        raise ValueError(f'Unknown Configuration input value: {input_string}')


class FlowrateModel(GeophiresInputEnum):
    USER_SUPPLIED = 1, "user supplied"
    FILE_SUPPLIED = 2, "file supplied"

    @staticmethod
    def from_int(int_val):
        for member in __class__:
            if member.int_value == int_val:
                return member

    @staticmethod
    def from_input_string(input_string: str):
        for member in __class__:
            if input_string == str(member.int_value):
                return member

        raise ValueError(f'Unknown Flow Rate Model input value: {input_string}')


class InjectionTemperatureModel(GeophiresInputEnum):
    USER_SUPPLIED = 1, "user supplied"
    FILE_SUPPLIED = 2, "file supplied"

    @staticmethod
    def from_int(int_val):
        for member in __class__:
            if member.int_value == int_val:
                return member

    @staticmethod
    def from_input_string(input_string: str):
        for member in __class__:
            if input_string == str(member.int_value):
                return member

        raise ValueError(f'Unknown Injection Temperature Model input value: {input_string}')


class DepreciationSchedule(GeophiresInputEnum):
    STRAIGHT_LINE_20_YEAR = 1, "20-year straight line"
    MACRS_5_YEAR = 2, "5-year MACRS"

    @staticmethod
    def from_int(int_val):
        for member in __class__:
            if member.int_value == int_val:
                return member

    @staticmethod
    def from_input_string(input_string: str):
        for member in __class__:
            if input_string == str(member.int_value):
                return member

        raise ValueError(f'Unknown Depreciation Schedule input value: {input_string}')
