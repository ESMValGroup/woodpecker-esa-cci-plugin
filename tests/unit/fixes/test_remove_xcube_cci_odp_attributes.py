import woodpecker
import xarray as xr
from woodpecker.fixes.registry import FixFunctionRegistry

from woodpecker_esa_cci_plugin.fixes.remove_xcube_cci_odp_attributes import (
    XCUBE_CCI_ODP_ATTRIBUTES,
)

FIX_ID = "esa_cci.remove_xcube_cci_odp_attributes"
# The history as set by the xcube-cci Open Data Portal store.
HISTORY = [
    {
        "program": "xcube_cci.chunkstore.CciChunkStore",
        "cube_params": {"time_range": ["2003-01-01T00:00:00", None]},
    }
]


def _xcube_cci_odp_attributes(dataset: xr.Dataset) -> dict[str, list[str]]:
    return {
        str(name): sorted(set(XCUBE_CCI_ODP_ATTRIBUTES) & set(variable.attrs))
        for name, variable in dataset.variables.items()
        if set(XCUBE_CCI_ODP_ATTRIBUTES) & set(variable.attrs)
    }


def test_fix_is_registered_through_entry_point() -> None:
    assert FIX_ID in FixFunctionRegistry.registered_ids()


def test_other_stores_are_not_changed(tcwv_dataset: xr.Dataset) -> None:
    assert isinstance(tcwv_dataset.attrs["history"], str)
    assert not woodpecker.check(tcwv_dataset, fixes=FIX_ID)


def test_attributes_are_removed(tcwv_dataset: xr.Dataset) -> None:
    # Like the variables in the xcube-cci Open Data Portal store.
    tcwv_dataset["tcwv"].attrs.update(
        orig_data_type="int16",
        fill_value=-32768,
        size=100,
        shape=[1, 10, 10],
        data_type="int16",
        dimensions=["time", "lat", "lon"],
    )
    tcwv_dataset["lat"].attrs.update(chunk_sizes=10, file_chunk_sizes=10)
    tcwv_dataset.attrs["history"] = HISTORY
    before = _xcube_cci_odp_attributes(tcwv_dataset)
    assert set(before) == {"tcwv", "lat"}

    findings = woodpecker.check(tcwv_dataset, fixes=FIX_ID)
    messages = [finding["message"] for finding in findings.findings]
    assert messages == [
        (
            "tcwv has attributes data_type, dimensions, fill_value, "
            "orig_data_type, shape, size"
        ),
        "lat has attributes chunk_sizes, file_chunk_sizes",
        "the history global attribute is not a string",
    ]

    preview = woodpecker.apply(tcwv_dataset, fixes=FIX_ID, dry_run=True)
    assert preview.changed == 1
    assert _xcube_cci_odp_attributes(tcwv_dataset) == before
    assert tcwv_dataset.attrs["history"] == HISTORY

    result = woodpecker.apply(tcwv_dataset, fixes=FIX_ID, dry_run=False)
    assert result.changed == 1
    assert not _xcube_cci_odp_attributes(tcwv_dataset)
    assert tcwv_dataset.attrs["history"] == (
        '{"program": "xcube_cci.chunkstore.CciChunkStore", "cube_params": '
        '{"time_range": ["2003-01-01T00:00:00", null]}}'
    )
    # Other attributes are kept.
    assert tcwv_dataset["tcwv"].attrs["units"] == "kg/m2"
    assert tcwv_dataset["lat"].attrs["units"] == "degrees_north"
    assert not woodpecker.check(tcwv_dataset, fixes=FIX_ID)


def test_history_string_is_kept(tcwv_dataset: xr.Dataset) -> None:
    tcwv_dataset["tcwv"].attrs["orig_data_type"] = "int16"
    tcwv_dataset.attrs["history"] = "Created by the ESA CCI processor"

    woodpecker.apply(tcwv_dataset, fixes=FIX_ID, dry_run=False)

    assert "orig_data_type" not in tcwv_dataset["tcwv"].attrs
    assert tcwv_dataset.attrs["history"] == "Created by the ESA CCI processor"
