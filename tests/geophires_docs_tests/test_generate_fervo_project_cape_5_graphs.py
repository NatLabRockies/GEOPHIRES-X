from __future__ import annotations

from base_test_case import BaseTestCase
from geophires_docs.generate_fervo_project_cape_5_graphs import _get_redrilling_event_indexes
from geophires_x_client import GeophiresInputParameters
from geophires_x_client import GeophiresXClient
from geophires_x_client import GeophiresXResult
from geophires_x_client import ImmutableGeophiresInputParameters


class FervoProjectCape5GraphsTestCase(BaseTestCase):

    def test_get_redrilling_event_indexes(self) -> None:
        input_params: GeophiresInputParameters = ImmutableGeophiresInputParameters(
            from_file_path=self._get_test_file_path('../examples/Fervo_Project_Cape-5.txt')
        )
        r: GeophiresXResult = GeophiresXClient().get_geophires_result(input_params)

        redrilling_indexes = _get_redrilling_event_indexes((input_params, r))
        self.assertEqual(
            r.result['ENGINEERING PARAMETERS']['Number of times redrilling']['value'], len(redrilling_indexes)
        )
