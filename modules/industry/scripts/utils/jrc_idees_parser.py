from typing import Union

import numpy as np
import xarray as xr

STANDARD_COORDS = ["cat_name", "year", "country_code", "carrier_name"]


def ensure_standard_coordinates(ds: Union[xr.Dataset, xr.DataArray]):
    """Remove all coordinates that do not match a predefined standard."""
    removed_coords = set(ds.coords).difference(STANDARD_COORDS)
    removed_dims = removed_coords.intersection(ds.dims)
    if removed_dims:
        raise ValueError(f"Cannot ensure standard coordinates for {removed_dims}.")

    ds = ds.drop(removed_coords)
    return ds


def get_auxiliary_electric_final_intensity(
    section: str,
    material: str,
    jrc_energy: xr.Dataset,
    jrc_prod: xr.DataArray,
    fill_empty: bool = False,
) -> xr.DataArray:
    """Wrapper for auxiliary electrical processes."""
    auxiliaries = ["Lighting", "Air compressors", "Motor drives", "Fans and pumps"]
    auxiliary_intensity = sum(
        get_subsection_final_intensity(
            section, aux, material, "Electricity", jrc_energy, jrc_prod, fill_empty
        )
        for aux in auxiliaries
    )

    return auxiliary_intensity


def get_subsection_final_intensity(
    section: str,
    subsection: str,
    material: str,
    carrier_name: str,
    jrc_energy: xr.Dataset,
    jrc_prod: xr.DataArray,
    fill_empty: bool = False,
) -> xr.DataArray:
    """Get final energy intensity of a given JRC section/subsection/material."""
    # Extract relevant section and subsection data.
    final_demand = jrc_energy["final"].sel(section=section, subsection=subsection)
    useful_demand = jrc_energy["useful"].sel(section=section, subsection=subsection)
    production = jrc_prod.sel(produced_material=material)

    total_eff = useful_demand / final_demand
    carrier_eff = total_eff.where(total_eff > 0).sel(carrier_name=carrier_name)
    if fill_empty:
        # First by country avg. (all years), then by year avg. (all countries).
        carrier_eff = carrier_eff.fillna(carrier_eff.mean(dim="year"))
        carrier_eff = carrier_eff.fillna(carrier_eff.mean(dim="country_code"))

    # Get the useful energy intensity of all production (e.g., twh/kt_steel)
    useful_intensity = useful_demand.sum(dim="carrier_name") / production
    # Then reconstruct final intensity.
    final_intensity = useful_intensity / carrier_eff

    # Prettify
    final_intensity = ensure_standard_coordinates(final_intensity)
    final_intensity = final_intensity.assign_attrs(units="twh/kt")
    final_intensity.name = "final_intensity"

    assert final_intensity.sum() >= useful_intensity.sum(), "Creating energy!"

    return final_intensity.fillna(0)


def get_subsection_useful_intensity(
    section: str,
    subsection: str,
    material: str,
    jrc_energy: xr.Dataset,
    jrc_prod: xr.DataArray,
) -> xr.DataArray:
    """Get useful energy intensity of a given section/subsection/material."""
    useful_demand = jrc_energy["useful"].sel(section=section, subsection=subsection)
    production = jrc_prod.sel(produced_material=material)
    useful_intensity = (useful_demand / production).sum("carrier_name")

    # Prettify
    useful_intensity = ensure_standard_coordinates(useful_intensity)
    useful_intensity = useful_intensity.assign_attrs(units="twh/kt")
    useful_intensity.name = "useful_intensity"

    assert ~np.isinf(
        useful_intensity
    ).any(), f"Zero division ocurred for {section}.{subsection} and {material}!"

    return useful_intensity.fillna(0)


# TODO: fix me!
# def get_carrier_demand(
#     carrier: str, all_demand_df: pd.DataFrame, jrc_energy: xr.Dataset
# ) -> pd.DataFrame:
#     """
#     Get demand for a specific carrier, assuming all end use demand that could consume
#     that carrier are completely met by that carrier.
#     """
#     energy = jrc_energy.xs(carrier, level="carrier_name")
#     energy_efficiency = energy.xs("demand").div(energy.xs("consumption"))
#     # Fill NaNs (where there is demand, but no consumption in that country)
#     # with the average efficiency a. from the country, b. from all countries
#     energy_efficiency = energy_efficiency.fillna(energy_efficiency.mean())

#     return all_demand_df.reindex(energy_efficiency.index).div(energy_efficiency)
