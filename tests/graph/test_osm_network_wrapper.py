import shutil
from pathlib import Path

import networkx as nx
import pytest
from networkx import Graph, MultiDiGraph
from networkx.testing import assert_graphs_equal
from networkx.utils import graphs_equal
from shapely.geometry import LineString, Polygon
from shapely.geometry.base import BaseGeometry

from tests import test_data, slow_test
import ra2ce.graph.networks_utils as nut
from ra2ce.graph.osm_network_wrapper import OsmNetworkWrapper


class TestOsmNetworkWrapper:
    @pytest.fixture
    def _config_fixture(self) -> dict:
        _test_dir = test_data / "graph" / "test_osm_network_wrapper"

        yield {
            "static": _test_dir / "static",
            "network": {
                "polygon": "_test_polygon.geojson"
            },
            "origins_destinations": {
                "origins": None,
                "destinations": None,
                "origins_names": None,
                "destinations_names": None,
                "id_name_origin_destination": None,
                "category": "dummy_category",
                "region": "",
            },
            "cleanup": {"snapping_threshold": None, "segmentation_length": None},
        }

    @pytest.mark.parametrize("config", [
        pytest.param(None, id="NONE as dictionary"),
        pytest.param({}, id="Empty dictionary"),
        pytest.param({"network": {}}, id='"Empty Config["network"]"'),
        pytest.param({"network": "string"}, id='"invalid Config["network"] type"')
    ])
    def test_osm_network_wrapper_initialisation_with_invalid_config(self, config: dict):
        _files = []
        with pytest.raises(ValueError) as exc_err:
            OsmNetworkWrapper(config=config, graph_crs=None)
        assert str(exc_err.value) == "Config cannot be None" or \
               "A network dictionary is required for creating a OsmNetworkWrapper object" or \
               'Config["network"] should be a dictionary'

    def test_get_graph_from_osm_download_with_invalid_polygon_arg(self, _config_fixture: dict):
        _files = []
        # _network = Network(_config_fixture, _files)
        _osm_network = OsmNetworkWrapper(config=_config_fixture, graph_crs=None)
        _polygon = None
        _link_type = ""
        _network_type = ""
        with pytest.raises(AttributeError) as exc_err:
            _osm_network.get_graph_from_osm_download(_polygon, _link_type, _network_type)

        assert str(exc_err.value) == "'NoneType' object has no attribute 'is_valid'"

    def test_get_graph_from_osm_download_with_invalid_polygon_arg_geometry(self, _config_fixture: dict):
        _osm_network = OsmNetworkWrapper(config=_config_fixture, graph_crs=None)
        _polygon = LineString([[0, 0], [1, 0], [1, 1]])
        _link_type = ""
        _network_type = ""
        with pytest.raises(TypeError) as exc_err:
            _osm_network.get_graph_from_osm_download(_polygon, _link_type, _network_type)

        assert str(
            exc_err.value) == "Geometry must be a shapely Polygon or MultiPolygon. If you requested graph from place name, make sure your query resolves to a Polygon or MultiPolygon, and not some other geometry, like a Point. See OSMnx documentation for details."

    def test_get_graph_from_osm_download_with_invalid_network_type_arg(self, _config_fixture: dict):
        _osm_network = OsmNetworkWrapper(config=_config_fixture, graph_crs=None)
        _polygon = Polygon([(0., 0.), (0., 1.), (1., 1.), (1., 0.), (0., 0.)])
        _link_type = ""
        _network_type = ""
        with pytest.raises(ValueError) as exc_err:
            _osm_network.get_graph_from_osm_download(_polygon, _link_type, _network_type)

        assert str(exc_err.value) == 'Unrecognized network_type ""'

    @pytest.fixture
    def _valid_network_polygon_fixture(self) -> BaseGeometry:
        _test_input_directory = test_data.joinpath("graph", "test_osm_network_wrapper")
        _polygon_file = _test_input_directory.joinpath("_test_polygon.geojson")
        assert _polygon_file.exists()
        _polygon_dict = nut.read_geojson(_polygon_file)
        yield nut.geojson_to_shp(_polygon_dict)

    @slow_test
    def test_get_graph_from_osm_download_output(self, _config_fixture: dict,
                                                _valid_network_polygon_fixture: BaseGeometry):
        # 1. Define test data.
        _osm_network = OsmNetworkWrapper(config=_config_fixture, graph_crs=None)
        _link_type = ""
        _network_type = "drive"

        # 2. Run test.
        graph_complex = _osm_network.get_graph_from_osm_download(
            polygon=_valid_network_polygon_fixture,
            network_type=_network_type,
            link_type=_link_type
        )
        _osm_network.drop_duplicates(graph_complex)

        # 3. Verify expectations
        # reference: https://www.openstreetmap.org/node/1402598729#map=17/51.98816/4.39126&layers=T
        _osm_id_node_to_validate = 4987298323
        # reference: https://www.openstreetmap.org/way/334316041#map=19/51.98945/4.39166&layers=T
        _osm_id_edge_to_validate = 334316041

        assert isinstance(graph_complex, Graph)
        assert _osm_id_node_to_validate in list(graph_complex.nodes.keys())
        assert _osm_id_edge_to_validate in list(map(lambda x: x["osmid"], graph_complex.edges.values()))

    @pytest.mark.parametrize("config", [
        pytest.param({
            "static": Path(__file__).parent / "test_data" / "graph" / "test_osm_network_wrapper" / "static",
            "network": {"polygon": None}
        }, id="None polygon file"),
        pytest.param({
            "static": Path(__file__).parent / "test_data" / "graph" / "test_osm_network_wrapper" / "static",
            "network": {"polygon": "invalid_name"}
        }, id="Invalid polygon file name")
    ])
    def test_download_graph_from_osm_with_invalid_polygon_parameter(self, config: dict):
        _osm_network = OsmNetworkWrapper(config=config, graph_crs=None)
        with pytest.raises(FileNotFoundError) as exc_err:
            _osm_network.download_graph_from_osm()

        assert str(exc_err.value) == "No or invalid polygon file is introduced for OSM download" or \
               "No polygon_file file found"

    @pytest.fixture
    def _valid_graph_fixture(self) -> MultiDiGraph:
        _valid_graph = nx.MultiDiGraph()
        _valid_graph.add_node(1, x=1, y=10)
        _valid_graph.add_node(2, x=2, y=20)
        _valid_graph.add_node(3, x=1, y=10)
        _valid_graph.add_node(4, x=2, y=40)
        _valid_graph.add_node(5, x=3, y=50)

        _valid_graph.add_edge(1, 2, x=[1, 2], y=[10, 20])
        _valid_graph.add_edge(1, 3, x=[1, 1], y=[10, 10])
        _valid_graph.add_edge(2, 4, x=[2, 2], y=[20, 40])
        _valid_graph.add_edge(3, 4, x=[1, 2], y=[10, 40])
        _valid_graph.add_edge(1, 4, x=[1, 2], y=[10, 40])
        _valid_graph.add_edge(5, 3, x=[3, 1], y=[50, 10])
        _valid_graph.add_edge(5, 5, x=[3, 3], y=[50, 50])

        return _valid_graph

    @pytest.fixture
    def _valid_unique_graph_fixture(self) -> MultiDiGraph:
        _valid_unique_graph = nx.MultiDiGraph()
        _valid_unique_graph.add_node(1, x=1, y=10)
        _valid_unique_graph.add_node(2, x=2, y=20)
        _valid_unique_graph.add_node(4, x=2, y=40)
        _valid_unique_graph.add_node(5, x=3, y=50)

        _valid_unique_graph.add_edge(1, 2, x=[1, 2], y=[10, 20])
        _valid_unique_graph.add_edge(2, 4, x=[2, 2], y=[20, 40])
        _valid_unique_graph.add_edge(1, 4, x=[1, 2], y=[10, 40])
        _valid_unique_graph.add_edge(5, 1, x=[3, 1], y=[50, 10])

        return _valid_unique_graph

    def test_drop_duplicates_in_nodes(self, _valid_graph_fixture: MultiDiGraph,
                                      _valid_unique_graph_fixture: MultiDiGraph):
        unique_graph = OsmNetworkWrapper.drop_duplicates_in_nodes(graph=_valid_graph_fixture,
                                                                  unique_elements=None,
                                                                  unique_graph=None)

        assert unique_graph.nodes() == _valid_unique_graph_fixture.nodes()

    @pytest.mark.parametrize("unique_elements", [
        pytest.param(None, id="None unique_elements"),
        pytest.param(set(), id="Empty unique_elements")
    ])
    def test_drop_duplicates_in_edges_invalid_unique_elements_input(self, unique_elements,
                                                                    _valid_graph_fixture: MultiDiGraph,
                                                                    _valid_unique_graph_fixture: MultiDiGraph):
        with pytest.raises(ValueError) as exc_err:
            OsmNetworkWrapper.drop_duplicates_in_edges(graph=_valid_graph_fixture,
                                                       unique_elements=unique_elements
                                                       , unique_graph=None)

        assert str(exc_err.value) == """unique_elements cannot be None or empty. 
            Provide a set with all unique node coordinates as tuples of (x, y)"""

    def test_drop_duplicates_in_edges_invalid_unique_graph_input(self, _valid_graph_fixture: MultiDiGraph,
                                                                 _valid_unique_graph_fixture: MultiDiGraph):
        with pytest.raises(ValueError) as exc_err:
            OsmNetworkWrapper.drop_duplicates_in_edges(graph=_valid_graph_fixture,
                                                       unique_elements=set()
                                                       , unique_graph=None)

        assert str(exc_err.value) == """unique_graph cannot be None. Provide a graph with unique nodes or perform the 
        drop_duplicates_in_nodes on the graph to generate a unique_graph"""

    def test_drop_duplicates_in_edges(self, _valid_graph_fixture: MultiDiGraph,
                                      _valid_unique_graph_fixture: MultiDiGraph):
        # 1. Define test data.
        unique_elements = {(1, 10), (2, 20), (4, 40), (5, 50)}

        unique_graph = nx.MultiDiGraph()
        unique_graph.add_node(1, x=1, y=10)
        unique_graph.add_node(2, x=2, y=20)
        unique_graph.add_node(4, x=2, y=40)
        unique_graph.add_node(5, x=3, y=50)

        # 2. Run test.
        unique_graph = OsmNetworkWrapper.drop_duplicates_in_edges(graph=_valid_graph_fixture,
                                                                  unique_elements=unique_elements
                                                                  , unique_graph=unique_graph)

        # 3. Verify results
        assert graphs_equal(unique_graph, _valid_unique_graph_fixture)
