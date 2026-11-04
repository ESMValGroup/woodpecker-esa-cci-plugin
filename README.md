# woodpecker-esa-cci-plugin

[![codecov](https://codecov.io/gh/esmvalgroup/woodpecker-esa-cci-plugin/graph/badge.svg)](https://codecov.io/gh/esmvalgroup/woodpecker-esa-cci-plugin)

ESA CCI fixes and recipes for
[Woodpecker](https://github.com/roocs/woodpecker).

## Contents

- [Usage](#usage)
  - [Datasets with several variables](#datasets-with-several-variables)
  - [Memory use](#memory-use)
- [Supported datasets](#supported-datasets)
  - [Water vapour](#water-vapour)
  - [Sea surface temperature](#sea-surface-temperature)
  - [Sea surface salinity](#sea-surface-salinity)
  - [Cloud](#cloud)
  - [Aerosol](#aerosol)
  - [Snow](#snow)
  - [Sea ice concentration](#sea-ice-concentration)
  - [Sea ice thickness](#sea-ice-thickness)
  - [Ozone](#ozone)
  - [Ocean colour](#ocean-colour)
- [Uncertainties](#uncertainties)
- [Known data problems](#known-data-problems)
  - [Time steps in the Open Data Portal store](#time-steps-in-the-open-data-portal-store)
  - [Values](#values)
- [Recipes and fixes](#recipes-and-fixes)
- [Contributing](#contributing)
- [License](#license)

## Usage

Install this plugin together with woodpecker, and woodpecker finds its
fixes and recipes automatically. For example, to fix the ESA CCI water
vapour dataset from the
[ESA CCI Open Data Portal](https://climate.esa.int/en/data/), which needs
[s3fs](https://s3fs.readthedocs.io) to open the zarr store:

```python
import woodpecker
import xarray as xr
from woodpecker.io.backends.xr import XarrayInput

data_id = "ESACCI-WATERVAPOUR-L3C-TCWV-meris-005deg-2002-2017-fv3.2.zarr"
dataset = xr.open_zarr(
    f"s3://esacci/{data_id}",
    chunks="auto",
    storage_options={
        "anon": True,
        "client_kwargs": {
            "endpoint_url": "https://cci-ke-o.s3-ext.jc.rl.ac.uk",
        },
    },
)

# Woodpecker selects the recipe by matching the recipe path patterns
# against the input name, and fixes the dataset in place.
woodpecker.recipe.apply(
    XarrayInput(payload=dataset, name=data_id),
    woodpecker.recipe.catalog(),
    dry_run=False,
)

# Write the first month.
dataset.isel(time=0).to_netcdf("prw.nc")
```

The data stays lazy, so only the part that is written is downloaded. Use
`woodpecker.recipe.check` instead of `woodpecker.recipe.apply` to list the
problems without fixing them.

### Datasets with several variables

The cloud and aerosol datasets provide several variables, each from its own
recipe, named `esa_cci.<essential climate variable>_<variable>`, e.g.
`esa_cci.cloud_clt`, with a `_daily` suffix for the daily aerosol
datasets. Woodpecker raises an error when several recipes match, so pass
the recipe id:

```python
woodpecker.recipe.apply(
    XarrayInput(payload=dataset, name=data_id),
    woodpecker.recipe.catalog(),
    recipe_id="esa_cci.cloud_clt",
    dry_run=False,
)
```

Each recipe keeps only its own variable, so open the dataset again for each
variable.

### Memory use

The 0.05° daily datasets have storage chunks of a few MB, so with those as
dask chunks, each recipe step adds hundreds of thousands of tasks to the
dask graph, which takes several GB of memory. Use dask chunks of ~128 MB
instead: pass `chunks="auto"` to `xr.open_zarr`, or rechunk datasets
from the xcube-cci Kerchunk and Open Data Portal stores, which have no
option for the chunks, before applying the recipe:

```python
from xcube.core.store import new_data_store

data_id = (
    "esacci.WATERVAPOUR.day.L3S.TCWV.multi-sensor.multi-platform."
    "TCWV_land_005deg.3-2.r1"
)
dataset = new_data_store("cciodp").open_data(data_id).chunk("auto")
```

The ocean colour `OC_PRODUCTS` datasets contain about 90 variables, and the
recipes keep only `chlor_a` and its uncertainties. Opening all variables of
the daily dataset from the Open Data Portal store takes more than 3 GB, so
pass the variables to keep:

```python
dataset = new_data_store("cciodp").open_data(
    "esacci.OC.day.L3S.OC_PRODUCTS.multi-sensor.multi-platform.MERGED."
    "6-0.geographic",
    variable_names=[
        "chlor_a",
        "chlor_a_log10_rmsd",
        "chlor_a_log10_bias",
        "total_nobs",
    ],
)
```

## Supported datasets

This plugin supports the following datasets from the ESA CCI Open Data
Portal. They are available from three stores, which the
[xcube ESA CCI plugin](https://github.com/esa-cci/xcube-cci) opens as the
`ccizarr`, `ccikc` and `cciodp` data stores. The data id is the name to
pass to woodpecker.

Datasets in which some calendar months or days have no data, such as the
AVHRR afternoon orbit cloud dataset, get those time steps, with missing
values, as CMIP7 requires a time coordinate without gaps.

Some of these datasets have [known data problems](#known-data-problems).

For the CMIP7 variables that other ESA CCI datasets could provide, see
[docs/cmip7_variable_mapping.md](docs/cmip7_variable_mapping.md).

### Water vapour

Water vapour, total column, as the CMIP7 variable `prw`:

- zarr store: `ESACCI-WATERVAPOUR-L3C-TCWV-meris-005deg-2002-2017-fv3.2.zarr`
- Kerchunk store, daily and monthly v3.2 at 0.05° and 0.5°:
  `ESACCI-WATERVAPOUR-L3C-TCWV-meris-*-fv3.2-kr1.1`
- Open Data Portal store, daily and monthly v3.2 and v4.2 at 0.05° and
  0.5°:
  `esacci.WATERVAPOUR.{day,mon}.L3S.TCWV.multi-sensor.multi-platform.TCWV_land_*.{3-2,4-2}.r1`

### Sea surface temperature

Sea surface temperature, daily level 4 analyses, as the CMIP7 variable
`tos`:

- zarr store, GMPE:
  `ESACCI-L4_GHRSST-SST-GMPE-GLOB_CDR2.0-1981-2016-v02.0-fv01.0.zarr`
- Open Data Portal store, GMPE and OSTIA:
  `esacci.SST.day.L4.SSTskin.Unspecified.Unspecified.GMPE.2-0.r1`,
  `esacci.SST.day.L4.SSTdepth.multi-sensor.multi-platform.OSTIA.1-1.r1`
  and `esacci.SST.day.L4.SSTdepth.multi-sensor.multi-platform.OSTIA.2-1.sst`

### Sea surface salinity

Sea surface salinity, monthly level 4 analyses, as the CMIP7 variable `sos`,
from the 30-day means centred on the 15th of each month. The datasets also
have the overlapping 30-day means centred on the 1st, which the recipe
removes:

- Kerchunk store, v2.31, v3.21, v4.41 and v5.5:
  `ESACCI-SEASURFACESALINITY-L4-SSS-{,GLOBAL-}MERGED_OI_Monthly_CENTRED_15Day_*`
- Open Data Portal store, the same versions:
  `esacci.SEASURFACESALINITY.15-days.L4.SSS.multi-sensor.multi-platform.{,GLOBAL-}MERGED_OI_Monthly_CENTRED_15Day_*.r1`

### Cloud

Cloud, monthly AVHRR v3.0, as the CMIP7 variables `clt`, `lwp`, `clivi`,
`clwvi`, the sum of `lwp` and `clivi`, the top of atmosphere fluxes `rlut`,
`rlutcs`, `rsut`, `rsutcs` and `rsdt`, and the surface fluxes `rlus`,
`rsus`, `rsuscs`, `rlds`, `rldscs`, `rsds` and `rsdscs`:

- zarr store, `clt` only:
  `ESACCI-L3C_CLOUD-CLD_PRODUCTS-AVHRR_NOAA-1982-2016-fv3.0.zarr`
- Kerchunk store, the morning and afternoon orbits:
  `ESACCI-L3C_CLOUD-CLD_PRODUCTS-AVHRR_{AM,PM}-*-fv3.0-kr1.1`
- Open Data Portal store, the same:
  `esacci.CLOUD.mon.L3C.CLD_PRODUCTS.multi-sensor.multi-platform.AVHRR-{AM,PM}.3-0.r1`

### Aerosol

Aerosol, daily and monthly SU v4.3, as the CMIP7 variables `od550aer`,
`od550lt1aer` and `abs550aer`:

- Open Data Portal store, ATSR-2 and AATSR:
  `esacci.AEROSOL.{day,mon}.L3C.AER_PRODUCTS.{ATSR-2.ERS-2,AATSR.Envisat}.SU.4-3.r1`

### Snow

Snow, daily, as the CMIP7 variables `snc`, from the snow cover fraction on
the ground, and `snw`, from the snow water equivalent:

- zarr store, `snw` v1.0 and v2.0: `ESACCI-L3C_SNOW-SWE-*-fv*.zarr`
- Kerchunk store, `snc` and `snw` v2.0:
  `ESACCI-L3C_SNOW-SCFG-AVHRR_MERGED-19820101-20181230-fv2.0_kr1.0` and
  `ESACCI-L3C_SNOW-SWE-MERGED-19790102-20200524-fv2.0_kr1.2`
- Open Data Portal store, `snc` v2.0 and `snw` v2.0, v3.1 and v4.0:
  `esacci.SNOW.day.L3C.SCFG.multi-sensor.multi-platform.AVHRR_MERGED.2-0.r1`
  and `esacci.SNOW.day.L3C.SWE.multi-sensor.multi-platform.MERGED.*.r1`

### Sea ice concentration

Sea ice concentration, daily, as the CMIP7 variable `siconc`, for the
northern and the southern hemisphere, on the polar EASE-Grid 2.0 (x/y) with
2-D latitudes and longitudes:

- zarr store, AMSR v2.1 at 50 km, northern hemisphere only:
  `ESACCI-SEAICE-L4-SICONC-AMSR_50.0kmEASE2-NH-2002-2017-fv2.1.zarr`
- Kerchunk store, AMSR v2.1 at 25 and 50 km and Nimbus-5 ESMR v1.0
  (southern hemisphere only) and v1.1:
  `ESACCI-SEAICE-L4-SICONC-AMSR_*-fv2.1_kr1.0` and
  `ESACCI-SEAICE-L3C-SICONC-NIMBUS5_ESMR-EASE2_*`
- Open Data Portal store, the same products, and SSM/I and SSMIS v3.0 at
  12.5 km:
  `esacci.SEAICE.day.L4.SICONC.multi-sensor.multi-platform.AMSR_{25,50}kmEASE2.2-1.{NH,SH}`,
  `esacci.SEAICE.day.L3C.SICONC.ESMR-(Nimbus-5).Nimbus-5.*` and
  `esacci.SEAICE.day.L4.SICONC.multi-sensor.multi-platform.RE_SSMI_12-5kmEASE2-{NH,SH}.3-0.{NH,SH}`

### Sea ice thickness

Sea ice thickness, monthly, as the CMIP7 variable `sithick`, for the
northern hemisphere at 25 km, with data from October to April only, and the
southern hemisphere at 50 km, on the polar EASE-Grid 2.0 (x/y) with 2-D
latitudes and longitudes:

- zarr store, Envisat and CryoSat-2 v2.0, northern hemisphere only:
  `ESACCI-SEAICE-L3C-SITHICK-*-fv2.0.zarr`
- Kerchunk store, Envisat v2.0 (southern hemisphere only) and v3.0, and
  CryoSat-2 v3.0: `ESACCI-SEAICE-L3C-SITHICK-*`
- Open Data Portal store, Envisat and CryoSat-2 v2.0, v3.0 and v4.0, and
  ERS-2 (northern hemisphere only) and Sentinel-3 v4.0:
  `esacci.SEAICE.mon.L3C.SITHICK.*`

### Ozone

Ozone, as the CMIP7 variables `toz`, the total column, and `o3`, the mole
fraction:

- Open Data Portal store, `toz` from the daily merged total column
  product and the monthly merged nadir profile product:
  `esacci.OZONE.day.L3S.TC.multi-sensor.multi-platform.MERGED.fv0100.r1`
  and `esacci.OZONE.mon.L3.NP.multi-sensor.multi-platform.MERGED.fv0002.r1`
- Open Data Portal store, `o3` as monthly zonal means in 10° latitude
  bands on the 39 CMIP7 pressure levels of `plev39` (`o3_tavg-p39-hy-air`),
  from the limb profile products of GOMOS, MIPAS, OSIRIS, SCIAMACHY and
  SMR: `esacci.OZONE.mon.L3.LP.*.v0001.r1`. They cover the levels from
  the upper troposphere up, so the lower levels are missing values.

### Ocean colour

Ocean colour, daily and monthly merged v6.0 on the 4 km geographic grid, as
the CMIP7 variable `chl` at the sea surface (`chl_tavg-ols-hxy-sea`), from
the chlorophyll-a concentration `chlor_a`:

- zarr store, the products with all ocean colour variables:
  `ESACCI-OC-L3S-OC_PRODUCTS-MERGED-{1D_DAILY,1M_MONTHLY}_4km_GEO_PML_OCx_QAA-1997-2022-fv6.0.zarr`
- Kerchunk store, monthly:
  `ESACCI-OC-L3S-CHLOR_A-MERGED-1M_MONTHLY_4km_GEO_PML_OCx-199709-202212-fv6.0-kr1.1`
- Open Data Portal store, the chlorophyll-a and all-variable products:
  `esacci.OC.{day,mon}.L3S.{CHLOR_A,OC_PRODUCTS}.multi-sensor.multi-platform.MERGED.6-0.geographic`

## Uncertainties

The recipes keep the uncertainty information as ancillary variables, which
iris loads as ancillary variables of the cube:

- Water vapour: `tcwv_err`, the mean of the retrieval uncertainties, as the
  standard error of `prw`; `tcwv_ran`, their root mean square; `stdv`, the
  standard deviation of the retrievals; and in v3.2 `num_obs`, the number
  of retrievals
  ([Product User Guide, table 3-1, page 19](https://climate.esa.int/media/documents/Water_Vapour_cci_D4.3_PUG_v2.2.pdf#page=19)).
- Sea surface temperature: the standard error of `tos`, `analysis_error`
  in OSTIA 1-1 and `analysed_sst_uncertainty` in OSTIA 2-1, and for GMPE
  the spread of the ensemble of analyses, `standard_deviation`, which the
  ten HadISST2 realisations dominate, and its size, `analysis_number`
  ([Product User Guide and Specification, section 1.1, page 8](https://dast.copernicus-climate.eu/documents/satellite-sea-surface-temperature/C3S_D312a_Lot3.3.2.23_201906_PUGS_SST_GMPE_v1.1.pdf#page=8);
  [dataset](https://dx.doi.org/10.5285/a963d9415bb74247830f8704f825aa90)).
- Sea surface salinity: `sss_random_error`, the standard error of `sos`,
  and `total_nobs`, the number of observations. The
  [Product User Guide, section 2.4.2, page 25](https://Admin.Climate.Esa.Int/documents/2489/SSS_cci_PHASE02_D4.3-PUG-v4.1_final_signed.pdf#page=25)
  only says that the error is propagated in the optimal interpolation.
- Cloud fraction: `cfc_unc`, the mean of the pixel uncertainties, the
  probabilities that the cloud mask is wrong, which the
  [Product User Guide, section 2, page 12](https://climate.esa.int/media/documents/Cloud_Product-User-Guide-PUG_v5.1.pdf#page=12)
  calls a qualitative measure of the uncertainty of `clt`; `cfc_prop_unc`,
  the uncertainty propagated from the pixels
  ([Annex B, page 62](https://climate.esa.int/media/documents/Cloud_Product-User-Guide-PUG_v5.1.pdf#page=62)),
  except in the zarr store; `cfc_std`, the standard deviation over the
  month; and `nobs`, the number of observations. The
  other cloud variables have no uncertainty variables.
- Aerosol optical depth: `AOD550_uncertainty`, the propagated uncertainty
  including sampling, as the standard error of `od550aer`
  ([SU v4.3 version notes](https://esgf.ceda.ac.uk/thredds/fileServer/esg_esacci/aerosol/docs/SU_version_info_V4.3.txt));
  `AOD550_uncertainty_mean`, the mean of the pixel uncertainties; the
  standard deviations `AOD550_sdev`, `FM_AOD550_sdev` and `AAOD550_sdev`
  of `od550aer`, `od550lt1aer` and `abs550aer`; and `pixel_count`, the
  number of observations.
- Snow: `scfg_unc` and `swe_std`, the standard errors of `snc` and `snw`
  (Product User Guide, issue 3.1,
  [table 3.4, printed page 13](https://climate.esa.int/media/documents/Snow_cci_D4.3_PUG_v3.1.pdf#page=19) and
  [section 4.3, printed page 23](https://climate.esa.int/media/documents/Snow_cci_D4.3_PUG_v3.1.pdf#page=29)).
- Sea ice concentration: `total_standard_uncertainty`, the standard error
  of `siconc`
  ([Product User Guide, section 5.1, page 18](https://admin.climate.esa.int/media/documents/SeaIce_CCI_P1_PUG-HRSIC_D4.2_Issue_3.0.pdf#page=18)),
  or `total_standard_error` in the AMSR
  ([Product User Guide, section 5.1.3, page 19](https://admin.climate.esa.int/media/documents/Sea_Ice_Concentration_Product_User_Guide_1.1.pdf#page=19))
  and Nimbus-5 ESMR
  ([Product User Guide, section 4, page 15](https://climate.esa.int/media/documents/SeaIce_CCI_P1_PUG-ESMR_D4.2_Issue_1.1.pdf#page=15))
  datasets. The `status_flag` is not kept.
- Sea ice thickness: `sea_ice_thickness_uncertainty`, the standard error of
  `sithick`, from error propagation
  ([Product User Guide, section 2.2.1.2, page 12](https://zenodo.org/records/10605998/files/SeaIce_CCI+_P1_PUG-SIT_D4.2_Issue_3.2.pdf#page=12)).
  The flags and the region code are not kept.
- Total ozone column: the standard error, standard deviation and number of
  observations of `toz` from the total column product, and `O3e_du_tot`,
  the standard error of `toz` from the nadir profile product.
- Ozone zonal means: `standard_error_of_the_mean`, the standard error of
  `o3`; `mean_uncertainty_estimate`, the mean of the uncertainties of the
  profiles; and `sample_standard_deviation`, the standard deviation of the
  profiles. The datasets give them in percent of `o3`, and the recipe
  converts them to the units of `o3`.
- Ocean colour: `chlor_a_log10_rmsd` and `chlor_a_log10_bias`, the
  root-mean-square difference and bias of log10 of the chlorophyll-a
  concentration, which are dimensionless, and the number of observations,
  `total_nobs` in the daily and `total_nobs_sum` in the monthly products
  (Product User Guide,
  [section 3.3, page 17](https://climate.esa.int/documents/3123/D4.2_-_OC-CCI_Product_User_Guide_PUG_v6.5.pdf#page=17) and
  [section 3.6, page 21](https://climate.esa.int/documents/3123/D4.2_-_OC-CCI_Product_User_Guide_PUG_v6.5.pdf#page=21)).

## Known data problems

The recipes make the data follow the standards. They do not check its
quality, and they do not correct the values. While building them, we found the
problems below, so check them before using these datasets. They were found on
2026-11-04 with xcube-cci 0.14.2. The list only covers what we looked at, so
the absence of a dataset does not mean that its data is correct.

### Time steps in the Open Data Portal store

In the Open Data Portal store (`esacci.*`), a time step can contain the data of
another time step. The files pass the CF and CMIP7 checks anyway, because
the metadata is correct. Use the same dataset from the zarr or Kerchunk store
where there is one.

The likely cause is how xcube-cci finds the file of a time step: it takes the
first file
[that ends at or after the start of the time step](https://github.com/esa-cci/xcube-cci/blob/v0.14.2/xcube_cci/cciodp.py#L999-L1005),
so a file that ends exactly when the time step starts is chosen over the file of
that time step, and a file that starts exactly when the time step ends is used
for a time step without a file. The time steps are made from the time range of
the dataset, so they exist whether or not there is a file. We ran this
selection on the file times in the catalogue of the store, and the results
agree with all the differences in the data that we compared. We reported this in
[xcube-cci#74](https://github.com/esa-cci/xcube-cci/issues/74), and the problems that seem to be in the catalogue of the store in
[xcube-cci#75](https://github.com/esa-cci/xcube-cci/issues/75).

| Datasets (`esacci.`) | Problem | Evidence |
| --- | --- | --- |
| `SEAICE.day.L4.SICONC.multi-sensor.multi-platform.AMSR_*` | The data is a day late: each time step has the file of the day before, and the first time steps are copies of the first file. | Compared with the Kerchunk store, whose time steps match the dates in the file names, and the catalogue. |
| `SST.day.L4.SSTskin.Unspecified.Unspecified.GMPE.2-0.r1` | The data is a day late, and the first two time steps are the same. | Compared with the zarr store, on samples from 1981 and 1992, and the catalogue. |
| `SEAICE.day.L4.SICONC.multi-sensor.multi-platform.RE_SSMI_*`, `SST.day.L4.SSTdepth.multi-sensor.multi-platform.OSTIA.2-1.sst` | Probably a day late, like the datasets above. | The catalogue, for the first 200 time steps, and repeated fields in the data. There is no other store to compare with. |
| `SEAICE.day.L3C.SICONC.ESMR-(Nimbus-5).*` | All time steps have the same field, that of the first file, because all files have the same time range in the catalogue ([xcube-cci#75](https://github.com/esa-cci/xcube-cci/issues/75)). | Compared with the Kerchunk store for the southern hemisphere, and the catalogue for both. |
| `SEASURFACESALINITY.15-days.L4.SSS.*` | About half of the time steps have the data of the time step before, because the 30-day means overlap. This includes time steps that the recipe keeps. | Compared with the Kerchunk store for v5.5, and the catalogue for all versions. |
| `AEROSOL.{mon,day}.L3C.AER_PRODUCTS.*` | Many time steps have the same field as the one before. The catalogue predicts another file for 76 of 120 (AATSR) and 75 of 97 (ATSR-2) monthly, and 2315 of 3612 (AATSR) and 2387 of 2944 (ATSR-2) daily time steps. Many ATSR-2 files have an end time in the catalogue that is years after their start ([xcube-cci#75](https://github.com/esa-cci/xcube-cci/issues/75)). | Repeated fields in the data, and the catalogue. There is no other store to compare with, so it is unclear which time steps are right. |
| `SEAICE.mon.L3C.SITHICK.*.NH25KMEASE2.*` | September has no data in the northern hemisphere, but its time step is a copy of October. | Compared with the zarr store for Envisat v2.0, and the catalogue for all datasets. |
| `SNOW.day.L3C.SWE.*` | A day without data is a copy of the next day. In the first years, that is every other day. | Compared with the Kerchunk store for v2.0, and the catalogue for all versions. |
| `CLOUD.mon.*.AVHRR-PM.3-0.r1`, `OC.day.*`, `SNOW.day.L3C.SCFG.*`, `WATERVAPOUR.day.*.4-2.r1` | The same as above, but only for a few time steps, e.g. 1 of 420 for the cloud dataset and 13 of 9250 for chlorophyll. | The catalogue. The daily datasets other than chlorophyll were only checked for the first 200 time steps. |
| `OZONE.day.L3S.TC.multi-sensor.multi-platform.MERGED.fv0100.r1` | All days of a month that we sampled have the same field. The files have `1M` in their names and cover a month in the catalogue, so these may be monthly data on a daily time axis ([xcube-cci#75](https://github.com/esa-cci/xcube-cci/issues/75)). | Repeated fields in the data. There is no other store to compare with, so the cause is unclear. |
| `OZONE.mon.L3.NP.multi-sensor.multi-platform.MERGED.fv0002.r1` | Only 36 of the 144 monthly time steps have a file in the catalogue. The others have no data. | The catalogue, and samples of the data. There is no other store to compare with. |

We found no problem with the time steps of `CLOUD.mon.*.AVHRR-AM.3-0.r1`,
`OC.mon.*`, `WATERVAPOUR.mon.*` and the southern hemisphere of
`SEAICE.mon.L3C.SITHICK.*`. Those of the v3.2 of `WATERVAPOUR.day.*` and of
`SST.day.L4.SSTdepth.multi-sensor.multi-platform.OSTIA.1-1.r1` look correct in
the catalogue for the first 200 time steps. The files of
`OZONE.mon.L3.LP.*` hold several time steps, so the selection above does not
tell whether they are right, and we did not compare them with another source.

### Values

- Sea ice thickness can be negative, e.g. -0.46 m. The
  [Product User Guide, table on page 14](https://zenodo.org/records/10605998/files/SeaIce_CCI+_P1_PUG-SIT_D4.2_Issue_3.2.pdf#page=14)
  uses the fraction of negative thickness as a quality criterion, so these are
  part of the retrieval. The recipe keeps them.
- `sea_ice_thickness_uncertainty` reaches 104 m in November 2010 in
  `SEAICE.mon.L3C.SITHICK.SIRAL.CryoSat-2.NH25KMEASE2.2-0.r1`, where the
  thickness is below 8 m. It has no standard name in v2.0 and the recipe gives
  it the one of the later versions, while the
  [Product User Guide (issue 1.0), section 2.2.1.2, page 13](https://climate.esa.int/media/documents/SeaIce_CCI_P1_PUG_SIT_D4.2_Issue_1.0.pdf#page=13)
  calls the gridded uncertainties a maximum estimate.
- `total_standard_error` of the Nimbus-5 datasets goes slightly above 100 %.
  Part of it, the resampling uncertainty, is the difference between the maximum
  and the minimum in a window of 3 x 3 pixels, not a standard deviation
  ([Product User Guide, section 4, page 15](https://climate.esa.int/media/documents/SeaIce_CCI_P1_PUG-ESMR_D4.2_Issue_1.1.pdf#page=15)).

## Recipes and fixes

A fix corrects one kind of problem, e.g. it converts variables to other
units or removes attributes that are not allowed by the CF conventions. Most
fixes have options that configure what they do, such as the variables and
the units to convert them to. Each fix can check a dataset and report the
problems it finds, or apply the correction.

A recipe contains the fixes for one dataset: a list of steps, each of
which is a fix with its options, that runs in order. Woodpecker selects the
recipe for a dataset by matching the path patterns of the recipe against
the name of the input, e.g. `*ESACCI-L4_GHRSST-SST-GMPE-GLOB_*`. This plugin
provides one recipe for each group of datasets that need the same fixes,
e.g. the monthly water vapour datasets of version 3.2 in all stores.

To list the recipes, run:

```bash
pixi run woodpecker list-recipes
```

This also lists the recipes that come with woodpecker itself. Add
`--format json` to show the full recipes, including their path patterns and
the options of each step.

To list the fixes this plugin provides, with a description of each, run:

```bash
pixi run woodpecker list-fixes --dataset ESA-CCI
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to set up a development
environment and run the tests.

## License

Apache-2.0, see [LICENSE](LICENSE).
