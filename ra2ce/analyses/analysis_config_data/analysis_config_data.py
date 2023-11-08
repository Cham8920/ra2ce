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


from __future__ import annotations

from ra2ce.common.configuration.config_data_protocol import ConfigDataProtocol


class AnalysisConfigData(ConfigDataProtocol):
    @classmethod
    def from_dict(cls, dict_values: dict) -> AnalysisConfigData:
        _analysis_config = cls()
        _analysis_config.update(**dict_values)
        return _analysis_config


class AnalysisConfigDataWithNetwork(AnalysisConfigData):
    @classmethod
    def from_dict(cls, dict_values: dict) -> AnalysisConfigDataWithNetwork:
        return super().from_dict(dict_values)


class AnalysisConfigDataWithoutNetwork(AnalysisConfigData):
    @classmethod
    def from_dict(cls, dict_values: dict) -> AnalysisConfigDataWithoutNetwork:
        return super().from_dict(dict_values)
