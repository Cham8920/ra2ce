from pathlib import Path

import pytest

from ra2ce.analyses.analysis_config_data.analysis_config_data import AnalysisConfigData
from ra2ce.analyses.analysis_config_data.analysis_with_network_config_data import (
    AnalysisWithNetworkConfiguration,
)
from ra2ce.graph.network_config_wrapper import NetworkConfigWrapper
from tests import test_data


class TestAnalysisWithNetworkConfig:
    def test_from_data_no_file_raises(self):
        with pytest.raises(FileNotFoundError):
            AnalysisWithNetworkConfiguration.from_data(Path("not_a_file"), None)

    def test_initialize(self):
        _config = AnalysisWithNetworkConfiguration()
        assert isinstance(_config, AnalysisWithNetworkConfiguration)
        assert isinstance(_config.config_data, AnalysisConfigData)

    @pytest.fixture(autouse=False)
    def valid_analysis_ini(self) -> Path:
        _ini_file = test_data / "acceptance_test_data" / "analyses.ini"
        assert _ini_file.exists()
        return _ini_file

    def test_from_data(self, valid_analysis_ini: Path):
        # 1. Define test data.
        _config_data = AnalysisConfigData()

        # 2. Run test.
        _config = AnalysisWithNetworkConfiguration.from_data(
            valid_analysis_ini, _config_data
        )

        # 3. Verify final expectations.
        assert isinstance(_config, AnalysisWithNetworkConfiguration)
        assert _config.config_data == _config_data
        assert _config.ini_file == valid_analysis_ini

    def test_from_data_with_network(self, valid_analysis_ini: Path):
        # 1. Define test data.
        _config_data = AnalysisConfigData()
        _network_config = NetworkConfigWrapper()

        # 2. Run test.
        _config = AnalysisWithNetworkConfiguration.from_data_with_network(
            valid_analysis_ini, _config_data, _network_config
        )

        # 3. Verify final expectations.
        assert isinstance(_config, AnalysisWithNetworkConfiguration)
        assert _config.config_data == _config_data
        assert _config.ini_file == valid_analysis_ini
        assert _config._network_config == _network_config

    def test_configure(self, valid_analysis_ini: Path):
        # 1. Define test data.
        _config_data = AnalysisConfigData()
        _network_config = NetworkConfigWrapper()
        _config = AnalysisWithNetworkConfiguration.from_data_with_network(
            valid_analysis_ini, _config_data, _network_config
        )

        # 2. Run test.
        _config.configure()

    def test_is_valid(self, valid_analysis_ini: Path):
        # 1. Define test data.
        class DummyConfigData(AnalysisConfigData):
            def is_valid(self) -> bool:
                return True

        # 2. Run test.
        _result = AnalysisWithNetworkConfiguration.from_data(
            valid_analysis_ini, DummyConfigData()
        ).is_valid()

        # 3. Verify expectations
        assert _result is True
