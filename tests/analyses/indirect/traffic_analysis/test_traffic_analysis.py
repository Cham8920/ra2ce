from ra2ce.analyses.indirect.traffic_analysis.accumulated_traffic_dataclass import (
    AccumulatedTraffic,
)
from ra2ce.analyses.indirect.traffic_analysis.traffic_analysis import TrafficAnalysis
import pytest
from tests.analyses.indirect.traffic_analysis import (
    TrafficAnalysisInput,
    valid_traffic_analysis_input,
    _equity_test_data,
)
from tests import slow_test, test_results, test_data
import pandas as pd


class TestTrafficAnalysis:
    @pytest.fixture
    def valid_traffic_analysis(
        self,
        valid_traffic_analysis_input: TrafficAnalysisInput,
    ) -> TrafficAnalysis:
        yield TrafficAnalysis(
            valid_traffic_analysis_input.gdf_data,
            valid_traffic_analysis_input.od_table_data,
            valid_traffic_analysis_input.destination_names,
        )

    @slow_test
    def test_equity_analysis_with_valid_data(
        self,
        valid_traffic_analysis: TrafficAnalysis,
        request: pytest.FixtureRequest,
    ):
        # 1. Define test data.
        _test_result = test_results.joinpath(request.node.name + ".csv")
        if _test_result.exists():
            _test_result.unlink()

        # Define expected results.
        _expected_result = pd.read_csv(
            _equity_test_data.joinpath("expected_result_without_equity.csv"),
            index_col=0,
            dtype={
                "u": str,
                "v": str,
                "traffic": float,
                "traffic_egalitarian": float,
            },
        )
        assert isinstance(_expected_result, pd.DataFrame)
        assert len(_expected_result.values) == 359

        # 2. Run test.
        _result = valid_traffic_analysis.optimal_route_od_link()

        # 3. Verify expectations.
        assert isinstance(_result, pd.DataFrame)
        _result.to_csv(_test_result)

        assert not any(_result[["u", "v"]].duplicated())
        pd.testing.assert_frame_equal(_expected_result, _result)

    def test_traffic_analysis_get_accumulated_traffic_from_node(
        self, valid_traffic_analysis: TrafficAnalysis
    ):
        # 1. Define test data.
        # Get some valid data, we will only check the type of output for this method.
        _total_d_nodes = 42
        _o_node = "A_22"

        # 2. Run test.
        _accumulated_traffic = (
            valid_traffic_analysis._get_accumulated_traffic_from_node(
                _o_node, _total_d_nodes
            )
        )

        # 3. Verify expectations.
        assert isinstance(_accumulated_traffic, AccumulatedTraffic)
        assert _accumulated_traffic.egalitarian == 1
        assert _accumulated_traffic.prioritarian == 0
        assert _accumulated_traffic.regular == pytest.approx(3.1097, 0.0001)
