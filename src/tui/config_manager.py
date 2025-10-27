"""
Configuration Manager for TUI Persistence.

Handles saving, loading, and managing plot configurations for reuse.
Stores configurations as JSON in user's home directory.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


class ConfigManager:
    """
    Manage persistent configurations for plot generation.

    Features:
    - Save plot configurations with metadata
    - Load recent configurations
    - Export/import configurations
    - Automatic timestamping and description

    Storage location: ~/.lab_plotter_configs.json
    """

    def __init__(self, config_file: Optional[Path] = None, max_recent: int = 20):
        """
        Initialize ConfigManager.

        Parameters
        ----------
        config_file : Path, optional
            Path to configuration file. Defaults to ~/.lab_plotter_configs.json
        max_recent : int
            Maximum number of recent configurations to keep (default: 20)
        """
        if config_file is None:
            self.config_file = Path.home() / ".lab_plotter_configs.json"
        else:
            self.config_file = Path(config_file)

        self.max_recent = max_recent
        self._ensure_config_file()

    def _ensure_config_file(self) -> None:
        """Create config file if it doesn't exist."""
        if not self.config_file.exists():
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            self._save_data({"configs": [], "version": "1.0.0"})

    def _load_data(self) -> Dict[str, Any]:
        """Load configuration data from JSON file."""
        try:
            with open(self.config_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            # Reset to empty if corrupted
            return {"configs": [], "version": "1.0.0"}

    def _save_data(self, data: Dict[str, Any]) -> None:
        """Save configuration data to JSON file."""
        with open(self.config_file, "w") as f:
            json.dump(data, f, indent=2)

    def save_config(
        self,
        config: Dict[str, Any],
        description: Optional[str] = None,
        auto_description: bool = True
    ) -> str:
        """
        Save a plot configuration.

        Parameters
        ----------
        config : dict
            Configuration dictionary with plot parameters
        description : str, optional
            User-provided description
        auto_description : bool
            If True, generate description from config automatically

        Returns
        -------
        str
            Configuration ID (timestamp-based)

        Examples
        --------
        >>> cm = ConfigManager()
        >>> config = {
        ...     "chip_number": 67,
        ...     "chip_group": "Alisson",
        ...     "plot_type": "ITS",
        ...     "legend_by": "vg",
        ...     "baseline": 60.0
        ... }
        >>> config_id = cm.save_config(config, "Dark ITS at VG=3V")
        """
        # Load existing data
        data = self._load_data()

        # Generate config ID (timestamp with microseconds for uniqueness)
        config_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        # Generate automatic description if requested
        if auto_description and description is None:
            description = self._generate_description(config)

        # Create config entry
        entry = {
            "id": config_id,
            "timestamp": datetime.now().isoformat(),
            "description": description or "No description",
            "config": config
        }

        # Add to beginning of list (most recent first)
        data["configs"].insert(0, entry)

        # Trim to max_recent
        if len(data["configs"]) > self.max_recent:
            data["configs"] = data["configs"][:self.max_recent]

        # Save
        self._save_data(data)

        return config_id

    def _generate_description(self, config: Dict[str, Any]) -> str:
        """
        Generate automatic description from config.

        Format: "ChipXX - PlotType [key params]"
        Example: "Alisson67 - ITS (Vg=3V, λ=455nm)"
        """
        parts = []

        # Chip info
        chip_group = config.get("chip_group", "")
        chip_number = config.get("chip_number", "")
        if chip_group and chip_number:
            parts.append(f"{chip_group}{chip_number}")

        # Plot type
        plot_type = config.get("plot_type", "")
        if plot_type:
            parts.append(plot_type)

        # Key parameters
        params = []

        # Preset (for ITS)
        preset = config.get("preset")
        if preset and preset != "custom":
            params.append(f"preset={preset}")

        # VG filter
        vg = config.get("vg_filter")
        if vg is not None:
            params.append(f"Vg={vg:g}V")

        # Wavelength filter
        wl = config.get("wavelength_filter")
        if wl is not None:
            params.append(f"λ={wl:g}nm")

        # VDS filter
        vds = config.get("vds_filter")
        if vds is not None:
            params.append(f"Vds={vds:g}V")

        # Method (for transconductance)
        method = config.get("method")
        if method:
            params.append(f"method={method}")

        # Legend by
        legend = config.get("legend_by")
        if legend and legend != "led_voltage":  # Only show if non-default
            params.append(f"legend={legend}")

        # Baseline mode (for ITS)
        baseline_mode = config.get("baseline_mode")
        if baseline_mode and baseline_mode != "fixed":
            params.append(f"baseline={baseline_mode}")

        # Combine parts
        desc = " - ".join(parts)
        if params:
            desc += f" ({', '.join(params)})"

        return desc or "Plot configuration"

    def load_config(self, config_id: str) -> Optional[Dict[str, Any]]:
        """
        Load a configuration by ID.

        Parameters
        ----------
        config_id : str
            Configuration ID (timestamp)

        Returns
        -------
        dict or None
            Configuration dictionary, or None if not found
        """
        data = self._load_data()

        for entry in data["configs"]:
            if entry["id"] == config_id:
                return entry["config"]

        return None

    def get_recent_configs(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get list of recent configurations.

        Parameters
        ----------
        limit : int, optional
            Maximum number of configs to return (default: all)

        Returns
        -------
        list
            List of config entries with id, timestamp, description, config
        """
        data = self._load_data()
        configs = data.get("configs", [])

        if limit is not None:
            configs = configs[:limit]

        return configs

    def delete_config(self, config_id: str) -> bool:
        """
        Delete a configuration by ID.

        Parameters
        ----------
        config_id : str
            Configuration ID to delete

        Returns
        -------
        bool
            True if deleted, False if not found
        """
        data = self._load_data()

        # Find and remove
        original_count = len(data["configs"])
        data["configs"] = [c for c in data["configs"] if c["id"] != config_id]

        if len(data["configs"]) < original_count:
            self._save_data(data)
            return True

        return False

    def clear_all(self) -> int:
        """
        Clear all saved configurations.

        Returns
        -------
        int
            Number of configurations deleted
        """
        data = self._load_data()
        count = len(data["configs"])
        data["configs"] = []
        self._save_data(data)
        return count

    def export_config(self, config_id: str, export_path: Path) -> bool:
        """
        Export a single configuration to a JSON file.

        Parameters
        ----------
        config_id : str
            Configuration ID to export
        export_path : Path
            Path to export file

        Returns
        -------
        bool
            True if exported successfully, False if config not found
        """
        data = self._load_data()

        for entry in data["configs"]:
            if entry["id"] == config_id:
                with open(export_path, "w") as f:
                    json.dump(entry, f, indent=2)
                return True

        return False

    def import_config(self, import_path: Path) -> Optional[str]:
        """
        Import a configuration from a JSON file.

        Parameters
        ----------
        import_path : Path
            Path to import file

        Returns
        -------
        str or None
            New configuration ID if imported successfully, None if failed
        """
        try:
            import time

            with open(import_path, "r") as f:
                entry = json.load(f)

            # Validate structure
            if not all(k in entry for k in ["id", "timestamp", "description", "config"]):
                return None

            # Generate new ID to avoid conflicts (add microseconds for uniqueness)
            config = entry["config"]
            description = entry["description"] + " (imported)"

            # Add a small delay to ensure unique timestamp
            time.sleep(0.1)

            return self.save_config(config, description, auto_description=False)

        except (json.JSONDecodeError, FileNotFoundError, KeyError):
            return None

    def search_configs(self, query: str) -> List[Dict[str, Any]]:
        """
        Search configurations by description or parameters.

        Parameters
        ----------
        query : str
            Search query (case-insensitive)

        Returns
        -------
        list
            List of matching config entries
        """
        data = self._load_data()
        query_lower = query.lower()

        matches = []
        for entry in data["configs"]:
            # Search in description
            if query_lower in entry["description"].lower():
                matches.append(entry)
                continue

            # Search in config values (chip number, plot type, etc.)
            config_str = json.dumps(entry["config"]).lower()
            if query_lower in config_str:
                matches.append(entry)

        return matches

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about saved configurations.

        Returns
        -------
        dict
            Statistics including total count, by plot type, etc.
        """
        data = self._load_data()
        configs = data.get("configs", [])

        stats = {
            "total_count": len(configs),
            "by_plot_type": {},
            "by_chip": {},
            "oldest": None,
            "newest": None,
        }

        if configs:
            # Count by plot type
            for entry in configs:
                plot_type = entry["config"].get("plot_type", "Unknown")
                stats["by_plot_type"][plot_type] = stats["by_plot_type"].get(plot_type, 0) + 1

                # Count by chip
                chip_group = entry["config"].get("chip_group", "")
                chip_number = entry["config"].get("chip_number", "")
                chip_name = f"{chip_group}{chip_number}" if chip_group and chip_number else "Unknown"
                stats["by_chip"][chip_name] = stats["by_chip"].get(chip_name, 0) + 1

            # Oldest/newest
            stats["oldest"] = configs[-1]["timestamp"]
            stats["newest"] = configs[0]["timestamp"]

        return stats
