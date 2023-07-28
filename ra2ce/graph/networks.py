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
from typing import Any

import geopandas as gpd
import networkx as nx
import pyproj

from ra2ce.common.io.readers import GraphPickleReader
from ra2ce.graph import networks_utils as nut
from ra2ce.graph.exporters.network_exporter_factory import NetworkExporterFactory
from ra2ce.graph.network_config_data.network_config_data import NetworkConfigData
from ra2ce.graph.osm_network_wrapper.osm_network_wrapper import OsmNetworkWrapper
from ra2ce.graph.shp_network_wrapper.shp_network_wrapper import ShpNetworkWrapper
from ra2ce.graph.shp_network_wrapper.vector_network_wrapper import VectorNetworkWrapper
from ra2ce.graph.trails_network_wrapper.trails_network_wrapper import (
    TrailsNetworkWrapper,
)


class Network:
    """Network in GeoDataFrame or NetworkX format.

    Networks can be created from shapefiles, OSM PBF files, can be downloaded from OSM online or can be loaded from
    feather or gpickle files. Origin-destination nodes can be added.

    Attributes:
        config: A dictionary with the configuration details on how to create and adjust the network.
    """

    def __init__(self, network_config: NetworkConfigData, files: dict):
        # General
        self.project_name = network_config.project.name
        self.output_graph_dir = network_config.output_graph_dir
        if not self.output_graph_dir.is_dir():
            self.output_graph_dir.mkdir(parents=True)

        # Network
        self._network_dir = network_config.network_dir
        self.base_graph_crs = None  # Initiate variable
        self.base_network_crs = None  # Initiate variable

        self._network_config = network_config.network

        # Origins and destinations
        _origins_destinations = network_config.origins_destinations
        self.origins = _origins_destinations.origins
        self.destinations = _origins_destinations.destinations
        self.origins_names = _origins_destinations.origins_names
        self.destinations_names = _origins_destinations.destinations_names
        self.id_name_origin_destination = (
            _origins_destinations.id_name_origin_destination
        )
        self.origin_count = _origins_destinations.origin_count
        self.od_category = _origins_destinations.category
        self.region = _origins_destinations.region
        self.region_var = _origins_destinations.region_var

        # Cleanup
        self._cleanup = network_config.cleanup

        # files
        self.files = files

    def _any_cleanup_enabled(self) -> bool:
        return (
            self._cleanup.snapping_threshold
            or self._cleanup.pruning_threshold
            or self._cleanup.merge_lines
            or self._cleanup.cut_at_intersections
        )

    def _create_network_from_shp(
        self,
    ) -> tuple[nx.classes.graph.Graph, gpd.GeoDataFrame]:
        logging.info("Start creating a network from the submitted shapefile.")
        if self._any_cleanup_enabled():
            return self.network_shp()
        return self.network_cleanshp()

    def network_shp(
        self, crs: int = 4326
    ) -> tuple[nx.classes.graph.Graph, gpd.GeoDataFrame]:
        """Creates a (graph) network from a shapefile.

        Returns the same geometries for the network (GeoDataFrame) as for the graph (NetworkX graph), because
        it is assumed that the user wants to keep the same geometries as their shapefile input.

        Args:
            crs (int): the EPSG number of the coordinate reference system that is used

        Returns:
            graph_complex (NetworkX graph): The resulting graph.
            edges_complex (GeoDataFrame): The resulting network.
        """
        # Make a pyproj CRS from the EPSG code
        _shp_network_wrapper = ShpNetworkWrapper(
            network_options=self._network_config,
            cleanup_options=self._cleanup,
            region_path=self.region,
            crs_value=crs,
        )
        graph_complex, edges_complex = _shp_network_wrapper.get_network(
            self.output_graph_dir,
            self.project_name,
        )

        self.base_graph_crs = pyproj.CRS.from_user_input(crs)
        self.base_network_crs = pyproj.CRS.from_user_input(crs)

        # Exporting complex graph because the shapefile should be kept the same as much as possible.
        return graph_complex, edges_complex

    def network_cleanshp(self) -> tuple[nx.classes.graph.Graph, gpd.GeoDataFrame]:
        """Creates a (graph) network from a clean shapefile (primary_file - no further advance cleanup is needed)

        Returns the same geometries for the network (GeoDataFrame) as for the graph (NetworkX graph), because
        it is assumed that the user wants to keep the same geometries as their shapefile input.

        Returns:
            graph_complex (NetworkX graph): The resulting graph.
            edges_complex (GeoDataFrame): The resulting network.
        """
        # initialise vector network wrapper
        vector_network_wrapper = VectorNetworkWrapper(
            network_data=self._network_config,
            region_path=self.region,
            crs_value="",
        )

        # setup network using the wrapper
        (
            graph_complex,
            edges_complex,
        ) = vector_network_wrapper.get_network()

        # Set the CRS of the graph and network to wrapper crs
        self.base_graph_crs = vector_network_wrapper.crs
        self.base_network_crs = vector_network_wrapper.crs

        return graph_complex, edges_complex

    def network_osm_download(self) -> tuple[nx.classes.graph.Graph, gpd.GeoDataFrame]:
        """
        Creates a network from a polygon by downloading via the OSM API in the extent of the polygon.

        Returns:
            tuple[nx.classes.graph.Graph, gpd.GeoDataFrame]: Tuple of Simplified graph (for use in the indirect analyses) and Complex graph (for use in the direct analyses).
        """
        osm_network = OsmNetworkWrapper(
            network_data=self._network_config,
            graph_crs="",
            output_graph_dir=self.output_graph_dir,
        )
        graph_simple, edges_complex = osm_network.get_network()

        # No segmentation required, the non-simplified road segments from OSM are already small enough
        self.base_graph_crs = pyproj.CRS.from_user_input(
            "EPSG:4326"
        )  # Graphs from OSM download are always in this CRS.
        self.base_network_crs = pyproj.CRS.from_user_input(
            "EPSG:4326"
        )  # Graphs from OSM download are always in this CRS.

        return graph_simple, edges_complex

    def add_od_nodes(
        self, graph: nx.classes.graph.Graph, crs: pyproj.CRS
    ) -> nx.classes.graph.Graph:
        """Adds origins and destinations nodes from shapefiles to the graph.

        Args:
            graph (NetworkX graph): the NetworkX graph to which OD nodes should be added
            crs (int): the EPSG number of the coordinate reference system that is used

        Returns:
            graph (NetworkX graph): the NetworkX graph with OD nodes
        """
        from ra2ce.graph.origins_destinations import (
            add_od_nodes,
            read_origin_destination_files,
        )

        name = "origin_destination_table"

        # Add the origin/destination nodes to the network
        ods = read_origin_destination_files(
            str(self.origins),
            self.origins_names,
            str(self.destinations),
            self.destinations_names,
            self.id_name_origin_destination,
            self.origin_count,
            crs,
            self.od_category,
            self.region if self.region else "",
            self.region_var,
        )

        ods, graph = add_od_nodes(ods, graph, crs, self.od_category)
        ods.crs = crs

        # Save the OD pairs (GeoDataFrame) as pickle
        ods.to_feather(self.output_graph_dir.joinpath(name + ".feather"), index=False)
        logging.info(f"Saved {name + '.feather'} in {self.output_graph_dir}.")

        # Save the OD pairs (GeoDataFrame) as shapefile
        if self._network_config.save_shp:
            ods_path = self.output_graph_dir.joinpath(name + ".shp")
            ods.to_file(ods_path, index=False)
            logging.info(f"Saved {ods_path.stem} in {ods_path.resolve().parent}.")

        return graph

    def generate_origins_from_raster(self):
        """Adds origins and destinations nodes from shapefiles to the graph."""
        from ra2ce.graph.origins_destinations import origins_from_raster

        out_fn = origins_from_raster(
            self._network_dir,
            self._network_config.polygon,
            self.origins,
        )

        return out_fn

    def _export_network_files(
        self, network: Any, graph_name: str, types_to_export: list[str]
    ):
        _exporter = NetworkExporterFactory()
        _exporter.export(
            network=network,
            basename=graph_name,
            output_dir=self.output_graph_dir,
            export_types=types_to_export,
        )
        self.files[graph_name] = _exporter.get_pickle_path()

    def create(self) -> dict:
        """Handler function with the logic to call the right functions to create a network.

        Returns:
            (dict): A dict of a network (GeoDataFrame) and 1 (base NetworkX graph) or 2 graphs (base NetworkX and OD graph)
        """
        # Save the 'base' network as gpickle and if the user requested, also as shapefile.
        to_save = ["pickle"] if not self._network_config.save_shp else ["pickle", "shp"]
        od_graph = None
        base_graph = None
        network_gdf = None

        # For all graph and networks - check if it exists, otherwise, make the graph and/or network.
        if not (self.files["base_graph"] or self.files["base_network"]):
            # Create the network from the network source
            if self._network_config.source == "shapefile":
                base_graph, network_gdf = self._create_network_from_shp()
            elif self._network_config.source == "OSM PBF":
                logging.info(
                    """The original OSM PBF import is no longer supported. 
                                Instead, the beta version of package TRAILS is used. 
                                First stable release of TRAILS is expected in 2023."""
                )

                # base_graph, network_gdf = self.network_osm_pbf() #The old approach is depreciated
                base_graph, network_gdf = TrailsNetworkWrapper(
                    network_data=self._network_config, crs_value=4326
                ).get_network()

                self.base_network_crs = network_gdf.crs

            elif self._network_config.source == "OSM download":
                logging.info("Start downloading a network from OSM.")
                base_graph, network_gdf = self.network_osm_download()
            elif self._network_config.source == "pickle":
                logging.info("Start importing a network from pickle")
                base_graph = GraphPickleReader().read(
                    self.output_graph_dir.joinpath("base_graph.p")
                )
                network_gdf = gpd.read_feather(
                    self.output_graph_dir.joinpath("base_network.feather")
                )

                # Assuming the same CRS for both the network and graph
                self.base_graph_crs = pyproj.CRS.from_user_input(network_gdf.crs)
                self.base_network_crs = pyproj.CRS.from_user_input(network_gdf.crs)

            # Set the road lengths to meters for both the base_graph and network_gdf
            # TODO: rename "length" column to "length [m]" to be explicit
            edges_lengths_meters = {
                (e[0], e[1], e[2]): {
                    "length": nut.line_length(e[-1]["geometry"], self.base_graph_crs)
                }
                for e in base_graph.edges.data(keys=True)
            }
            nx.set_edge_attributes(base_graph, edges_lengths_meters)

            network_gdf["length"] = network_gdf["geometry"].apply(
                lambda x: nut.line_length(x, self.base_network_crs)
            )

            # Save the graph and geodataframe
            self._export_network_files(base_graph, "base_graph", to_save)
            self._export_network_files(network_gdf, "base_network", to_save)
        else:
            logging.info(
                "Apparently, you already did create a network with ra2ce earlier. "
                + "Ra2ce will use this: {}".format(self.files["base_graph"])
            )

            if self.files["base_graph"] is not None:
                base_graph = GraphPickleReader().read(self.files["base_graph"])
            else:
                base_graph = None

            if self.files["base_network"] is not None:
                network_gdf = gpd.read_feather(self.files["base_network"])
            else:
                network_gdf = None

            # Assuming the same CRS for both the network and graph
            self.base_graph_crs = pyproj.CRS.from_user_input(network_gdf.crs)
            self.base_network_crs = pyproj.CRS.from_user_input(network_gdf.crs)

        # create origins destinations graph
        if (
            (self.origins)
            and (self.destinations)
            and not self.files["origins_destinations_graph"]
        ):
            # reading the base graphs
            if self.files["base_graph"] and base_graph:
                base_graph = GraphPickleReader().read(self.files["base_graph"])
            # adding OD nodes
            if self.origins.suffix == ".tif":
                self.origins = self.generate_origins_from_raster()
            od_graph = self.add_od_nodes(base_graph, self.base_graph_crs)
            self._export_network_files(od_graph, "origins_destinations_graph", to_save)

        return {
            "base_graph": base_graph,
            "base_network": network_gdf,
            "origins_destinations_graph": od_graph,
        }
