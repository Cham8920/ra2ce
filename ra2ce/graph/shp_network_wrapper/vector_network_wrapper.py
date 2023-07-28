import logging
from pathlib import Path

import networkx as nx
import pandas as pd
import geopandas as gpd
import momepy

from shapely.geometry import Point
from pyproj import CRS
from ra2ce.graph.network_config_data.network_config_data import NetworkSection
from ra2ce.graph.network_wrapper_protocol import NetworkWrapperProtocol
import ra2ce.graph.networks_utils as nut


class VectorNetworkWrapper(NetworkWrapperProtocol):
    """A class for handling and manipulating vector files.

    Provides methods for reading vector data, cleaning it, and setting up graph and
    network.
    """

    def __init__(
        self,
        network_data: NetworkSection,
        region_path: Path,
        crs_value: str,
    ) -> None:
        """Initializes the VectorNetworkWrapper object.

        Args:
            config (dict): Configuration dictionary.

        Raises:
            ValueError: If the config is None or doesn't contain a network dictionary,
                or if config['network'] is not a dictionary.
        """
        self.primary_files = network_data.primary_file
        self.directed = network_data.directed
        self.crs = CRS.from_user_input(crs_value if crs_value else "epsg:4326")
        self.region_path = region_path

    def get_network(
        self,
    ) -> tuple[nx.MultiGraph, gpd.GeoDataFrame]:
        """Gets a network built from vector files.

        Returns:
            nx.MultiGraph: MultiGraph representing the graph.
            gpd.GeoDataFrame: GeoDataFrame representing the network.
        """
        gdf = self._read_vector_to_project_region_and_crs()
        gdf = self.clean_vector(gdf)
        if self.directed:
            graph = self.get_direct_graph_from_vector(gdf)
        else:
            graph = self.get_indirect_graph_from_vector(gdf)
        edges, nodes = self.get_network_edges_and_nodes_from_graph(graph)
        graph_complex = nut.graph_from_gdf(edges, nodes, node_id="node_fid")
        return graph_complex, edges

    def _read_vector_to_project_region_and_crs(self) -> gpd.GeoDataFrame:
        gdf = self._read_files(self.primary_files)
        if gdf is None:
            logging.info("no file is read.")
            return None

        # set crs and reproject if needed
        if not gdf.crs and self.crs:
            gdf = gdf.set_crs(self.crs)
            logging.info("setting crs as default EPSG:4326. specify crs if incorrect")

        if self.crs:
            gdf = gdf.to_crs(self.crs)
            logging.info("reproject vector file to project crs")

        # clip for region
        if self.region_path:
            _region_gpd = self._read_files([self.region_path])
            gdf = gpd.overlay(gdf, _region_gpd, how="intersection", keep_geom_type=True)
            logging.info("clip vector file to project region")

        # validate
        if not any(gdf):
            logging.warning("No vector features found within project region")
            return None

        return gdf

    def _read_files(self, file_list: list[Path]) -> gpd.GeoDataFrame:
        """Reads a list of files into a GeoDataFrame.

        Args:
            file_list (list[Path]): List of file paths.

        Returns:
            gpd.GeoDataFrame: GeoDataFrame representing the data.
        """
        # read file
        gdf = gpd.GeoDataFrame(pd.concat(list(map(gpd.read_file, file_list))))
        logging.info(
            "Read files {} into a 'GeoDataFrame'.".format(
                ", ".join(map(str, file_list))
            )
        )
        return gdf

    @staticmethod
    def get_direct_graph_from_vector(gdf: gpd.GeoDataFrame) -> nx.DiGraph:
        """Creates a simple directed graph with node and edge geometries based on a given GeoDataFrame.

        Args:
            gdf (gpd.GeoDataFrame): Input GeoDataFrame containing line geometries.
                Allow both LineString and MultiLineString.

        Returns:
            nx.DiGraph: NetworkX graph object with "crs", "approach" as graph properties.
        """

        # simple geometry handeling
        gdf = VectorNetworkWrapper.explode_and_deduplicate_geometries(gdf)

        # to graph
        digraph = nx.DiGraph(crs=gdf.crs, approach="primal")
        for _, row in gdf.iterrows():
            from_node = row.geometry.coords[0]
            to_node = row.geometry.coords[-1]
            digraph.add_node(from_node, geometry=Point(from_node))
            digraph.add_node(to_node, geometry=Point(to_node))
            digraph.add_edge(
                from_node,
                to_node,
                geometry=row.pop(
                    "geometry"
                ),  # **row TODO: check if we do need all columns
            )

        return digraph

    @staticmethod
    def get_indirect_graph_from_vector(gdf: gpd.GeoDataFrame) -> nx.Graph:
        """Creates a simple undirected graph with node and edge geometries based on a given GeoDataFrame.

        Args:
            gdf (gpd.GeoDataFrame): Input GeoDataFrame containing line geometries.
                Allow both LineString and MultiLineString.

        Returns:
            nx.Graph: NetworkX graph object with "crs", "approach" as graph properties.
        """
        digraph = VectorNetworkWrapper.get_direct_graph_from_vector(gdf)
        return digraph.to_undirected()

    @staticmethod
    def get_network_edges_and_nodes_from_graph(
        graph: nx.Graph,
    ) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
        """Sets up network nodes and edges from a given graph.

        Args:
            graph (nx.Graph): Input graph with geometry for nodes and edges.
                Must contain "crs" as graph property.

        Returns:
            gpd.GeoDataFrame: GeoDataFrame representing the network edges with "edge_fid", "node_A", and "node_B".
            gpd.GeoDataFrame: GeoDataFrame representing the network nodes with "node_fid".
        """

        # TODO ths function use conventions. Good to make consistant convention with osm
        nodes, edges = momepy.nx_to_gdf(graph, nodeID="node_fid")
        edges["edge_fid"] = (
            edges["node_start"].astype(str) + "_" + edges["node_end"].astype(str)
        )
        edges.rename(
            {"node_start": "node_A", "node_end": "node_B"}, axis=1, inplace=True
        )
        if not nodes.crs:
            nodes.crs = graph.graph["crs"]
        if not edges.crs:
            edges.crs = graph.graph["crs"]
        return edges, nodes

    @staticmethod
    def clean_vector(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Cleans a GeoDataFrame.

        Args:
            gdf (gpd.GeoDataFrame): Input GeoDataFrame.

        Returns:
            gpd.GeoDataFrame: Cleaned GeoDataFrame.
        """

        gdf = VectorNetworkWrapper.explode_and_deduplicate_geometries(gdf)

        return gdf

    @staticmethod
    def explode_and_deduplicate_geometries(gpd: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Explodes and deduplicates geometries a GeoDataFrame.

        Args:
            gpd (gpd.GeoDataFrame): Input GeoDataFrame.

        Returns:
            gpd.GeoDataFrame: GeoDataFrame with exploded and deduplicated geometries.
        """
        gpd = gpd.explode()
        gpd = gpd[
            gpd.index.isin(
                gpd.geometry.apply(lambda geom: geom.wkb).drop_duplicates().index
            )
        ]
        return gpd
