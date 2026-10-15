import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--full-time-axis",
        action="store_true",
        help=(
            "Apply the recipes to all time steps of the Kerchunk and Open "
            "Data Portal datasets in the integration tests, instead of the "
            "first few. Select the datasets with -k."
        ),
    )


@pytest.fixture(scope="session")
def full_time_axis(pytestconfig: pytest.Config) -> bool:
    """Return whether to use all time steps of the datasets."""
    return bool(pytestconfig.getoption("--full-time-axis"))
