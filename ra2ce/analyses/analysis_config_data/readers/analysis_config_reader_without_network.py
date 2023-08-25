"""
                    GNU GENERAL PUBLIC LICENSE
                      Version 3, 29 June 2007

    Risk Assessment and Adaptation for Critical Infrastructure (RA2CE).
    Copyright (C) 2023 Stichting Deltares

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""


import logging
from pathlib import Path

from ra2ce.analyses.analysis_config_data.analysis_config_data import (
    AnalysisConfigDataWithoutNetwork,
)
from ra2ce.analyses.analysis_config_data.readers.analysis_config_reader_base import (
    AnalysisConfigReaderBase,
)
from ra2ce.analyses.analysis_config_wrapper.analysis_config_wrapper_base import (
    AnalysisConfigWrapperBase,
)
from ra2ce.graph.network_config_data.network_config_data_reader import (
    NetworkConfigDataReader,
)


class AnalysisConfigReaderWithoutNetwork(AnalysisConfigReaderBase):
    def read(self, ini_file: Path) -> AnalysisConfigDataWithoutNetwork:
        if not isinstance(ini_file, Path) or not ini_file.is_file():
            raise ValueError("No analysis ini file 'Path' provided.")
        _analisis_config_dict = self._get_analysis_config_data(ini_file)
        _output_network_ini_file = _analisis_config_dict["output"] / "network.ini"
        _network_config = NetworkConfigDataReader().read(_output_network_ini_file)
        _analisis_config_dict.update(_network_config.to_dict())
        _network = _analisis_config_dict.get("network", None)
        if _network:
            _analisis_config_dict["origins_destinations"] = _network.get(
                "origins_destinations", None
            )
        else:
            logging.warn(f"Not found network key for the Analysis {ini_file}")
        return AnalysisConfigDataWithoutNetwork.from_dict(_analisis_config_dict)

    def _get_analysis_config_data(self, ini_file: Path) -> dict:
        _root_path = AnalysisConfigWrapperBase.get_network_root_dir(ini_file)
        _config_data = self._import_configuration(_root_path, ini_file)
        _config_data = self._convert_analysis_types(_config_data)
        self._copy_output_files(ini_file, _config_data)
        return _config_data