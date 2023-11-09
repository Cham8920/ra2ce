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


from configparser import ConfigParser
from pathlib import Path

from ra2ce.analyses.analysis_config_data.analysis_config_data import (
    AnalysisConfigData,
    AnalysisConfigDataWithNetwork,
)
from ra2ce.analyses.analysis_config_data.readers.analysis_config_reader_base import (
    AnalysisConfigReaderBase,
)
from ra2ce.analyses.analysis_config_wrapper.analysis_config_wrapper_base import (
    AnalysisConfigWrapperBase,
)
from ra2ce.graph.network_config_wrapper import NetworkConfigWrapper


class AnalysisConfigReaderWithNetwork(AnalysisConfigReaderBase):
    _parser: ConfigParser
    _network_data: NetworkConfigWrapper

    def __init__(self, network_data: NetworkConfigWrapper) -> None:
        super().__init__()
        self._network_data = network_data
        if not network_data:
            raise ValueError(
                "Network data mandatory for an AnalysisIniConfigurationReader reader."
            )

    def read(self, ini_file: Path) -> AnalysisConfigDataWithNetwork:
        _config = super().read(ini_file)
        _config_data = AnalysisConfigDataWithNetwork(
            input_path=_config.input_path,
            output_path=_config.output_path,
            static_path=_config.static_path,
            project=_config.project,
            direct=_config.direct,
            indirect=_config.indirect,
        )
        self._copy_output_files(ini_file, _config_data)
        return _config_data
