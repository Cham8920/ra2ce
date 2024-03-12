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

from pathlib import Path

import pandas as pd

FILE_NAME_KEY = "File name"
RA2CE_NAME_KEY = "RA2CE name"


class HazardNames:
    names_df: pd.DataFrame
    names: list[str]

    def __init__(self, hazard_names_df: pd.DataFrame, hazard_names: list[str]) -> None:
        self.names_df = hazard_names_df
        self.names = hazard_names

    @classmethod
    def from_file(cls, hazard_names_file: Path) -> HazardNames:
        """
        Create a HazardNames object from a file.

        Args:
            hazard_names_file (Path): Path to the files with the hazard names.

        Returns:
            HazardNames: HazardNames object.
        """
        if hazard_names_file.is_file():
            _names_df = pd.read_excel(hazard_names_file)
            _names = _names_df[FILE_NAME_KEY].tolist()
        else:
            _names_df = pd.DataFrame(data=None)
            _names = []
        return cls(_names_df, _names)

    def get_name(self, hazard: str) -> str:
        """
        Get the RA2CE name of a specific hazard.

        Args:
            hazard (str): Name of the hazard.

        Returns:
            str: RA2CE name of the hazard.
        """
        return self.names_df.loc[
            self.names_df[FILE_NAME_KEY] == hazard,
            RA2CE_NAME_KEY,
        ].values[0]
