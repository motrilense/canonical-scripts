#!/usr/bin/env python3
"""Extract power consumption metrics from Redfish data dumps."""

import json
from pathlib import Path


def safe_get(data, *keys, default="NA"):
    """Safely navigate nested dict/list structures, returning default if missing."""
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        elif isinstance(current, list):
            if isinstance(key, int) and 0 <= key < len(current):
                current = current[key]
            else:
                return default
        else:
            return default
        if current is None:
            return default
    return current


def extract_chassis_id(member_ref):
    """Extract chassis ID from a member reference like '/redfish/v1/Chassis/1'."""
    if not member_ref:
        return None
    # remove trailing slashes and get the last part
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

    # read Redfish version from index.json (/redfish/v1/ endpoint)
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

    # read Chassis.json
    chassis_json_path = hostname_dir / "Chassis.json"
    if not chassis_json_path.exists():
        return result

    try:
        with open(chassis_json_path, "r") as f:
            chassis_data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return result

    # get chassis members
    members = chassis_data.get("Members", [])
    if not members:
        return result

    # process all chassis members to get power states
    power_states = []
    power_metrics_found = False

    for member in members:
        chassis_id = extract_chassis_id(member.get("@odata.id"))
        if not chassis_id:
            continue

        # read chassis details
        chassis_detail_path = hostname_dir / "Chassis" / f"{chassis_id}.json"
        if not chassis_detail_path.exists():
            continue

        try:
            with open(chassis_detail_path, "r") as f:
                chassis_detail = json.load(f)
        except (json.JSONDecodeError, IOError):
            continue

        # get PowerState
        power_state = safe_get(chassis_detail, "PowerState", default="NA")
        if power_state != "NA":
            power_states.append(power_state.lower())

        # only get power metrics from the first chassis with Power data
        if not power_metrics_found:
            power_ref = chassis_detail.get("Power")
            if power_ref and isinstance(power_ref, dict):
                power_json_path = (
                    hostname_dir / "Chassis" / chassis_id / "Power.json"
                )
                if power_json_path.exists():
                    try:
                        with open(power_json_path, "r") as f:
                            power_data = json.load(f)
                        # extract power metrics from PowerControl array
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

    result["power_states"] = sorted(power_states)

    return result


def main():
    # base directory containing information collected using Redfish
    base_dir = Path(__file__).parents[1] / "data" / "redfish-dump-2025-12-17"

    all_results = []

    # iterate over datacenters and machines
    for datacenter_dir in base_dir.iterdir():
        if not datacenter_dir.is_dir():
            continue

        for hostname_dir in sorted(datacenter_dir.iterdir()):
            if not hostname_dir.is_dir():
                continue

            res = get_power_metrics(hostname_dir, datacenter_dir.name)
            all_results.append(res)

    # display results
    for r in all_results:
        power_states_str = (
            ", ".join(r["power_states"])
            if r["power_states"]
            else "NA"
        )

        print(
            f"[{r['redfish_version']}] [{power_states_str}] "
            f"{r['datacenter']}/{r['hostname']}: "
            f"PowerConsumedWatts={r['PowerConsumedWatts']}, "
            f"MinConsumedWatts={r['MinConsumedWatts']}, "
            f"MaxConsumedWatts={r['MaxConsumedWatts']}, "
            f"AverageConsumedWatts={r['AverageConsumedWatts']}"
        )


if __name__ == "__main__":
    main()
