# copyright, 2023, Malcolm I Ross
from __future__ import annotations

import copy
import dataclasses
import re

import sys
from collections.abc import Iterable
from typing import List, Optional
from dataclasses import dataclass, field
from enum import IntEnum
from forex_python.converter import CurrencyRates, CurrencyCodes

from abc import ABC

from pint import UndefinedUnitError
from pint.facets.plain import PlainQuantity

from geophires_x.OptionList import GeophiresInputEnum
from geophires_x.Units import *

SCHEDULE_DSL_MULTIPLIER_SYMBOL = '*'

_ureg = get_unit_registry()
_DISABLE_FOREX_API = True  # See https://github.com/NREL/GEOPHIRES-X/issues/236#issuecomment-2414681434

_JSON_PARAMETER_TYPE_STRING = 'string'
_JSON_PARAMETER_TYPE_INTEGER = 'integer'
_JSON_PARAMETER_TYPE_NUMBER = 'number'
_JSON_PARAMETER_TYPE_ARRAY = 'array'
_JSON_PARAMETER_TYPE_BOOLEAN = 'boolean'
_JSON_PARAMETER_TYPE_OBJECT = 'object'


class HasQuantity(ABC):

    def quantity(self, as_units: str | Enum | None = None) -> PlainQuantity:
        """
        :param as_units: Optional units to convert to. If None, will use current units.

        :rtype: pint.registry.Quantity - note type annotation uses PlainQuantity due to issues with python 3.8 failing
            to import the Quantity TypeAlias
        """

        # noinspection PyUnresolvedReferences
        quant_val = self.value

        if isinstance(quant_val, str):
            quant_val = float(quant_val)

        if isinstance(quant_val, Iterable):
            quant_val = [float(it) for it in quant_val]

        base_q = _ureg.Quantity(quant_val, str(convertible_unit(self.CurrentUnits.value)))
        if as_units is None:
            return base_q

        if isinstance(as_units, Enum):
            return base_q.to(convertible_unit(as_units.value))

        return base_q.to(convertible_unit(as_units))


@dataclass
class ParameterEntry:
    """A dataclass that contains the three fields that are being read from the user-provided file

    Attributes:
        Name (str): The official name of the parameter that the user wants to set
        sValue (str): The value that the user wants it to be set to, as a string.
        Comment (str): The optional comment that the user provided with that parameter in the text file
    """

    Name: str
    sValue: str
    Comment: Optional[str] = None
    raw_entry: Optional[str] = None


@dataclass
class OutputParameter(HasQuantity):
    """A dataclass that is the holder values that are provided to the user as output
     but are calculated internally by GEOPHIRES

    Attributes:
        Name (str): The official name of that output
        value: (any): the value of this parameter - can be int, float, text, bool, list, etc...
        ToolTipText (str): Text to place in a ToolTip in a UI
        UnitType (IntEnum): The class of units that parameter falls in (i.e., "length", "time", "area"...)
        PreferredUnits (Enum): The units as required by GEOPHIRES (or your algorithms)
        CurrentUnits (Enum): The units that the parameter is provided in (usually the same PreferredUnits)
        UnitsMatch (boolean): Internal flag set when units are different
    """

    Name: str = ""
    display_name: str = None
    value: Any = 0
    ToolTipText: str = ""
    UnitType: IntEnum = Units.NONE
    PreferredUnits: Enum = Units.NONE
    # set to PreferredUnits by default assuming that the current units are the preferred units -
    # they will only change if the read function reads a different unit associated with a parameter
    CurrentUnits: Enum = PreferredUnits
    json_parameter_type: str = None

    @property
    def UnitsMatch(self) -> str:
        return self.CurrentUnits == self.PreferredUnits

    def with_preferred_units(self) -> Any:  # Any is a proxy for Self
        ret: OutputParameter = dataclasses.replace(self)
        ret.value = ret.quantity().to(convertible_unit(ret.PreferredUnits)).magnitude
        ret.CurrentUnits = ret.PreferredUnits
        return ret

    def __post_init__(self):
        if self.display_name is None:
            self.display_name: str = self.Name

        if self.json_parameter_type is None:
            # Note that this is sensitive to order of comparison; unit test ensures correct behavior:
            # test_parameter.ParameterTestCase.test_output_parameter_json_types
            if isinstance(self.value, str):
                self.json_parameter_type = _JSON_PARAMETER_TYPE_STRING
            elif isinstance(self.value, bool):
                self.json_parameter_type = _JSON_PARAMETER_TYPE_BOOLEAN
            elif isinstance(self.value, float) or isinstance(self.value, int):
                # Default number values may not be representative of whether calculated values are integer-only,
                # so we specify number type even if value is int.
                self.json_parameter_type = _JSON_PARAMETER_TYPE_NUMBER
            elif isinstance(self.value, dict):
                self.json_parameter_type = _JSON_PARAMETER_TYPE_OBJECT
            elif isinstance(self.value, Iterable):
                self.json_parameter_type = _JSON_PARAMETER_TYPE_ARRAY
            else:
                self.json_parameter_type = _JSON_PARAMETER_TYPE_OBJECT

@dataclass
class Parameter(HasQuantity):
    """
     A dataclass that is the holder values that are provided (optionally) by the user.  These are all the inout values
     to the model.  They all must have a default value that is reasonable and will
     provide a reasonable result if not changed.

    Attributes:
        Name (str): The official name of that output
        Required (bool, False): Is this parameter required to be set?  See user manual.
        Provided (bool, False): Has this value been provided by the user?
        Valid (bool, True): has this value been successfully validated?
        ErrMessage (str): the error message that the user sees if the va;ue they provide does not pass validation -
              by default, it is: "assuming default value (see manual)"
        InputComment (str): The optional comment that the user provided with that parameter in the text file
        ToolTipText (str): Text to place in a ToolTip in a UI
        UnitType (IntEnum): The class of units that parameter falls in (i.e., "length", "time", "area"...)
        PreferredUnits (Enum): The units as required by GEOPHIRES (or your algorithms)
        CurrentUnits (Enum): The units that the parameter is provided in (usually the same PreferredUnits)
        UnitsMatch (boolean): Internal flag set when units are different
    """

    Name: str = ""
    Required: bool = False
    Provided: bool = False
    Valid: bool = True
    ErrMessage: str = "assume default value (see manual)"
    InputComment: str = ""
    ToolTipText: str = Name
    UnitType: IntEnum = Units.NONE
    PreferredUnits: Enum = None

    # set to PreferredUnits assuming that the current units are the preferred units
    # - they will only change if the read function reads a different unit associated with a parameter
    CurrentUnits: Enum = PreferredUnits

    @property
    def UnitsMatch(self) -> bool:
        return self.PreferredUnits == self.CurrentUnits

    parameter_category: str = None

    ValuesEnum: GeophiresInputEnum = None

    def __post_init__(self):
        if self.PreferredUnits is None:
            self.PreferredUnits = self.CurrentUnits

@dataclass
class boolParameter(Parameter):
    """
    boolParameter: a dataclass that stores the values for a Boolean value.  Includes the default value and the
    validation values (if appropriate).  Child of Parameter, so it gets all the Attributes of that class.

    Attributes:
        value (bool): The value of that parameter
        DefaultValue (bool, True):  The default value of that parameter
    """

    def __post_init__(self):
        if self.value is None:
            self.value: bool = self.DefaultValue

    value: bool = None
    DefaultValue: bool = value
    json_parameter_type: str = _JSON_PARAMETER_TYPE_BOOLEAN


@dataclass
class intParameter(Parameter):
    """
    intParameter: a dataclass that stores the values for an Integer value.  Includes the default value and the
    validation values (if appropriate).  Child of Parameter, so it gets all the Attributes of that class.

    Attributes:
        value (int): The value of that parameter
        DefaultValue (int, 0):  The default value of that parameter
        AllowableRange (list): A list of the valid values
    """

    def __post_init__(self):
        if self.value is None:
            self.value:int = self.DefaultValue

    value: int = None
    DefaultValue: int = value
    AllowableRange: List[int] = field(default_factory=list)
    json_parameter_type: str = _JSON_PARAMETER_TYPE_INTEGER

    def coerce_value_to_enum(self):
        if self.ValuesEnum is not None:
            if not isinstance(self.value, self.ValuesEnum):
                self.value = self.ValuesEnum.from_int(self.value)


@dataclass
class floatParameter(Parameter):
    """
    floatParameter: a dataclass that stores the values for a Float value.  Includes the default value and the
    validation values (if appropriate).  Child of Parameter, so it gets all the Attributes of that class.

    Attributes:
        value (float): The value of that parameter
        DefaultValue (float, 0.0):  The default value of that parameter
        Min (float, -1.8e308): minimum valid value - not that it is set to a very small value,
                which means that any value is valid by default
        Min (float, 1.8e308): maximum valid value - not that it is set to a very large value,
                which means that any value is valid by default
    """

    def __post_init__(self):
        if self.value is None:
            self.value = self.DefaultValue
        super().__post_init__()

    value: float = None

    DefaultValue: float = 0.0
    Min: float = -1.8e30
    Max: float = 1.8e30
    json_parameter_type: str = _JSON_PARAMETER_TYPE_NUMBER


@dataclass
class strParameter(Parameter):
    """
    strParameter: a dataclass that stores the values for a String value.  Includes the default value and the
    validation values (if appropriate).  Child of Parameter, so it gets all the Attributes of that class.

    Attributes:
        value (str): The value of that parameter
        DefaultValue (str, ""):  The default value of that parameter
    """
    def __post_init__(self):
        if self.value is None:
            self.value: str = self.DefaultValue

    value: str = None
    DefaultValue: str = value
    json_parameter_type: str = _JSON_PARAMETER_TYPE_STRING


@dataclass
class listParameter(Parameter):
    """
    listParameter: a dataclass that stores the values for a List of values.  Includes the default value and the
    validation values (if appropriate).  Child of Parameter, so it gets all the Attributes of that class.

    Attributes:
        value (list): The value of that parameter
        DefaultValue (list, []):  The default value of that parameter
        Min (float, -1.8e308): minimum valid value of each value in the list - not that it is set to a very small value,
              which means that any value is valid by default
        Min (float, 1.8e308): maximum valid value of each va;ue in the list - not that it is set to a very large value,
            which means that any value is valid by default
    """

    def __post_init__(self):
        if self.value is None:
            self.value: str = self.DefaultValue

    value: List[float] = None
    DefaultValue: List[float] = field(default_factory=list)
    Min: float = -1.8e308
    Max: float = 1.8e308
    json_parameter_type: str = _JSON_PARAMETER_TYPE_ARRAY

    # TODO push this up to the Parameter class and add support for all parameter types (not just list)
    auto_raise_exception_on_invalid_read: bool = False
    """
    Whether to automatically raise an exception when an invalid read occurs.
    Should be True for newly added parameters (False default is for backwards compatibility).
    """


def ReadParameter(ParameterReadIn: ParameterEntry, ParamToModify, model) -> None:
    """
    ReadParameter: A method to take a single ParameterEntry object and use it to update the associated Parameter.
    Does validation as well as Unit and Currency conversion
    :param ParameterReadIn: The value the user wants to change and the value they want to change it to (as a string)
     and  any comment they provided with it (as a string) - all in one object (ParameterEntry) that is passed in
      to this method as a parameter itself (ParameterReadIn) - see ParameterEntry class for details on the fields in it
    :type ParameterReadIn: :class:`~geophires_x.Parameter.ParameterEntry`
    :param ParamToModify: The Parameter that will be modified (assuming it passes validation and conversion) - this is
      the object that will be modified by this method - see Parameter class for details on the fields in it
    :type ParamToModify: :class:`~geophires_x.Parameter.Parameter`
    :param model: The container class of the application, giving access to everything else, including the logger
    :type model: :class:`~geophires_x.Model.Model`
    :return: None
    """
    model.logger.info(f'Init {str(__name__)}: {sys._getframe().f_code.co_name} for {ParamToModify.Name}')

    # these Parameter Types don't have units so don't do anything fancy, and ignore it if the user has supplied units
    if isinstance(ParamToModify, boolParameter) or isinstance(ParamToModify, strParameter):
        if isinstance(ParamToModify, boolParameter):
            val_sanitized = ('' if ParameterReadIn.sValue is None else ParameterReadIn.sValue).strip().lower()
            if val_sanitized in ['0', 'false', 'f', 'no',  'n']:
                ParamToModify.value = False
            elif val_sanitized in ['1', 'true', 't', 'yes', 'y']:
                ParamToModify.value = True
            else:
                ParamToModify.value = bool(ParameterReadIn.sValue)
                model.logger.warning(
                    f'Non-boolean value "{ParameterReadIn.sValue}" given for '
                    f'{ParamToModify.Name} treated as {ParamToModify.value}.'
                )
        else:
            ParamToModify.value = ParameterReadIn.sValue
        ParamToModify.Provided = True  # set provided to true because we are using a user provide value now
        ParamToModify.Valid = True  # set Valid to true because it passed the validation tests
        model.logger.info(f'Complete {str(__name__)}: {sys._getframe().f_code.co_name}')
        return

    # deal with the case where the value has a unit involved - that will be indicated by a space in it
    if ' ' in ParameterReadIn.sValue and SCHEDULE_DSL_MULTIPLIER_SYMBOL not in ParameterReadIn.sValue:
        new_str = ConvertUnits(ParamToModify, ParameterReadIn.sValue, model)
        if len(new_str) > 0:
            ParameterReadIn.sValue = new_str
    else:
        # The value came in without any units
        # TODO: determine the proper action in this case
        # (previously, it was assumed that the value must be
        # using the default PreferredUnits, which was not always
        # valid and led to incorrect units in the output)
        pass

    def default_parameter_value_message(new_val: Any, param_to_modify_name: str, default_value: Any) -> str:
        return (
            f'Parameter given ({str(new_val)}) for {param_to_modify_name} is the same as the default value. '
            f'Consider removing {param_to_modify_name} from the input file unless you wish '
            f'to change it from the default value of ({str(default_value)})'
        )

    if isinstance(ParamToModify, intParameter):
        New_val = int(float(ParameterReadIn.sValue))

        if New_val == ParamToModify.DefaultValue:
            if len(ParamToModify.ErrMessage) > 0:
                msg = default_parameter_value_message(New_val, ParamToModify.Name, ParamToModify.DefaultValue)
                model.logger.info(msg)

            model.logger.info(f'Complete {str(__name__)}: {sys._getframe().f_code.co_name}')
            return

        if New_val == ParamToModify.value:
            # We have nothing to change - user provide value that was the same as the
            # existing value (likely, the default value)
            return

        if not (New_val in ParamToModify.AllowableRange):
            # user provided value is out of range, so announce it, leave set to whatever it was set to (default value)
            err_msg = f"Error: Parameter given ({New_val}) for {ParamToModify.Name} outside of valid range."
            print(err_msg)
            model.logger.fatal(err_msg)
            model.logger.info(f'Complete {str(__name__)}: {sys._getframe().f_code.co_name}')
            raise ValueError(err_msg)
        else:
            # All is good
            ParamToModify.value = New_val  # set the new value
            ParamToModify.Provided = True  # set provided to true because we are using a user provide value now
            ParamToModify.Valid = True  # set Valid to true because it passed the validation tests
    elif isinstance(ParamToModify, floatParameter):
        New_val = float(ParameterReadIn.sValue)

        if New_val == ParamToModify.DefaultValue:
            # Warning - the value read in is the same as the default value, making it superfluous
            # - add a warning and suggestion

            ParamToModify.Provided = True
            if len(ParamToModify.ErrMessage) > 0:
                msg = default_parameter_value_message(New_val, ParamToModify.Name, ParamToModify.DefaultValue)
                model.logger.info(msg)

            model.logger.info(f'Complete {str(__name__)}: {sys._getframe().f_code.co_name}')
        if New_val == ParamToModify.value:
            # We have nothing to change - user provided value that was the same as the
            # existing value (likely, the default value)
            model.logger.info(f'Complete {str(__name__)}: {sys._getframe().f_code.co_name}')
            return

        if (New_val < float(ParamToModify.Min)) or (New_val > float(ParamToModify.Max)):
            # user provided value is out of range, so announce it, leave set to whatever it was set to (default value)
            err_msg = f'Error: Parameter given ({New_val}) for {ParamToModify.Name} outside of valid range.'
            print(err_msg)
            model.logger.fatal(err_msg)
            model.logger.info(f'Complete {str(__name__)}: {sys._getframe().f_code.co_name}')
            raise ValueError(err_msg)
        else:
            # All is good
            ParamToModify.value = New_val  # set the new value
            ParamToModify.Provided = True  # set provided to true because we are using a user provide value now
            ParamToModify.Valid = True  # set Valid to true because it passed the validation tests
    elif isinstance(ParamToModify, listParameter):
        _read_list_parameter(ParameterReadIn, ParamToModify, model)

    elif isinstance(ParamToModify, boolParameter):
        if ParameterReadIn.sValue == "0":
            New_val = False
        if ParameterReadIn.sValue == "false" or ParameterReadIn.sValue == "False" or ParameterReadIn.sValue == "FALSE":
            New_val = False
        else:
            New_val = True
        if New_val == ParamToModify.value:
            model.logger.info(f'Complete {str(__name__)}": {sys._getframe().f_code.co_name}')
            # We have nothing to change - user provide value that was the same as the existing value (likely, the default value)
            return

        ParamToModify.value = New_val  # set the new value
        ParamToModify.Provided = True  # set provided to true because we are using a user provide value now
        ParamToModify.Valid = True  # set Valid to true because it passed the validation tests
    elif isinstance(ParamToModify, strParameter):
        New_val = str(ParameterReadIn.sValue)
        if New_val == ParamToModify.value:
            # We have nothing to change - user provide value that was the same as the existing value (likely, the default value)
            return
        ParamToModify.value = New_val  # set the new value
        ParamToModify.Provided = True  # set provided to true because we are using a user provide value now
        ParamToModify.Valid = True  # set Valid to true because it passed the validation tests

    model.logger.info(f'Complete {str(__name__)}: {sys._getframe().f_code.co_name}')


def _read_list_parameter(ParameterReadIn: ParameterEntry, ParamToModify: listParameter, model) -> None:
    """
    :type ParamToModify: :class:`~geophires_x.Parameter.Parameter`
    :type model: :class:`~geophires_x.Model.Model`
    """

    from geophires_x.GeoPHIRESUtils import is_float, is_int as _is_int  # avoid circular imports

    is_positional_parameter = ' ' in ParameterReadIn.Name and _is_int(ParamToModify.Name.split(' ')[-1])
    if is_positional_parameter:
        New_val = float(ParameterReadIn.sValue)
        # Some list parameters are read in with enumerated parameter names;  in these cases we use the last
        # character of the description to get the position i.e., "Gradient 1" is position 0.
        parts = ParameterReadIn.Name.split(' ')
        position = int(parts[1]) - 1
        if position >= len(ParamToModify.value):
            ParamToModify.value.append(New_val)  # we are adding to the list, so use append
        else:  # we are replacing a value, so pop the value we want to replace, then insert a new one
            ParamToModify.value.pop(position)
            ParamToModify.value.insert(position, New_val)
    else:
        # In an ideal world this would be handled in ParameterEntry such that its sValue and Comment are
        # correct; however, that would only be practical if ParameterEntry had typing information to know
        # whether to treat text after a second comma as a comment or list entry.

        ParamToModify.value = [float(x.strip()) if is_float(x.strip()) else x.strip() for x in
                               re.split(r',\s*--', ParameterReadIn.raw_entry)[0].split(',')[1:] if x.strip() != '']

    ParamToModify.Provided = True

    # TODO make this a property of listParameter
    is_boolean_type = (ParamToModify.DefaultValue is not None and
        (isinstance(ParamToModify.DefaultValue, Iterable) and
        len(ParamToModify.DefaultValue) > 0 and
        isinstance(ParamToModify.DefaultValue[0], bool))
        or (isinstance(ParamToModify.DefaultValue, bool)))


    def _is_bool_val(_val: Any) -> bool:
        return isinstance(_val, bool) or (str(_val).strip().lower() in ['true', 'false', '1', '0', 'yes', 'no'])

    valid = True
    for i in range(len(ParamToModify.value)):
        New_val = ParamToModify.value[i]
        if is_boolean_type:
            if _is_bool_val(New_val):
                continue
            msg = f'Value given ({str(New_val)}) for {ParamToModify.Name} is not boolean.'
            valid = False

        if isinstance(New_val, str):
            if '*' in New_val:
                New_val = New_val.split('*')[0]
            New_val = float(New_val.strip())

        if (New_val < float(ParamToModify.Min)) or (New_val > float(ParamToModify.Max)):
            msg = (
                f'Value given ({str(New_val)}) for {ParamToModify.Name} outside of valid range '
                f'({ParamToModify.Min}–{ParamToModify.Max}).'
            )
            valid = False

        if not valid:
            print(f'Warning: {msg}')
            model.logger.warning(msg)

    ParamToModify.Valid = valid

    if not ParamToModify.Valid and ParamToModify.auto_raise_exception_on_invalid_read:
        raise ValueError(f'Invalid value provided for {ParamToModify.Name}: {ParamToModify.value}')


def ConvertUnits(ParamToModify, strUnit: str, model) -> str:
    """
    ConvertUnits gets called if a unit version is needed: either currency or standard units like F to C or m to ft
    :param ParamToModify: The Parameter that will be modified (assuming it passes validation and conversion) - this is
        the object that will be modified by this method - see Parameter class for details on the fields in it
    :type ParamToModify: :class:`~geophires_x.Parameter.Parameter`
    :param strUnit: A string containing the value to be converted along with the units it is currently in.
        The units to convert to are set by the PreferredUnits of ParamToModify
    :type strUnit: str
    :param model: The container class of the application, giving access to everything else, including the logger
    :type model: :class:`~geophires_x.Model.Model`
    :return: The new value as a string (without the units, because they are already held in PreferredUnits of ParamToModify)
    :rtype: str
    """
    model.logger.info(f'Init {str(__name__)}: {sys._getframe().f_code.co_name} for {ParamToModify.Name}')

    # deal with the currency case
    if ParamToModify.UnitType in [Units.CURRENCY, Units.CURRENCYFREQUENCY, Units.COSTPERMASS, Units.ENERGYCOST]:
        prefType = ParamToModify.PreferredUnits.value
        parts = strUnit.split(' ')
        val = parts[0].strip()
        currType = parts[1].strip()
        # user has provided a currency that is the currency expected, so just strip off the currency
        if prefType == currType:
            strUnit = str(val)
            ParamToModify.CurrentUnits = currType
            return strUnit

        Factor = 1.0

        # First we need to deal the possibility that there is a suffix on the units (like /yr, kwh, or /tonne)
        # that will make it not be recognized by the currency conversion engine.
        # We strip the suffix off of a copy of the string that represents the units,
        # derive the suffix conversion factor using pint, then
        # then allow the currency conversion to happen.
        currSuff = prefSuff = ""
        elements = currType.split("/")
        if len(elements) > 1:
            currType = elements[0]  # strip off the suffix, but save it
            currSuff = "/" + elements[1]
        elements = prefType.split("/")
        if len(elements) > 1:
            prefType = elements[0]  # strip off the suffix, but save it
            prefSuff = "/" + elements[1]

        if currSuff != prefSuff:
            Factor *= 1/_ureg.Quantity(1, currSuff[1:]).to(prefSuff[1:]).magnitude

        # Let's try to deal with first the simple conversion where the required units have a prefix like M (m) or K (k)
        # that means a "million" or a "thousand", like MUSD (or KUSD), and the user provided USD (or KUSD) or KEUR, MEUR
        # we have to deal with the case that the M, m, K, or k are NOT prefixes, but rather are a part of the currency name.
        cc = CurrencyCodes()
        currFactor = prefFactor = 1.0
        currPrefix = prefPrefix = False

        prefShort = prefType
        currShort = currType
        # if either of these returns a symbol, then we must have prefixes we need to deal with
        symbol = cc.get_symbol(prefType[1:])
        symbol2 = cc.get_symbol(currType[1:])
        if symbol is not None:
            prefPrefix = True
        if symbol2 is not None:
            currPrefix = True
        if prefPrefix and prefType[0] in ['M', 'm']:
            prefFactor = prefFactor * 1_000_000.0
        elif prefPrefix and prefType[0] in ['K', 'k']:
            prefFactor = prefFactor * 1000.0
        if currPrefix and currType[0] in ['M', 'm']:
            currFactor = currFactor / 1_000_000.0
        elif currPrefix and currType[0] in ['K', 'k']:
            currFactor = currFactor / 1000.0

        Factor *= currFactor * prefFactor

        if prefPrefix:
            prefShort = prefType[1:]
        if currPrefix:
            currShort = currType[1:]

        if prefShort == currShort:
            # this is true, then we just have a conversion between KUSD and USD, MUSD to KUSD, MUER to EUR, etc.,
            # so just do the simple factor conversion

            val = float(val) * Factor
            strUnit = str(val)
            ParamToModify.CurrentUnits = f'{currType}{currSuff}'
            return strUnit

        try:
            # if we come here, we have a currency conversion to do (USD->EUR, etc.).

            if _DISABLE_FOREX_API:
                raise RuntimeError('Forex API disabled')

            cr = CurrencyRates()
            conv_rate = cr.get_rate(currShort, prefShort)
        except BaseException as ex:
            print(str(ex))
            msg = (
                f'Error: GEOPHIRES failed to convert your currency for {ParamToModify.Name} to something it understands. '
                f'You gave {strUnit} - conversion may be affected by https://github.com/NREL/GEOPHIRES-X/issues/236. '
                f'Please change your units to {ParamToModify.PreferredUnits.value} '
                f'to continue. Cannot continue unless you do. Exiting.'
            )
            print(msg)
            model.logger.critical(str(ex))
            model.logger.critical(msg)

            raise RuntimeError(msg)

        New_val = (conv_rate * float(val)) * Factor
        strUnit = str(New_val)
        ParamToModify.CurrentUnits = parts[1]

        if len(prefSuff) > 0:
            prefType = prefType + prefSuff  # set it back the way it was
        if len(currSuff) > 0:
            currType = currType + currSuff
        parts = strUnit.split(' ')
        strUnit = parts[0]
        return strUnit

    else:  # must be something other than boolean, string, or currency
        if isinstance(strUnit, pint.Quantity):
            val = ParamToModify.value
            currType = str(strUnit)
        else:
            parts = strUnit.split(' ')
            val = parts[0].strip()
            currType = parts[1].strip()
        # check to see if the units provided (CurrentUnits) are the same as the preferred units.
        # In that case, we don't need to do anything.
        try:
            # Make a Pint Quantity out of the old value: the amount of the unit doesn't matter,
            # just the units, so I set the amount to 0
            Old_valQ = _ureg.Quantity(0.000, str(ParamToModify.CurrentUnits.value))
            New_valQ = _ureg.Quantity(float(val), currType)  # Make a Pint Quantity out of the new value
        except BaseException as ex:
            print(str(ex))
            msg = (
                f'Error: GEOPHIRES failed to initialize your units for {ParamToModify.Name} '
                f'to something it understands. '
                f'You gave {strUnit} - Are the units defined for Pint library, or have you defined them in the '
                f'user-defined units file (GEOPHIRES3_newunits)?  Cannot continue. Exiting.'
            )
            print(msg)
            model.logger.critical(str(ex))
            model.logger.critical(msg)

            raise RuntimeError(msg)

        if Old_valQ.units != New_valQ.units:  # do the transformation only if the units don't match
            ParamToModify.CurrentUnits = LookupUnits(currType)[0]
            try:
                # update the quantity to the preferred units,
                # so we don't have to change the underlying calculations.  This assumes that Pint recognizes our unit.
                # If we have a new unit, we have to add it to the Pint configuration text file
                New_valQ.ito(Old_valQ)
            except BaseException as ex:
                print(str(ex))
                msg = (
                    f'Error: GEOPHIRES failed to convert your units for {ParamToModify.Name} '
                    f'to something it understands. You gave {strUnit} - Are the units defined for Pint library, '
                    f'or have you defined them in the user defined units file (GEOPHIRES3_newunits)? '
                    f'Cannot continue. Exiting.'
                )
                print(msg)
                model.logger.critical(str(ex))
                model.logger.critical(msg)

                raise RuntimeError(msg)

            # set sValue to the value based on the new units - don't add units to it - it should just be a raw number
            strUnit = str(New_valQ.magnitude)

            new_val_units_lookup = LookupUnits(str(New_valQ.units))
            if new_val_units_lookup is not None and new_val_units_lookup[0] is not None:
                ParamToModify.CurrentUnits = new_val_units_lookup[0]

        else:
            # if we come here, we must have a unit declared, but the unit must be the same as the preferred unit,
            # so we need to just get rid of the extra text after the space
            parts = strUnit.split(' ')
            strUnit = parts[0]

    model.logger.info(f'Complete {str(__name__)}: {sys._getframe().f_code.co_name}')
    return strUnit


def ConvertUnitsBack(ParamToModify: Parameter, model):
    """
    CovertUnitsBack: Converts units back to what the user specified they as.  It does this so that the user can see them
    in the report as the units they specified. We know that because CurrentUnits contains the desired units
    :param param: The Parameter that will be modified (assuming it passes validation and conversion) - this is
        the object that will be modified by this method - see Parameter class for details on the fields in it
    :type param: :class:`~geophires_x.Parameter.Parameter`
    :param model: The container class of the application, giving access to everything else, including the logger
    :type model: :class:`~geophires_x.Model.Model`
    :return: None
    """
    model.logger.info(f'Init {str(__name__)}: {sys._getframe().f_code.co_name} for {ParamToModify.Name}')

    try:
        ParamToModify.value = _ureg.Quantity(ParamToModify.value, convertible_unit(ParamToModify.CurrentUnits)).to(convertible_unit(ParamToModify.PreferredUnits)).magnitude
        ParamToModify.CurrentUnits = ParamToModify.PreferredUnits
    except AttributeError as ae:
        # TODO refactor to check for/convert currency instead of relying on try/except once currency conversion is
        #  re-enabled - https://github.com/NREL/GEOPHIRES-X/issues/236?title=Currency+conversions+disabled
        model.logger.warning(f'Failed to convert units with pint, attempting currency conversion ({ae})')

        try:
            param_modified: Parameter = _parameter_with_currency_units_converted_back_to_preferred_units(ParamToModify,
                                                                                                         model)
            ParamToModify.value = param_modified.value
            ParamToModify.CurrentUnits = param_modified.CurrentUnits
            ParamToModify.UnitType = param_modified.UnitType
        except AttributeError as cce:
            model.logger.error(f'Currency conversion failed ({cce})')

            msg = (
                f'Error: GEOPHIRES failed to convert your units for {ParamToModify.Name} to something it understands. '
                f'You gave {ParamToModify.CurrentUnits}  - Are the units defined for Pint library, '
                f' or have you defined them in the user defined units file (GEOPHIRES3_newunits)? '
                f'Cannot continue. Exiting.'
            )
            model.logger.critical(msg)

            raise RuntimeError(msg)


    model.logger.info(f'Complete {str(__name__)}: {sys._getframe().f_code.co_name}')


def _parameter_with_currency_units_converted_back_to_preferred_units(param: Parameter, model) -> Parameter:
    """
    TODO clean up and consolidate with pint-based conversion in ConvertUnitsBack
    """

    param_with_units_converted_back = copy.deepcopy(param)

    # deal with the currency case
    if param.UnitType in [Units.CURRENCY, Units.CURRENCYFREQUENCY, Units.COSTPERMASS, Units.ENERGYCOST]:
        prefType = param.PreferredUnits.value
        currType = param.CurrentUnits

        # First we need to deal the possibility that there is a suffix on the units (like /yr, kwh, or /tonne)
        # that will make it not be recognized by the currency conversion engine.
        # generally, we will just strip the suffix off of a copy of the string that represents the units, then allow
        # the conversion to happen. For now, we ignore the suffix.
        # this has the consequence that we don't do any conversion based on that suffix, so units like EUR/MMBTU
        # will trigger a conversion to USD/MMBTU, where MMBY+TU doesn't get converted to KW (or whatever)
        currSuff = prefSuff = ""
        elements = str(currType).split("/")
        if len(elements) > 1:
            currType = elements[0]  # strip off the suffix, but save it
            currSuff = "/" + elements[1]
        elements = prefType.split("/")
        if len(elements) > 1:
            prefType = elements[0]  # strip off the suffix, but save it
            prefSuff = "/" + elements[1]

        # Let's try to deal with first the simple conversion where the required units have a prefix like M (m) or K (k)
        # that means a "million" or a "thousand", like MUSD (or KUSD), and the user provided USD (or KUSD) or KEUR, MEUR
        # we have to deal with the case that the M, m, K, or k are NOT prefixes,
        # but rather are a part of the currency name.
        cc = CurrencyCodes()
        currFactor = prefFactor = 1.0
        currPrefix = prefPrefix = False
        Factor = 1.0
        prefShort = prefType
        currShort = currType
        symbol = cc.get_symbol(
            prefType[1:]
        )  # if either of these returns a symbol, then we must have prefixes we need to deal with
        symbol2 = cc.get_symbol(currType[1:])
        if symbol is not None:
            prefPrefix = True
        if symbol2 is not None:
            currPrefix = True
        if prefPrefix and prefType[0] in ['M', 'm']:
            prefFactor = prefFactor * 1_000_000.0
        elif prefPrefix and prefType[0] in ['K', 'k']:
            prefFactor = prefFactor * 1000.0
        if currPrefix and currType[0] in ['M', 'm']:
            currFactor = currFactor / 1_000_000.0
        elif currPrefix and currType[0] in ['K', 'k']:
            currFactor = currFactor / 1000.0
        Factor = currFactor * prefFactor
        if prefPrefix:
            prefShort = prefType[1:]
        if currPrefix:
            currShort = currType[1:]
        if prefShort == currShort:
            # this is true, then we just have a conversion between KUSD and USD, MUSD to KUSD, MUER to EUR, etc.,
            # so just do the simple factor conversion
            param_with_units_converted_back.value = param.value * Factor
            param_with_units_converted_back.CurrentUnits = currType
            return param_with_units_converted_back

        # Now lets deal with the case where the units still don't match, so we have a real currency conversion,
        # like USD to EUR
        # start the currency conversion process
        cc = CurrencyCodes()
        try:
            if _DISABLE_FOREX_API:
                raise RuntimeError('Forex API disabled')

            cr = CurrencyRates()
            conv_rate = cr.get_rate(currType, prefType)
        except BaseException as ex:
            print(str(ex))
            msg = (
                f'Error: GEOPHIRES failed to convert your currency for {param.Name} to something it understands.'
                f'You gave {currType} - conversion may be affected by https://github.com/NREL/GEOPHIRES-X/issues/236.  '
                f'Please change your units to {param.PreferredUnits.value} '
                f'to continue. Cannot continue unless you do.  Exiting.'
            )
            print(msg)
            model.logger.critical(str(ex))
            model.logger.critical(msg)

            raise RuntimeError(msg, ex)

        param_with_units_converted_back.value = (conv_rate * float(param.value)) / prefFactor
        return param_with_units_converted_back

    else:
        raise AttributeError(
            f'Unit/unit type ({param.CurrentUnits}/{param.UnitType}) for {param.Name} '
            f'is not a recognized currency unit'
        )


def LookupUnits(sUnitText: str):
    """
    LookupUnits Given a unit class and a text string, this will return the value from the Enumeration if it is there
    (or return nothing if it is not)
    :param sUnitText: The text string to look for in the Enumeration of units (like "m" or "feet") - this is the text
        that the user provides in the input file or the GUI to specify the units they want to use for a parameter or
        output value (like "m" or "feet")
    :type sUnitText: str (text)
    :return: The Enumerated value and the Unit class Enumeration
    :rtype: tuple
    """
    # look through all unit types and names for a match with my units
    for uType in Units:
        MyEnum = None
        if uType == Units.LENGTH:
            MyEnum = LengthUnit
        elif uType == Units.AREA:
            MyEnum = AreaUnit
        elif uType == Units.VOLUME:
            MyEnum = VolumeUnit
        elif uType == Units.MASS:
            MyEnum = MassUnit
        elif uType == Units.DENSITY:
            MyEnum = DensityUnit
        elif uType == Units.TEMPERATURE:
            MyEnum = TemperatureUnit
        elif uType == Units.PRESSURE:
            MyEnum = PressureUnit
        elif uType == Units.TIME:
            MyEnum = TimeUnit
        elif uType == Units.FLOWRATE:
            MyEnum = FlowRateUnit
        elif uType == Units.TEMP_GRADIENT:
            MyEnum = TemperatureGradientUnit
        elif uType == Units.DRAWDOWN:
            MyEnum = DrawdownUnit
        elif uType == Units.IMPEDANCE:
            MyEnum = ImpedanceUnit
        elif uType == Units.PRODUCTIVITY_INDEX:
            MyEnum = ProductivityIndexUnit
        elif uType == Units.INJECTIVITY_INDEX:
            MyEnum = InjectivityIndexUnit
        elif uType == Units.HEAT_CAPACITY:
            MyEnum = HeatCapacityUnit
        elif uType == Units.THERMAL_CONDUCTIVITY:
            MyEnum = ThermalConductivityUnit
        elif uType == Units.CURRENCY:
            MyEnum = CurrencyUnit
        elif uType == Units.CURRENCYFREQUENCY:
            MyEnum = CurrencyFrequencyUnit
        elif uType == Units.PERCENT:
            MyEnum = PercentUnit
        elif uType == Units.ENERGY:
            MyEnum = EnergyUnit
        elif uType == Units.ENERGYCOST:
            MyEnum = EnergyCostUnit
        elif uType == Units.ENERGYFREQUENCY:
            MyEnum = EnergyFrequencyUnit
        elif uType == Units.COSTPERMASS:
            MyEnum = CostPerMassUnit
        elif uType == Units.AVAILABILITY:
            MyEnum = AvailabilityUnit
        elif uType == Units.ENTROPY:
            MyEnum = EntropyUnit
        elif uType == Units.ENTHALPY:
            MyEnum = EnthalpyUnit
        elif uType == Units.POROSITY:
            MyEnum = PorosityUnit
        elif uType == Units.PERMEABILITY:
            MyEnum = PermeabilityUnit
        elif uType == Units.ENERGYDENSITY:
            MyEnum = EnergyDensityUnit
        elif uType == Units.MASSPERTIME:
            MyEnum = MassPerTimeUnit
        elif uType == Units.COSTPERDISTANCE:
            MyEnum = CostPerDistanceUnit
        elif uType == Units.POWER:
            MyEnum = PowerUnit
        elif uType == Units.CO2PRODUCTION:
            MyEnum = CO2ProductionUnit
        elif uType == Units.ENERGYPERCO2:
            MyEnum = EnergyPerCO2Unit

        if MyEnum is not None:
            for item in MyEnum:
                if item.value == sUnitText:
                    return item, uType

    # No match was found with the unit text string, so try with the canonical symbol (if different).
    try:
        symbol = _ureg.get_symbol(sUnitText)
        if symbol != sUnitText:
            return LookupUnits(symbol)
    except UndefinedUnitError as _uue:
        return sUnitText, uType

    return None, None


def ConvertOutputUnits(oparam: OutputParameter, newUnit: Units, model):
    """
    ConvertOutputUnits Given an output parameter, convert the value(s) from what they contain
    (as calculated by GEOPHIRES) to what the user specified as what they want for outputs.  Conversion happens inline.

    :param oparam: The parameter you want to be converted (value or list of values).  Because Parameters know the
        PreferredUnits and CurrentUnits, this routine knows what to do. It will convert the value(s) in the parameter
        to the new units, and then reset the CurrentUnits to the new units. This is done so that the user can see the units
        they specified in the output report. The value(s) in the parameter are converted back to the original units after
        the report is generated. This is done so that the calculations are done in the units that GEOPHIRES expects. If
        the user wants to see the output in different units, they can specify that in the input file or the GUI.
    :type oparam: :class:`~geophires_x.Parameter.Parameter`
    :param newUnit: The new units you want to convert value to (like "m" or "feet") - this is the text that the user
        provides in the input file or the GUI to specify the units they want to use for a parameter or output value
        (like "m" or "feet")
    :type newUnit: str (text)
    :param model: The container class of the application, giving access to everything else, including the logger
    :type model: :class:`~geophires_x.Model.Model`
    :return: None
    """

    try:
        oparam.value = _ureg.Quantity(oparam.value, oparam.CurrentUnits.value).to(convertible_unit(newUnit.value)).magnitude
        oparam.CurrentUnits = newUnit
        return
    except AttributeError as ae:
        # TODO refactor to check for/convert currency instead of relying on try/except once currency conversion is
        #  re-enabled - https://github.com/NREL/GEOPHIRES-X/issues/236?title=Currency+conversions+disabled
        model.logger.warning(f'Failed to convert units with pint, falling back to legacy conversion code ({ae})')

    if isinstance(oparam.value, str):
        return  # strings have no units
    elif isinstance(oparam.value, bool):
        return  # booleans have no units
    DefUnit, UnitSystem = LookupUnits(str(newUnit.value))

    if UnitSystem not in [Units.CURRENCY, Units.CURRENCYFREQUENCY, Units.COSTPERMASS, Units.ENERGYCOST]:
        msg = (
                    "Warning: GEOPHIRES failed to initialize your units for "
                    + oparam.Name
                    + " to something it understands. You gave "
                    + str(newUnit.value)
                    + " -Are the units defined for"
                    + " Pint library, or have you defined them in the user defined units file (GEOPHIRES3_newunits)?"
                    + " Continuing without output conversion."
                )
        print(msg)
        model.logger.warning(msg)
        return

    else:
        prefType = oparam.PreferredUnits.value
        currType = newUnit.value

        # First we need to deal the possibility that there is a suffix on the units (like /yr, kwh, or /tonne)
        # that will make it not be recognized by the currency conversion engine.
        # generally, we will just strip the suffix off of a copy of the string that represents the units, then
        # allow the conversion to happen. For now, we ignore the suffix.
        # this has the consequence that we don't do any conversion based on that suffix, so units like EUR/MMBTU
        # will trigger a conversion to USD/MMBTU, where MMBY+TU doesn't get converted to KW (or whatever)
        currSuff = prefSuff = ""
        elements = str(currType).split("/")
        if len(elements) > 1:
            currType = elements[0]  # strip off the suffix, but save it
            currSuff = "/" + elements[1]
        elements = prefType.split("/")
        if len(elements) > 1:
            prefType = elements[0]  # strip off the suffix, but save it
            prefSuff = "/" + elements[1]

        # Let's try to deal with first the simple conversion where the required units have a prefix like M (m) or K (k)
        # that means a "million" or a "thousand", like MUSD (or KUSD), and the user provided USD (or KUSD) or KEUR, MEUR
        # we have to deal with the case that the M, m, K, or k are NOT prefixes, but rather
        # are a part of the currency name.
        cc = CurrencyCodes()
        currFactor = prefFactor = 1.0
        currPrefix = prefPrefix = False
        Factor = 1.0
        prefShort = prefType
        currShort = currType
        symbol = cc.get_symbol(
            prefType[1:]
        )  # if either of these returns a symbol, then we must have prefixes we need to deal with
        symbol2 = cc.get_symbol(currType[1:])
        if symbol is not None:
            prefPrefix = True
        if symbol2 is not None:
            currPrefix = True
        if prefPrefix and prefType[0] in ['M', 'm']:
            prefFactor = prefFactor * 1_000_000.0
        elif prefPrefix and prefType[0] in ['K', 'k']:
            prefFactor = prefFactor * 1000.0
        if currPrefix and currType[0] in ['M', 'm']:
            currFactor = currFactor / 1_000_000.0
        elif currPrefix and currType[0] in ['K', 'k']:
            currFactor = currFactor / 1000.0
        Factor = currFactor * prefFactor
        if prefPrefix:
            prefShort = prefType[1:]
        if currPrefix:
            currShort = currType[1:]
        if prefShort == currShort:
            # this is true, then we just have a conversion between KUSD and USD, MUSD to KUSD, MUER to EUR, etc.,
            # so just do the simple factor conversion and exit
            oparam.value = oparam.value * Factor
            oparam.CurrentUnits = DefUnit
            return

        # start the currency conversion process
        # if we have a symbol for a currency type, then the type is known to the library.
        # If we don't try some tricks to make it into something it does do recognize
        symbol = cc.get_symbol(currShort)
        if symbol is None:
            msg = (
                f'Error: GEOPHIRES failed to convert your currency for {oparam.Name} to something it understands.'
                f'You gave {currType} - conversion may be affected by https://github.com/NREL/GEOPHIRES-X/issues/236.  '
                f'Please change your units to {oparam.PreferredUnits.value} '
                f'to continue. Cannot continue unless you do.  Exiting.'
            )
            print(msg)
            model.logger.critical(msg)

            raise RuntimeError(msg)

        symbol = cc.get_symbol(prefShort)
        # if we have a symbol for a currency type, then the type is known to the library.  If we don't
        # try some tricks to make it into something it does do recognize
        if symbol is None:
            msg = (
                f'Error: GEOPHIRES failed to convert your currency for {oparam.Name} to something it understands.'
                f'You gave {currType} - conversion may be affected by https://github.com/NREL/GEOPHIRES-X/issues/236.  '
                f'Please change your units to {oparam.PreferredUnits.value} '
                f'to continue. Cannot continue unless you do.  Exiting.'
            )

            print(msg)
            model.logger.critical(msg)

            raise RuntimeError(msg)
        try:
            if _DISABLE_FOREX_API:
                raise RuntimeError('Forex API disabled')

            cr = CurrencyRates()
            conv_rate = cr.get_rate(prefShort, currShort)
        except BaseException as ex:
            print(str(ex))

            msg = (
                f'Error: GEOPHIRES failed to convert your currency for {oparam.Name} to something it understands. '
                f'You gave {currType} - conversion may be affected by https://github.com/NREL/GEOPHIRES-X/issues/236. '
                f'Please change your units to {oparam.PreferredUnits.value} '
                f'to continue. Cannot continue unless you do. Exiting.'
            )

            print(msg)

            model.logger.critical(str(ex))
            model.logger.critical(msg)

            raise RuntimeError(msg)

        oparam.value = Factor * conv_rate * float(oparam.value)
        oparam.CurrentUnits = DefUnit
        model.logger.info(f'Complete {str(__name__)}: {sys._getframe().f_code.co_name}')



def coerce_int_params_to_enum_values(parameter_dict:dict[str,Parameter]) -> None:
    """
    Some modules have intParameters with an int default value whose working value gets set to an
    enum when the parameter is read. If the parameter is not provided as an input, the default int value needs to
    be coerced into the corresponding enum value.
    TODO: resolve these enum/int value discrepancies so this workaround can be removed
    """

    for param_name, param in parameter_dict.items():
        if isinstance(param, intParameter):
            parameter_dict[param_name].coerce_value_to_enum()
