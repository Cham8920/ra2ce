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

from ra2ce.graph.hazard.hazard_intersect_builder_protocol import (
    HazardIntersectBuilderProtocol,
)
from networkx import Graph
from geopandas import GeoDataFrame
from ra2ce.graph.networks_utils import (
    graph_from_gdf,
    graph_to_gdf,
)
from pandas import read_csv


class HazardIntersectBuilderForTable(HazardIntersectBuilderProtocol):

    def get_intersection(self, hazard_overlay: GeoDataFrame | Graph) -> GeoDataFrame | Graph:
        return super().get_intersection(hazard_overlay)

    def _from_network_x(self, hazard_overlay: Graph) -> Graph:
        """Joins a table with IDs and hazard information with the road segments with corresponding IDs."""
        gdf, gdf_nodes = graph_to_gdf(hazard_overlay, save_nodes=True)
        gdf = self._from_geodataframe(gdf)

        # TODO: Check if the graph is created again correctly.
        hazard_overlay = graph_from_gdf(gdf, gdf_nodes)
        return hazard_overlay

    def _from_geodataframe(self, hazard_overlay: GeoDataFrame):
        """Joins a table with IDs and hazard information with the road segments with corresponding IDs."""
        for haz in self.hazard_files["table"]:
            if haz.suffix in [".csv"]:
                hazard_overlay = self.join_table(hazard_overlay, haz)
        return hazard_overlay

    def join_table(self, graph: Graph, hazard: str) -> Graph:
        df = read_csv(hazard)
        df = df[self._hazard_field_name]
        graph = graph.merge(
            df,
            how="left",
            left_on=self._network_file_id,
            right_on=self._hazard_id,
        )

        graph.rename(
            columns={
                self._hazard_field_name: [
                    n[:-3] for n in self.hazard_name_table[self._ra2ce_name_key]
                ][0]
            },
            inplace=True,
        )  # Check if this is the right name
        return graph
