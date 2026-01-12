
#!/usr/bin/env python3
"""Extract power consumption metrics from Redfish data dumps."""

import json
from pathlib import Path


def safe_get(data, *keys, default="NA"):
    """Safely navigate nested dictionary keys, returning default if not found."""
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
            if current is None:
                return default
        elif isinstance(current, list) and len(current) > 0:
            if isinstance(key, int):
                if key < len(current):
                    current = current[key]
                else:
                    return default
            else:
                return default
        else:
            return default
    return current if current is not None else default


def extract_chassis_id(member_ref):
    """Extract chassis ID from a member reference like '/redfish/v1/Chassis/1'."""
    if not member_ref:
        return None
    # Remove trailing slashes and get the last part
    parts = member_ref.rstrip("/").split("/")
    return parts[-1] if parts else None


def get_power_metrics(hostname_dir, datacenter):
    """Extract power metrics from a hostname directory."""
    hostname = hostname_dir.name
    result = {
        "datacenter": datacenter,
        "hostname": hostname,
        "redfish_version": "NA",
        "power_states": [],
        "PowerConsumedWatts": "NA",
        "MinConsumedWatts": "NA",
        "MaxConsumedWatts": "NA",
        "AverageConsumedWatts": "NA",
    }

    # Read Redfish version from index.json (/redfish/v1/ endpoint)
    index_json_path = hostname_dir / "index.json"
    if index_json_path.exists():
        try:
            with open(index_json_path, "r") as f:
                index_data = json.load(f)
                result["redfish_version"] = safe_get(
                    index_data, "RedfishVersion", default="NA"
                )
        except (json.JSONDecodeError, IOError):
            pass

    # Read Chassis.json
    chassis_json_path = hostname_dir / "Chassis.json"
    if not chassis_json_path.exists():
        return result

    try:
        with open(chassis_json_path, "r") as f:
            chassis_data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return result

    # Get chassis members
    members = chassis_data.get("Members", [])
    if not members:
        return result

    # Process all chassis members to get power states
    power_states = []
    power_metrics_found = False

    for member in members:
        chassis_id = extract_chassis_id(member.get("@odata.id"))
        if not chassis_id:
            continue

        # Read chassis details
        chassis_detail_path = hostname_dir / "Chassis" / f"{chassis_id}.json"
        if not chassis_detail_path.exists():
            continue

        try:
            with open(chassis_detail_path, "r") as f:
                chassis_detail = json.load(f)
        except (json.JSONDecodeError, IOError):
            continue

        # Get PowerState
        power_state = safe_get(chassis_detail, "PowerState", default="NA")
        if power_state != "NA":
            power_states.append(power_state.lower())

        # Only get power metrics from the first chassis with Power data
        if not power_metrics_found:
            # Check if Power reference exists
            power_ref = chassis_detail.get("Power")
            if power_ref and isinstance(power_ref, dict):
                # Read Power.json
                power_json_path = (
                    hostname_dir / "Chassis" / chassis_id / "Power.json"
                )
                if power_json_path.exists():
                    try:
                        with open(power_json_path, "r") as f:
                            power_data = json.load(f)
                        # Extract power metrics from PowerControl array
                        power_control = power_data.get("PowerControl", [])
                        if power_control and len(power_control) > 0:
                            pc = power_control[0]
                            result["PowerConsumedWatts"] = safe_get(
                                pc, "PowerConsumedWatts"
                            )
                            result["MinConsumedWatts"] = safe_get(
                                pc, "PowerMetrics", "MinConsumedWatts"
                            )
                            result["MaxConsumedWatts"] = safe_get(
                                pc, "PowerMetrics", "MaxConsumedWatts"
                            )
                            result["AverageConsumedWatts"] = safe_get(
                                pc, "PowerMetrics", "AverageConsumedWatts"
                            )
                            power_metrics_found = True
                    except (json.JSONDecodeError, IOError):
                        pass

    # Sort power states alphabetically
    result["power_states"] = sorted(power_states)

    return result


def main():
    """Main function to process all data centers and machines."""
    # Base directory containing all data center dumps
    base_dir = Path(__file__).parents[1] / "data" / "redfish-dump-2025-12-17"

    all_results = []

    # Iterate through all subdirectories as data centers
    for datacenter_dir in base_dir.iterdir():
        if not datacenter_dir.is_dir():
            continue

        # Iterate through all hostname directories
        for hostname_dir in sorted(datacenter_dir.iterdir()):
            if not hostname_dir.is_dir():
                continue

            metrics = get_power_metrics(hostname_dir, datacenter_dir.name)
            all_results.append(metrics)

    # Print results
    for result in all_results:
        # Format power states
        power_states_str = (
            ", ".join(result["power_states"])
            if result["power_states"]
            else "NA"
        )

        print(
            f"[{result['redfish_version']}] [{power_states_str}] "
            f"{result['datacenter']}/{result['hostname']}: "
            f"PowerConsumedWatts={result['PowerConsumedWatts']}, "
            f"MinConsumedWatts={result['MinConsumedWatts']}, "
            f"MaxConsumedWatts={result['MaxConsumedWatts']}, "
            f"AverageConsumedWatts={result['AverageConsumedWatts']}"
        )


if __name__ == "__main__":
    main()
