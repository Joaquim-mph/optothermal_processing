import sys
import inspect
from pathlib import Path


project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.cli.commands import derived_metrics as dm


def test_derive_all_metrics_default_procedures():
    sig = inspect.signature(dm.derive_all_metrics_command)
    option = sig.parameters["procedures"].default
    assert option.default == "IVg,VVg,It,ITt,Vt"


def test_derive_fitting_metrics_default_procedures():
    sig = inspect.signature(dm.derive_fitting_metrics_command)
    option = sig.parameters["procedures"].default
    assert option.default == "It,ITS,ITt,Vt,Tt"


def test_derive_consecutive_sweeps_default_procedures():
    sig = inspect.signature(dm.derive_consecutive_sweeps_command)
    option = sig.parameters["procedures"].default
    assert option.default == "IVg,VVg"
