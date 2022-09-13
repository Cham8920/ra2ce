from ra2ce.ra2ce import main
from tests import test_data


class TestAcceptance:
    def test_given_when(self):
        _network = test_data / "network.ini"
        _analysis = test_data / "analyses.ini"

        assert _network.is_file()
        assert _analysis.is_file()

        main(_network, _analysis)