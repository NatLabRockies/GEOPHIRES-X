import json
import os
import sys
from pathlib import Path
from typing import Tuple, Any

# Ruff disabled because imports are order-dependent
# ruff: noqa: I001
from geophires_x.Model import Model
from geophires_x.SBTEconomics import SBTEconomics
from geophires_x.SBTReservoir import SBTReservoir
from geophires_x.SBTWellbores import SBTWellbores

from geophires_x.SFReservoir import SFReservoir
from geophires_x.LHSReservoir import LHSReservoir
from geophires_x.MPFReservoir import MPFReservoir
from geophires_x.AGSEconomics import AGSEconomics
from geophires_x.AGSWellBores import AGSWellBores
from geophires_x.CylindricalReservoir import CylindricalReservoir
from geophires_x.EconomicsAddOns import EconomicsAddOns
from geophires_x.GeoPHIRESUtils import json_dumpse
from geophires_x.Parameter import Parameter
from geophires_x.SurfacePlantAGS import SurfacePlantAGS
from geophires_x.SurfacePlantSUTRA import SurfacePlantSUTRA
from geophires_x.SUTRAEconomics import SUTRAEconomics
from geophires_x.SUTRAReservoir import SUTRAReservoir
from geophires_x.SUTRAWellBores import SUTRAWellBores
from geophires_x.TDPReservoir import TDPReservoir
from geophires_x.TOUGH2Reservoir import TOUGH2Reservoir
from geophires_x.UPPReservoir import UPPReservoir

# noinspection PyProtectedMember
from geophires_x_client import GeophiresXResult, _get_logger
from hip_ra_x.hip_ra_x import HIP_RA_X

_log = _get_logger()


class GeophiresXSchemaGenerator:
    def __init__(self):
        pass

    @staticmethod
    def _get_dummy_model():
        stash_cwd = Path.cwd()
        stash_sys_argv = sys.argv
        sys.argv = ['']
        try:
            dummy_model = Model(enable_geophires_logging_config=False)
            return dummy_model
        finally:
            sys.argv = stash_sys_argv
            os.chdir(stash_cwd)

    def get_parameter_sources(self) -> list:
        """
        :rtype: list[Tuple[Any, str]]
        """
        dummy_model = self._get_dummy_model()
        return [
            (dummy_model.reserv, 'Reservoir'),
            (TDPReservoir(dummy_model), 'Reservoir'),
            (LHSReservoir(dummy_model), 'Reservoir'),
            (MPFReservoir(dummy_model), 'Reservoir'),
            (SFReservoir(dummy_model), 'Reservoir'),
            (UPPReservoir(dummy_model), 'Reservoir'),
            (CylindricalReservoir(dummy_model), 'Reservoir'),
            (SBTReservoir(dummy_model), 'Reservoir'),
            (SUTRAReservoir(dummy_model), 'Reservoir'),
            (TOUGH2Reservoir(dummy_model), 'Reservoir'),
            (dummy_model.wellbores, 'Well Bores'),
            (AGSWellBores(dummy_model), 'Well Bores'),
            (SBTWellbores(dummy_model), 'Well Bores'),
            (SUTRAWellBores(dummy_model), 'Well Bores'),
            (dummy_model.surfaceplant, 'Surface Plant'),
            (SurfacePlantAGS(dummy_model), 'Surface Plant'),
            (SurfacePlantSUTRA(dummy_model), 'Surface Plant'),
            (dummy_model.economics, 'Economics'),
            (AGSEconomics(dummy_model), 'Economics'),
            (SBTEconomics(dummy_model), 'Economics'),
            (SUTRAEconomics(dummy_model), 'Economics'),
            (EconomicsAddOns(dummy_model), 'Economics'),
        ]

    def get_schema_title(self) -> str:
        return 'GEOPHIRES'

    def get_parameters_json(self) -> Tuple[str, str]:

        def with_category(param_dict: dict, category: str):
            def _with_cat(p: Parameter, cat: str):
                p.parameter_category = cat
                return p

            return {k: _with_cat(v, category) for k, v in param_dict.items()}

        parameter_sources = self.get_parameter_sources()
        output_params = {}
        input_params = {}
        for param_source in parameter_sources:
            input_params.update(with_category(param_source[0].ParameterDict, param_source[1]))
            output_params.update(with_category(param_source[0].OutputParameterDict, param_source[1]))

        return json_dumpse(input_params), json_dumpse(output_params)

    def generate_json_schema(self) -> Tuple[dict, dict]:
        """
        :return: request schema, result schema
        :rtype: Tuple[dict, dict]
        """
        input_params_json, output_params_json = self.get_parameters_json()
        input_params = json.loads(input_params_json)

        properties = {}
        required = []

        for param_name in input_params:
            param = input_params[param_name]

            units_val = param['CurrentUnits'] if isinstance(param['CurrentUnits'], str) else None
            min_val, max_val = _get_min_and_max(param, default_val=None)

            properties[param_name] = {
                'description': param['ToolTipText'],
                'type': param['json_parameter_type'],
                'units': units_val,
                'category': param['parameter_category'],
                'default': _fix_floating_point_error(param['DefaultValue']),
                'minimum': min_val,
                'maximum': max_val,
            }

            if param['Required']:
                required.append(param_name)

            if param['ValuesEnum']:
                properties[param_name]['enum_values'] = param['ValuesEnum']

        request_schema = {
            'definitions': {},
            '$schema': 'http://json-schema.org/draft-04/schema#',
            'type': 'object',
            'title': f'{self.get_schema_title()} Request Schema',
            'required': required,
            'properties': properties,
        }

        result_schema = self.get_result_json_schema(output_params_json)

        return request_schema, result_schema

    def get_result_json_schema(self, output_params_json) -> dict:
        properties = {}
        required = []

        output_params = json.loads(output_params_json)
        display_name_aliases = {}
        for param_name in output_params:
            if 'display_name' in output_params[param_name]:
                display_name = output_params[param_name]['display_name']
                if display_name not in [None, ''] and display_name != param_name:
                    # output_params[display_name] = output_params[param_name]
                    display_name_aliases[display_name] = output_params[param_name]
                    display_name_aliases[display_name]['output_parameter_name'] = param_name

        output_params = {**output_params, **display_name_aliases}

        # noinspection PyProtectedMember
        for category in GeophiresXResult._RESULT_FIELDS_BY_CATEGORY:
            cat_properties = {}
            # noinspection PyProtectedMember
            for field in GeophiresXResult._RESULT_FIELDS_BY_CATEGORY[category]:
                param_name = field if isinstance(field, str) else field.field_name

                ignored_output_param_names = ['After-Tax IRR']  # Silently ignored in favor of "After-tax IRR"

                if param_name in ignored_output_param_names:
                    continue

                if param_name in properties:
                    _log.warning(f'Param {param_name} is already in properties: {properties[param_name]}')

                param = {} if param_name not in properties else properties[param_name]

                if param_name in output_params:
                    output_param = output_params[param_name]
                    param['type'] = output_param['json_parameter_type']
                    description = output_param['ToolTipText']
                    if 'output_parameter_name' in output_param:
                        if description is not None and description != '':
                            description = f'{output_param["output_parameter_name"]}. {description}'
                        else:
                            description = output_param['output_parameter_name']
                    param['description'] = description
                    param['units'] = (
                        output_param['CurrentUnits'] if isinstance(output_param['CurrentUnits'], str) else None
                    )

                cat_properties[param_name] = param.copy()

            properties[category] = {'type': 'object', 'properties': cat_properties}

        result_schema = {
            'definitions': {},
            '$schema': 'http://json-schema.org/draft-04/schema#',
            'type': 'object',
            'title': f'{self.get_schema_title()} Result Schema',
            'required': required,
            'properties': properties,
        }

        return result_schema

    def generate_parameters_reference_rst(self) -> str:
        input_params_json, output_params_json = self.get_parameters_json()
        input_params: dict = json.loads(input_params_json)

        input_params_by_category: dict = {}
        for input_param_name, input_param in input_params.items():
            category: str = input_param['parameter_category']
            if category not in input_params_by_category:
                input_params_by_category[category] = {}  # []

            input_params_by_category[category][input_param_name] = input_param

        def get_input_params_table(_category_params, category_name) -> str:
            category_display = category_name if category_name is not None else ''
            _input_rst = f"""
{category_display}
{'-' * len(category_display)}
    .. list-table:: {category_display}{' ' if len(category_display) > 0 else ''}Parameters
       :header-rows: 1

       * - Name
         - Description
         - Preferred Units
         - Default Value Type
         - Default Value
         - Min
         - Max"""

            for param_name in _category_params:
                param = input_params[param_name]

                # if param['Required']:
                #     TODO designate required params

                default_value = _fix_floating_point_error(_get_key(param, 'DefaultValue'))

                min_val, max_val = _get_min_and_max(param)

                _input_rst += f"""\n       * - {param['Name']}
         - {_get_key(param, 'ToolTipText')}
         - {_get_key(param, 'PreferredUnits')}
         - {_get_key(param, 'json_parameter_type')}
         - {default_value}
         - {min_val}
         - {max_val}"""

            return _input_rst

        input_rst = ''
        for category, category_params in input_params_by_category.items():
            input_rst += get_input_params_table(category_params, category)

        output_rst = self.get_output_params_table_rst(output_params_json)

        schema_ref_base_url = (
            'https://github.com/softwareengineerprogrammer/GEOPHIRES/blob/main/src/geophires_x_schema_generator/'
        )
        input_schema_ref_rst = ''
        if self.get_input_schema_reference() is not None:
            input_schema_ref_rst = (
                f'Schema: '
                f'`{self.get_input_schema_reference()} '
                f'<{schema_ref_base_url}{self.get_input_schema_reference()}>`__'
            )

        output_schema_ref_rst = ''
        if self.get_output_schema_reference() is not None:
            output_schema_ref_rst = (
                f'Schema: '
                f'`{self.get_output_schema_reference()} '
                f'<{schema_ref_base_url}{self.get_output_schema_reference()}>`__'
            )

        display_title = f'{self.get_schema_title()} Parameters'
        rst = f"""{display_title}
{'=' * len(display_title)}

.. contents::

Input Parameters
################
{input_schema_ref_rst}
{input_rst}

Outputs
#######
{output_schema_ref_rst}
{output_rst}
"""

        return rst

    def get_output_params_table_rst(self, output_params_json) -> str:
        output_schema = self.get_result_json_schema(output_params_json)

        output_params_by_category: dict = {}

        for category, category_params in output_schema['properties'].items():
            if category not in output_params_by_category:
                output_params_by_category[category] = {}  # []

            for param_name, param in category_params['properties'].items():
                output_params_by_category[category][param_name] = param

        def get_output_params_table(_category_params, category_name) -> str:
            category_display = category_name if category_name is not None else ''
            category_display = category_display.replace(' (M$)', '').replace(' (M$/yr)', '')
            _output_rst = f"""
{category_display}
{'-' * len(category_display)}
    .. list-table:: {category_display}{' ' if len(category_display) > 0 else ''}Outputs
       :header-rows: 1

       * - Name
         - Description
         - Preferred Units
         - Default Value Type"""

            for _param_name, _param in _category_params.items():
                _output_rst += f"""\n       * - {_param_name}
         - {_get_key(_param, 'description')}
         - {_get_key(_param, 'units')}
         - {_get_key(_param, 'type')}"""

            return _output_rst

        output_rst = ''
        for category, category_params in output_params_by_category.items():
            output_rst += get_output_params_table(category_params, category)

        return output_rst

    def get_input_schema_reference(self) -> str:
        return 'geophires-request.json'

    def get_output_schema_reference(self) -> str:
        return 'geophires-result.json'


def _get_key(param: dict, k: str, default_val='') -> Any:
    if k in param and str(param[k]) != '':
        return param[k]
    else:
        return default_val


def _get_min_and_max(param: dict, default_val='') -> Tuple:
    min_val = _get_key(param, 'Min', default_val=default_val)
    max_val = _get_key(param, 'Max', default_val=default_val)

    if 'AllowableRange' in param:
        # TODO warn if min/max are defined and at odds with allowable range
        min_val = min(param['AllowableRange'])
        max_val = max(param['AllowableRange'])

    return _fix_floating_point_error(min_val), _fix_floating_point_error(max_val)


def _fix_floating_point_error(val: Any) -> Any:
    if '.0000' in str(val):
        return format(float(val), '.1f')

    return val


class HipRaXSchemaGenerator(GeophiresXSchemaGenerator):
    def get_parameter_sources(self) -> list:
        """
        :rtype: list[Tuple[Any, str]]
        """
        dummy_model = HIP_RA_X()
        return [(dummy_model, None)]

    def get_schema_title(self) -> str:
        return 'HIP-RA-X'

    def get_result_json_schema(self, output_params_json) -> dict:
        return None  # FIXME TODO

    def get_output_params_table_rst(self, output_params_json) -> str:
        """
        FIXME TODO consolidate with generated result schema
        """

        output_params = json.loads(output_params_json)

        output_rst = """
    .. list-table:: Outputs
       :header-rows: 1

       * - Name
         - Description
         - Preferred Units
         - Default Value Type"""

        for param_name in output_params:
            param = output_params[param_name]

            def get_key(k):
                if k in param and str(param[k]) != '':  # noqa
                    return param[k]  # noqa
                else:
                    return ''

            output_rst += f"""\n       * - {param['Name']}
         - {get_key('ToolTipText')}
         - {get_key('PreferredUnits')}
         - {get_key('json_parameter_type')}"""

        return output_rst

    def get_input_schema_reference(self) -> str:
        return 'hip-ra-x-request.json'

    def get_output_schema_reference(self) -> str:
        return None
