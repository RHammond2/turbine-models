"""
This CLI tool helps to (re)build the base turbine power curve documentation for a given set of
wind turbines that have already been correctly added to the turbine library.

Note: Be careful with the `--overwrite` flag because it will overwrite all power curve figures
and markdown files associated with whichever turbines are run. After the intial build, this is
most helpful for adding new turbine(s) to the documentation site.

Note: The output refs.txt is provided to be able to copy and paste all newly generated turbine
markdown files into the appropriate section of _toc.yml. Failure to add these file references
means the turbine(s) will not be added to the documentation. Please also add the file reference
to the appropriate section of the documentation's `index.md` file.
"""

import argparse
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from turbine_models.parser import Turbines
from turbine_models.tools.extract_power_curve import extract_power_curve
from turbine_models.tools.power_curve_tools import pad_power_curve


DOCS_DIR = Path(__file__).parent
DATA_DIR = DOCS_DIR.parent / "turbine_models"
POWER_CURVES = DATA_DIR / "data"
SPECS = DATA_DIR / "specs"
IMAGES = DOCS_DIR / "images"

BETZ_LIMIT = 16.0 / 27.0

HEADER = """
---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.19.1
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---
"""

unit_map = {
    "name": "N/A",
    "nickname": "N/A",
    "rated_power": "kW",
    "rated_wind_speed": "m/s",
    "cut_in_wind_speed": "m/s",
    "cut_out_wind_speed": "m/s",
    "rotor_diameter": "m",
    "hub_height": "m",
    "drivetrain": "N/A",
    "control": "N/A",
    "iec_class": "N/A",
    "group": "N/A",
    "power_curve_file": "N/A",
    "manufacturer": "N/A",
    "origin": "N/A",
    "power_curve_type": "N/A",
    "rated_tsr": "Unitless",
    "reference_links": "N/A",
}
name_map = {
    "name": "Name",
    "nickname": "Nickname",
    "rated_power": "Rated Power",
    "rated_wind_speed": "Rated Wind Speed",
    "cut_in_wind_speed": "Cut-in Wind Speed",
    "cut_out_wind_speed": "Cut-out Wind Speed",
    "rotor_diameter": "Rotor Diameter",
    "hub_height": "Hub Height",
    "drivetrain": "Drivetrain",
    "control": "Control",
    "iec_class": "IEC Class",
    "group": "Group",
    "power_curve_file": "Power Curve File",
    "manufacturer": "Manufacturer",
    "origin": "Origin",
    "power_curve_type": "Power Curve Type",
    "rated_tsr": "Tip Speed Ratio",
    "reference_links": "Reference Links",
}
unit_map_df = pd.DataFrame([list(unit_map.values())], columns=unit_map.keys()).T

def build_page(turbine_type: str, turbine_name: str, specs: dict, *, has_cp: bool=True) -> str:

    title = f"# {turbine_name}"
    data_ref_title = "## Link to CSV File"
    data_ref = (
        "The .csv file can be found online in the GitHub at "
        f"[turbine_models/data/{turbine_type}/{turbine_name}.csv]"
        f"(https://github.com/NatLabRockies/turbine-models/tree/main/turbine_models/{turbine_type}/{turbine_name}.csv)"
    )

    specs_title = "## Key Parameters"
    specs = (
        pd.DataFrame([list(specs.values())], columns=specs.keys())
        .T
        .rename(columns={0: "Value"})
        .join(pd.DataFrame([list(unit_map.values())], columns=unit_map.keys()).T, how="left")
        .rename(columns={0: "Units"}, index=name_map)
    )
    specs.index = specs.index.set_names("Item")
    specs = specs.to_markdown()

    pc_title = "## Power Curve"
    pc = f"![power curve](../images/{turbine_type}/{turbine_name}_power_curve_kw.png)"
    cp_title = "## Cp Curve"
    cp = f"![Cp curve](../images/{turbine_type}/{turbine_name}_cp_curve.png)"

    ref_title = "## References"
    ref = """
    ```{bibliography}
    :filter: docname in docnames
    ```
    """

    if has_cp:
        md_text = "\n\n".join((
            title, data_ref_title, data_ref, specs_title, specs, pc_title, pc, cp_title, cp, ref_title, ref
        ))
    else:
        md_text = "\n\n".join((
            title, data_ref_title, data_ref, specs_title, specs, pc_title, pc, ref_title, ref
        ))
        
    with (DOCS_DIR / turbine_type / f"{turbine_name}.md").open("w") as f:
        f.write(md_text)
        f.write("\n")

def plot_turbine_specs(turbine_type: str, turbine_name: str, power_curve: dict, key: str) -> None:
    
    # Round cut-out wind speed up to the nearest value evenly divisible by 5
    # ws = power_curve["wind_speed"]
    # pc = power_curve["power_curve_kw"]
    # ws10 = ws > 10
    # ix_cut_out = (pc[ws10] == 0).tolist().index(True) + (~ws10).sum()
    # ws_max = 5 * np.ceil(x / 5)

    ws_max = 40
    ws, curve = pad_power_curve(power_curve["wind_speed"], power_curve[key], 0, ws_max)
    
    if (is_pc := key == "power_curve_kw"):
        ylabel = "Power [kW]"
        label = None
        ymax = np.ceil(curve.max() * 1.2)
    else:
        ylabel = "Cp [-]"
        label = "Cp"
        ymax = 0.61
    
    fig = plt.figure(figsize=(6, 4), layout="tight")
    ax = fig.add_subplot(111)
    
    ax.plot(ws, curve, label=label, c="tab:blue")
    
    ax.set_xlabel("Wind Speed [m/s]")
    ax.set_ylabel(ylabel)
    ax.set_xlim(0, ws_max)
    ax.set_ylim(0, ymax)
    if not is_pc:
        ax.axhline(BETZ_LIMIT, 0, ws_max, color="tab:orange", ls="--", label="Betz Limit")
        ax.legend()
    
    ax.grid()
    ax.set_axisbelow(True)

    fig.savefig(IMAGES / turbine_type / f"{turbine_name}_{key}.png")
    plt.close()


def parse_args(parser: argparse.ArgumentParser) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ERA5 download and combination script")
    parser.add_argument(
        "-t",
        "--type",
        dest="turbine_type",
        type=str,
        nargs="*",
        choices=["Distributed", "Onshore", "Offshore"],
        help="Type of turbine (corresponds to the data folder name in 'turbine_models/data').",
    )
    parser.add_argument(
        "-n",
        "--name",
        dest="name",
        type=str,
        default="all",
        nargs="*",
        help="Name(s) of the turbines (should match the turbine specs file name).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrites existing documentation files."
    )
    return parser.parse_args()

if __name__ == "__main__":

    types = ("Distributed", "Onshore", "Offshore")
    
    parser = argparse.ArgumentParser(description="Turbine documentation template builder")
    args = parse_args(parser)

    types = args.turbine_type if args.turbine_type else types
    if isinstance(types, str):
        types = [types]
    turbine_names = args.name if args.name else "all"
    if isinstance(turbine_names, str):
        turbine_names = [turbine_names]
    overwrite = args.overwrite

    if turbine_names != ["all"]:
        if len(types) > 1:
            raise ValueError("Please provide only a specific 'name' and 'turbine-type' combination.")

    turbines = Turbines()
    file_refs = []

    for turbine_type in types:
        group_name = turbine_type.lower()
        group = turbines.turbines(group=group_name)
        ix_map = {v: k for k, v in group.items()}
        turbine_order = sorted([*ix_map])
        if turbine_names != ["all"]:
            turbine_order = [el for el in turbine_order if el in turbine_names]
        for name in turbine_order:
            if not overwrite:
                if (DOCS_DIR / turbine_type / f"{name}.md").exists():
                    continue
            try:
                specs = turbines.specs(ix_map[name], group=group_name)
            except KeyError:
                print(f"{turbine_type} turbine: {name} failed to extract data, skipping for now.")
            base_specs = deepcopy(specs)
            base_specs.pop("power_curve")
            if not base_specs["reference_links"]:
                base_specs.pop("reference_links")
            pc_cols = specs["power_curve"].columns
            norm_power = {"Power [-]", "power"}.intersection(pc_cols)
            has_cp = {"Cp [-]", "cp"}.intersection(pc_cols)
            if not norm_power:
                pc_dict = extract_power_curve(specs)
                plot_turbine_specs(turbine_type, name, pc_dict, "power_curve_kw")
            else:
                pc_dict = {
                    col: np.array(list(s.values()))
                    for col, s in specs["power_curve"].rename(columns={"wind_speed_ms": "wind_speed", "cp": "cp_curve"}).to_dict().items()
                }
                plot_turbine_specs(turbine_type, name, pc_dict, "power")
            if has_cp:
                plot_turbine_specs(turbine_type, name, pc_dict, "cp_curve")
                
            build_page(turbine_type, name, base_specs, has_cp=has_cp)
            file_refs.append(f"  - file: {turbine_type}/{name}")

    with (DOCS_DIR / "refs.txt").open("w") as f:
        f.write("\n".join(file_refs))
