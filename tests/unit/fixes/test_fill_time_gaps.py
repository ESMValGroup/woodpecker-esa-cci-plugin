import numpy as np
import pytest
import woodpecker
import xarray as xr
from woodpecker.fixes.registry import FixFunctionRegistry

FIX_ID = "esa_cci.fill_time_gaps"
OPTIONS = {FIX_ID: {"coordinate": "time", "frequency": "mon"}}
CENTER_TIME = {"esa_cci.center_time": {"coordinate": "time"}}
# The months of the synthetic dataset, centered by esa_cci.center_time.
MIDDLE = np.array(
    ["2002-07-16T12", "2002-08-16T12", "2002-09-16"], dtype="datetime64[ns]"
)
BOUNDS = np.arange("2002-07", "2002-11", dtype="datetime64[M]")


@pytest.fixture
def dataset(tcwv_dataset: xr.Dataset) -> xr.Dataset:
    """Return the synthetic dataset without its second month."""
    woodpecker.apply(
        tcwv_dataset,
        fixes="esa_cci.center_time",
        dry_run=False,
        options=CENTER_TIME,
    )
    return tcwv_dataset.isel(time=[0, 2])


def _undecode(dataset: xr.Dataset) -> None:
    for name in ("time", "time_bnds"):
        dataset[name] = xr.conventions.encode_cf_variable(
            dataset[name].variable, name=name
        )


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_unconfigured_fix_does_nothing(dataset: xr.Dataset) -> None:
    assert not woodpecker.check(dataset, fixes=FIX_ID)


def test_time_without_gaps_is_unchanged(tcwv_dataset: xr.Dataset) -> None:
    assert not woodpecker.check(tcwv_dataset, fixes=FIX_ID, options=OPTIONS)


@pytest.mark.parametrize(
    "decode_times", [True, False], ids=["decoded", "not_decoded"]
)
def test_gaps_are_filled(
    dataset: xr.Dataset,
    decode_times: bool,  # noqa: FBT001
) -> None:
    if not decode_times:
        _undecode(dataset)
    original = dataset.copy(deep=True)

    findings = woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)
    assert findings.fix_ids == (FIX_ID,)
    messages = [finding["message"] for finding in findings.findings]
    assert messages == ["time has no time point in 1 months"]

    preview = woodpecker.apply(
        dataset, fixes=FIX_ID, dry_run=True, options=OPTIONS
    )
    assert preview.changed == 1
    xr.testing.assert_identical(dataset, original)

    woodpecker.apply(dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS)
    assert dataset.sizes["time"] == 3
    decoded = xr.decode_cf(dataset) if not decode_times else dataset
    np.testing.assert_array_equal(decoded["time"], MIDDLE)
    np.testing.assert_array_equal(
        decoded["time_bnds"],
        np.stack([BOUNDS[:-1], BOUNDS[1:]], axis=1).astype("datetime64[ns]"),
    )
    assert dataset["time"].attrs == original["time"].attrs
    assert dataset["time"].encoding == original["time"].encoding
    # The added month is missing, and the others are unchanged.
    assert dataset["tcwv"].isel(time=1).isnull().all()
    xr.testing.assert_identical(
        dataset["tcwv"].isel(time=[0, 2]), original["tcwv"]
    )
    # Variables without a time dimension are kept.
    assert set(dataset.variables) == set(original.variables)
    assert not woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)


def test_empty_time_is_unchanged(dataset: xr.Dataset) -> None:
    dataset = dataset.isel(time=slice(0))

    assert not woodpecker.check(dataset, fixes=FIX_ID, options=OPTIONS)


def test_bounds_with_time_last_are_filled(dataset: xr.Dataset) -> None:
    dataset["time_bnds"] = dataset["time_bnds"].T

    woodpecker.apply(dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS)
    assert dataset["time_bnds"].dims[1] == "time"
    np.testing.assert_array_equal(
        dataset["time_bnds"].T,
        np.stack([BOUNDS[:-1], BOUNDS[1:]], axis=1).astype("datetime64[ns]"),
    )


def test_data_stays_lazy(dataset: xr.Dataset) -> None:
    dataset = dataset.chunk()

    woodpecker.apply(dataset, fixes=FIX_ID, dry_run=False, options=OPTIONS)
    assert dataset["tcwv"].chunks is not None


def test_daily_gaps_are_filled() -> None:
    days = np.array(["2002-07-01", "2002-07-04"], dtype="datetime64[ns]")
    dataset = xr.Dataset(
        {"tcwv": ("time", np.ones(2, dtype="float32"))},
        coords={"time": ("time", days + np.timedelta64(12, "h"))},
    )
    options = {FIX_ID: {"coordinate": "time", "frequency": "day"}}

    woodpecker.apply(dataset, fixes=FIX_ID, dry_run=False, options=options)
    assert dataset.sizes["time"] == 4
    assert "time_bnds" not in dataset


@pytest.mark.parametrize(
    ("coordinate", "match"),
    [
        ("missing", "it does not exist"),
        ("time_bnds", "it is not a dimension coordinate"),
    ],
)
def test_invalid_coordinate_raises(
    dataset: xr.Dataset, coordinate: str, match: str
) -> None:
    options = {FIX_ID: {"coordinate": coordinate}}

    with pytest.raises(ValueError, match=match):
        woodpecker.check(dataset, fixes=FIX_ID, options=options)
