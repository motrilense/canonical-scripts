#!/usr/bin/env python3
"""Extract fan RPM metrics from Redfish data dumps.

This script scans a local dataset under data/redfish-dump-2025-12-17/
and reports fan RPM readings from the Thermal endpoint for each machine.
"""

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


def get_fan_metrics(hostname_dir, datacenter):
    """Extract fan metrics from a hostname directory."""
    hostname = hostname_dir.name
    result = {
        "datacenter": datacenter,
        "hostname": hostname,
        "power_states": [],  # one power state per chassis per machine
        "fans": [],  # list of fan RPMs
    }

    # /redfish/v1/Chassis
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

    # process all chassis members to get fan information
    for member in members:
        chassis_id = extract_chassis_id(member.get("@odata.id"))
        if not chassis_id:
            continue

        # read chassis details to check if Thermal endpoint exists
        chassis_detail_path = hostname_dir / "Chassis" / f"{chassis_id}.json"
        if not chassis_detail_path.exists():
            continue

        try:
            with open(chassis_detail_path, "r") as f:
                chassis_detail = json.load(f)
        except (json.JSONDecodeError, IOError):
            continue

        # get power state
        power_state = safe_get(chassis_detail, "PowerState", default="NA")
        if power_state != "NA":
            result["power_states"].append(power_state.lower())

        # check for Thermal endpoint
        thermal_ref = chassis_detail.get("Thermal")
        if thermal_ref and isinstance(thermal_ref, dict):
            thermal_json_path = (
                hostname_dir / "Chassis" / chassis_id / "Thermal.json"
            )
            if thermal_json_path.exists():
                try:
                    with open(thermal_json_path, "r") as f:
                        thermal_data = json.load(f)
                    # extract fan metrics from Fans array
                    fans = thermal_data.get("Fans", [])
                    for fan in fans:
                        fan_name = safe_get(fan, "Name")
                        fan_reading = safe_get(fan, "Reading")
                        
                        result["fans"].append({
                            "name": fan_name,
                            "reading_rpm": fan_reading,
                        })
                except (json.JSONDecodeError, IOError):
                    pass

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

            res = get_fan_metrics(hostname_dir, datacenter_dir.name)
            all_results.append(res)

    # display results
    #   Output pattern (for each machine):
    #   [<power state chassis0>, <power state chassis1>...] <datacenter/hostname>: <summary message>
    #     [<chassis ID>] <fan sensor name>: <reported value> RPM
    #     ...
    for r in all_results:
        power_states_str = (
            ", ".join(r["power_states"])
            if r["power_states"]
            else "NA"
        )
        
        if not r["fans"]:
            print(f"[{power_states_str}] {r['datacenter']}/{r['hostname']}: No fan information available")
        else:
            print(f"[{power_states_str}] {r['datacenter']}/{r['hostname']}:")
            for fan in r["fans"]:
                print(f"  {fan['name']}: {fan['reading_rpm']} RPM")


if __name__ == "__main__":
    main()
