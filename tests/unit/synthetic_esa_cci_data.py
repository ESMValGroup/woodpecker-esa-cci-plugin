"""Synthetic ESA CCI datasets for the tests."""

from collections.abc import Mapping

import numpy as np
import xarray as xr

WKT = (
    'GEOGCS["WGS84(DD)", \n'
    '  DATUM["WGS84", \n'
    '    SPHEROID["WGS84", 6378137.0, 298.257223563]], \n'
    '  PRIMEM["Greenwich", 0.0], \n'
    '  UNIT["degree", 0.017453292519943295], \n'
    '  AXIS["Geodetic longitude", EAST], \n'
    '  AXIS["Geodetic latitude", NORTH]]'
)

# A 45 degree version of the 0.05 degree grid, with decreasing latitude and
# longitude in the range [-180, 180].
RESOLUTION = 45.0
LAT_BNDS = np.column_stack(
    [
        np.arange(90.0, -90.0, -RESOLUTION),
        np.arange(90.0 - RESOLUTION, -90.0 - RESOLUTION, -RESOLUTION),
    ]
)
LON_BNDS = np.column_stack(
    [
        np.arange(-180.0, 180.0, RESOLUTION),
        np.arange(-180.0 + RESOLUTION, 180.0 + RESOLUTION, RESOLUTION),
    ]
)
MONTHS = np.arange("2002-07", "2002-10", dtype="datetime64[M]")

GRID_ATTRS = {
    "reference_datum": "geographical coordinates, WGS84 projection",
    "valid_range": [-90.0, 90.0],
}
LAT_ATTRS = {**GRID_ATTRS, "units": "degrees_north"}
LON_ATTRS = {
    **GRID_ATTRS,
    "units": "degrees_east",
    "valid_range": [-180.0, 180.0],
}
TIME_ENCODING = {
    "dtype": np.dtype("int32"),
    "units": "days since 1970-01-01 +0:00",
    "calendar": "gregorian",
}
FLOAT_ENCODING = {"dtype": np.dtype("float32"), "_FillValue": np.nan}

GLOBAL_ATTRS = {
    "Conventions": "CF-1.7",
    "acknowledgement": (
        "The combined MW and NIR product was initiated and funded by the ESA "
        "Water_Vapour_cci project. The NIR retrieval was developed by "
        "Spectral Earth. The NIR data was processed by Brockmann Consult. NIR "
        "data is owned by Brockmann Consult and Spectral Earth."
    ),
    "cdm_data_type": "grid",
    "comment": (
        "These data were produced in the frame of the Water Vapour ECV "
        "(Water_Vapour_cci) of the ESA Climate Change Initiative Extension "
        "(CCI+) Phase 1."
    ),
    "creator_email": "climate.office@esa.int",
    "creator_name": (
        "ESA Water_Vapour_cci; Brockmann Consult; DWD; EUMETSAT/CM SAF; "
        "Spectral Earth"
    ),
    "creator_url": "http://cci.esa.int/watervapour",
    "date_created": "2022-01-27 12:24:10 UTC",
    "filename": "ESACCI-WATERVAPOUR-L3C-TCWV-meris-005deg-200207-fv3.2.nc",
    "format_version": "CCI Data Standards v2.0",
    "geospatial_lat_max": "90.0",
    "geospatial_lat_min": "-90.0",
    "geospatial_lat_resolution": "0.05",
    "geospatial_lat_units": "degrees_north",
    "geospatial_lon_max": "180.0",
    "geospatial_lon_min": "-180.0",
    "geospatial_lon_resolution": "0.05",
    "geospatial_lon_units": "degrees_east",
    "geospatial_vertical_max": "0.0",
    "geospatial_vertical_min": "0.0",
    "history": (
        "python nc-compliance-py-process.py "
        "/hd4/yarn/local/usercache/olaf/appcache/application_1640808937980_441"
        "00/container_1640808937980_44100_01_000002/l3_tcwv_meris_005deg_2002-"
        "07-01_2002-07-31.nc; converted to zarr on 8 Aug 2025"
    ),
    "id": "10.5285/4a85c0ef880e4f668cd4ec8e846855ef",
    "institution": "ESACCI",
    "key_variables": "tcwv",
    "keywords": (
        "EARTH SCIENCE > ATMOSPHERE > ATMOSPHERIC WATER VAPOR > WATER "
        "VAPOR,EARTH SCIENCE > ATMOSPHERE > ATMOSPHERIC WATER VAPOR > "
        "PRECIPITABLE WATER"
    ),
    "keywords-vocabulary": "GCMD Science Keywords, Version 8.1",
    "license": "ESA CCI Data Policy: free and open access",
    "naming-authority": "ESACCI",
    "platform": "Envisat, Terra, Sentinel-3",
    "product_version": "3.2",
    "project": "Climate Change Initiative - European Space Agency",
    "publisher_email": "climate.office@esa.int",
    "publisher_name": "ESACCI",
    "publisher_url": "https://climate.esa.int/en/esa-climate/esa-cci/",
    "references": (
        "WV_cci D2.2: ATBD Part 1 - MERIS-MODIS-OLCI L2 Products, Issue 2.1, "
        "21 January 2021; WV_cci D4.2: CRDP Issue 3.0, 11 August 2021 "
    ),
    "sensor": (
        "Medium Resolution Imaging Spectrometer; Moderate-Resolution Imaging "
        "Spectroradiometer; Ocean and Land Colour Instrument; Special Sensor "
        "Microwave Imager/Sounder"
    ),
    "source": (
        "Near-infrared Level 3 data over land from Brockmann Consult and "
        "Spectral Earth"
    ),
    "spatial_resolution": "5.6km at Equator",
    "standard_name_vocabulary": (
        "NetCDF Climate and Forecast (CF) Metadata Convention version 67"
    ),
    "summary": (
        "This global TCWV data record was generated from MERIS, MODIS and "
        "OLCI observations over land. The product covers the period 2002-2017 "
        "with daily and montlhy as well as 0.05° and 0.5° temporal and "
        "spatial resolutions, respectively."
    ),
    "time_coverage_end": "20171231 23:59:59 UTC",
    "time_coverage_resolution": "P1M",
    "time_coverage_start": "20020701 00:00:00 UTC",
    "title": (
        "Global Total Column of Water Vapour Product from Near Infrared "
        "Imagers"
    ),
    "tracking_id": "07bef376-7f6c-11ec-869e-002590086f26",
}


def _field(
    name: str,
    dtype: str,
    attrs: Mapping[str, object],
    encoding: Mapping[str, object],
    start: float = 0.0,
) -> xr.Variable:
    """Return a deterministic (time, lat, lon) variable."""
    shape = (MONTHS.size, LAT_BNDS.shape[0], LON_BNDS.shape[0])
    data = (start + np.arange(np.prod(shape))).reshape(shape).astype(dtype)
    if np.issubdtype(dtype, np.integer):
        # Stay within the valid range of flags.
        data %= 8
    else:
        # MERIS only observes land, so there are missing values.
        data[:, 0, 0] = np.nan
    variable = xr.Variable(
        ("time", "lat", "lon"),
        data,
        attrs={"standard_name": name, **attrs},
    )
    variable.encoding = dict(encoding)
    return variable


def make_tcwv_dataset() -> xr.Dataset:
    """Return a small ESA CCI water vapour dataset as loaded with xcube.

    It mimics ``ESACCI-WATERVAPOUR-L3C-TCWV-meris-005deg-2002-2017-fv3.2.zarr``
    from the xcube-cci ``ccizarr`` data store, including its problems.
    """
    time_bnds = np.column_stack(
        [MONTHS, MONTHS + np.timedelta64(1, "M") - np.timedelta64(1, "D")]
    ).astype("datetime64[ns]")
    time = MONTHS.astype("datetime64[ns]") + np.timedelta64(14, "D")
    lat = LAT_BNDS.mean(axis=1)
    lon = LON_BNDS.mean(axis=1)

    kg_m2 = {"units": "kg/m2"}
    dataset = xr.Dataset(
        {
            "crs": xr.Variable(
                (),
                np.int32(1178880137),
                attrs={
                    "comment": (
                        "A coordinate reference system (CRS) defines how the "
                        "georeferenced spatial data relates to real "
                        "locations on the Earth's surface "
                    ),
                    "i2m": "0.05,0.0,0.0,-0.05,-180.0,90.0",
                    "long_name": "Coordinate Reference System ",
                    "standard_name": "coordinate reference system",
                    "wkt": WKT,
                },
            ),
            "lat_bnds": xr.Variable(
                ("lat", "nv"),
                LAT_BNDS.astype("float32"),
                attrs={
                    "comment": (
                        "Contains the northern and southern boundaries of "
                        "the grid cells."
                    ),
                    "long_name": "latitude bounds",
                    "standard_name": "latitude bounds",
                    **LAT_ATTRS,
                },
            ),
            "lon_bnds": xr.Variable(
                ("lon", "nv"),
                LON_BNDS.astype("float32"),
                attrs={
                    "comment": (
                        "Contains the eastern and western boundaries of the "
                        "grid cells."
                    ),
                    "long_name": "longitude bounds",
                    "standard_name": "longitude bounds",
                    **LON_ATTRS,
                },
            ),
            "time_bnds": xr.Variable(
                ("time", "nv"),
                time_bnds,
                attrs={
                    "comment": (
                        "Contains the start and end times for the time "
                        "period the data represent."
                    ),
                    "long_name": "time bounds",
                    "standard_name": "time bounds",
                },
                encoding=TIME_ENCODING,
            ),
            "num_days_tcwv": _field(
                "num_days_tcwv",
                "float64",
                {
                    "long_name": (
                        "Number of days in month with a valid TCWV value in "
                        "L3 grid cell"
                    ),
                    "units": " ",
                },
                {"dtype": np.dtype("int32"), "_FillValue": np.int32(-1)},
            ),
            "num_obs": _field(
                "num_obs",
                "float32",
                {
                    "long_name": (
                        "Number of Total Column of Water Vapour retrievals "
                        "contributing to L3 grid cell"
                    ),
                    "units": " ",
                },
                FLOAT_ENCODING,
            ),
            "stdv": _field(
                "stdv",
                "float32",
                {
                    "long_name": (
                        "Standard deviation of Total Column of Water Vapour"
                    ),
                    **kg_m2,
                },
                FLOAT_ENCODING,
            ),
            "surface_type_flag": _field(
                "surface_type_flag",
                "int8",
                {
                    "flag_meanings": (
                        "LAND OCEAN CLOUD_OVER_LAND HEAVY_PRECIP_OVER_OCEAN "
                        "SEA_ICE COAST PARTLY_CLOUDY_OVER_LAND PARTLY_SEA_ICE"
                    ),
                    "flag_values": list(range(8)),
                    "long_name": "Surface type flag",
                    "units": " ",
                    "valid_range": [0, 7],
                },
                {"dtype": np.dtype("int8")},
            ),
            "tcwv": _field(
                "tcwv",
                "float32",
                {
                    "actual_range": [0.009999997913837433, 69.95999908447266],
                    "ancillary_variables": "stdv num_obs",
                    "long_name": "Total Column of Water",
                    **kg_m2,
                    "valid_range": [0.0, 70.0],
                },
                FLOAT_ENCODING,
                start=0.5,
            ),
            "tcwv_err": _field(
                "tcwv_err",
                "float32",
                {"long_name": "Average retrieval uncertainty", **kg_m2},
                FLOAT_ENCODING,
            ),
            "tcwv_ran": _field(
                "tcwv_ran",
                "float32",
                {"long_name": "Random retrieval uncertainty", **kg_m2},
                FLOAT_ENCODING,
            ),
        },
        coords={
            "lat": xr.Variable(
                "lat",
                lat,
                attrs={
                    "axis": "Y",
                    "bounds": "lat_bnds",
                    "long_name": "latitude",
                    "standard_name": "latitude",
                    **LAT_ATTRS,
                },
            ),
            "lon": xr.Variable(
                "lon",
                lon,
                attrs={
                    "axis": "X",
                    "bounds": "lon_bnds",
                    "long_name": "longitude",
                    "standard_name": "longitude",
                    **LON_ATTRS,
                },
            ),
            "time": xr.Variable(
                "time",
                time,
                attrs={
                    "axis": "T",
                    "bounds": "time_bnds",
                    "long_name": (
                        "Product dataset time given as days since 1970-01-01"
                    ),
                    "standard_name": "time",
                },
                encoding=TIME_ENCODING,
            ),
        },
        attrs=GLOBAL_ATTRS,
    )
    for name in ("lat", "lon"):
        dataset[name].encoding = {"dtype": np.dtype("float64")}
    for name in ("lat_bnds", "lon_bnds"):
        dataset[name].encoding = {"dtype": np.dtype("float32")}
    dataset["crs"].encoding = {"dtype": np.dtype("int32")}
    # The zarr store has one chunk per time step and several per grid.
    chunks = {"time": 1, "lat": 2, "lon": 4, "nv": -1}
    for var, variable in dataset.data_vars.items():
        if variable.ndim:
            dataset[var] = variable.chunk(
                {dim: chunks[str(dim)] for dim in variable.dims}
            )
    return dataset
