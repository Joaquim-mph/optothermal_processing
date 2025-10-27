import polars as pl
from pathlib import Path
import re

NUMERIC_FULL = re.compile(
    r"""^
       [-+]?               # optional sign
       \d*\.?\d+           # digits with optional decimal
       (?:[eE][-+]?\d+)?   # optional scientific
       (?:\s*[A-Za-z%μμΩ°]+)?  # optional unit (μm, %, Ω, °C, etc)
       $""",
    re.VERBOSE,
)

# to pull the number out of "0.26 V" or "1e-06 A"
NUMERIC_PART = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def parse_iv_metadata(csv_path: Path) -> dict:
    """
    Read only the header of an IV .csv and pull out all the #Parameters keys.
    Returns a flat dict, e.g.
    {
      "Information": "SnS - no light - PAIN",
      "Irange": 1e-6,
      "NPLC": 1.0,
      "Burn-in time": 0.0,
      ...
    }
    """
    params = {}
    with csv_path.open(encoding="utf-8", errors="ignore") as f:
        in_params = False
        for line in f:
            if line.startswith("#Parameters:"):
                in_params = True
                continue
            if not in_params:
                continue
            if not line.startswith("#\t"):
                break

            key, raw_val = line[2:].split(":", 1)
            key = key.strip()
            raw_val = raw_val.strip()

            # 1) numeric-only?
            if NUMERIC_FULL.match(raw_val):
                num_str = NUMERIC_PART.search(raw_val).group()
                params[key] = float(num_str)

            # 2) boolean?
            elif raw_val.lower() in ("true", "false"):
                params[key] = (raw_val.lower() == "true")

            # 3) otherwise keep full text
            else:
                params[key] = raw_val

    # 4) derive Laser toggle if it wasn't in the header
    lv = params.get("Laser voltage")
    if lv is not None:
        params["Laser toggle"] = (lv != 0.0)

    params["source_file"] = str(csv_path)
    return params


# 1) find all IV csv files
folder_name = "raw_data/Alisson_23_sept"
raw = Path(folder_name)
all_csvs = list(raw.rglob("*.csv"))
# drop any file whose name starts with "._"
csv_paths = [p for p in all_csvs if not p.name.startswith("._")]

# 2) parse each one
records = []
for p in csv_paths:
    try:
        rec = parse_iv_metadata(p)
        records.append(rec)
    except Exception as e:
        print(f"warning: could not parse {p}: {e}")

# 3) build Polars DataFrame
df_meta = pl.DataFrame(records)
# save to the current directory as "metadata.csv"
df_meta.write_csv(f"{folder_name}_metadata.csv")
# 1) Just the names:
#print(df_meta)
print("|DONE!!!|")