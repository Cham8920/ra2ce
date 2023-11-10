from ra2ce.analyses.analysis_config_data.analysis_config_data import (
    AnalysisConfigData,
    AnalysisSectionDirect,
)
from ra2ce.analyses.direct.analyses_direct import DirectAnalyses
from tests import test_data


class TestDirectAnalyses:
    def test_init(self):
        _config = {}
        _graphs = {}
        _analyses = DirectAnalyses(_config, _graphs)
        assert isinstance(_analyses, DirectAnalyses)

    def test_execute(self):
        _config = AnalysisConfigData(
            direct=[
                AnalysisSectionDirect(
                    name="DummyExecute", analysis="", save_gpkg=False, save_csv=False
                )
            ],
            output_path=test_data,
        ).to_dict()
        _graphs = {}
        DirectAnalyses(_config, _graphs).execute()
