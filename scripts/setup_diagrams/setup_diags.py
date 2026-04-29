"""Generate electrical and optical setup schematic diagrams.

Outputs PNGs next to this script unless --out-dir is given.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import schemdraw
import schemdraw.elements as elm


def draw_electrical(out_path: Path, show: bool) -> None:
    with schemdraw.Drawing(show=show) as d:
        fet = d.add(elm.NFet(bulk=False).reverse())

        d.add(elm.Line().left().at(fet.gate).length(2))
        gate_node = d.here

        d.add(elm.BatteryCell().down().label("$V_{g}$"))
        d.add(elm.Ground())

        d.add(elm.Line().left().at(gate_node).length(2))
        d.add(elm.MeterV().down().label(""))
        d.add(elm.Ground())

        d.add(elm.MeterA().right().at(fet.drain).label(""))
        d.add(elm.Line().right().length(1))
        d.add(elm.BatteryCell().down().reverse().label("$V_{ds}$"))
        d.add(elm.Ground())

        d.add(elm.Line().down().at(fet.source).length(0.5))
        d.add(elm.Ground())

        d.save(str(out_path), dpi=300)


def draw_optical(out_path: Path, show: bool) -> None:
    with schemdraw.Drawing(show=show) as d:
        d.add(elm.BatteryCell().right())
        d.add(elm.Line().down().length(2))
        d.add(elm.Diode().left())
        d.add(elm.Line().up().length(2))
        d.save(str(out_path), dpi=300)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).parent,
        help="Directory to write PNGs into (default: script directory)",
    )
    parser.add_argument(
        "--show", action="store_true", help="Display windows interactively"
    )
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    draw_electrical(args.out_dir / "electrical_setup.png", args.show)
    draw_optical(args.out_dir / "optical_setup.png", args.show)


if __name__ == "__main__":
    main()
