#!/usr/bin/env python3
"""Extract temperature sensor readings from Redfish data dumps.

This script scans a local dataset under data/redfish-dump-2025-12-17/
and reports temperature readings from the Thermal endpoint for each machine.
"""

import json
from pathlib import Path
from typing import Any


def safe_get(data: Any, *keys, default=None):
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


def _last_segment(odata_id: str | None) -> str | None:
    """Extract the last segment from an OData ID path."""
    if not odata_id:
        return None
    parts = odata_id.rstrip("/").split("/")
    return parts[-1] if parts else None


def _read_json(path: Path) -> dict[str, Any] | None:
    """Read and parse a JSON file, returning None on error."""
    try:
        if not path.exists():
            return None
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return None


def get_temperature_information(host_dir: Path, datacenter: str) -> dict[str, Any]:
    """Extract temperature sensor readings from Thermal endpoint."""
    hostname = host_dir.name
    
    result: dict[str, Any] = {
        "datacenter": datacenter,
        "hostname": hostname,
        "power_states": [],  # one power state per chassis per machine
        "temperatures": [],  # list of temperature sensor readings
        "message": "",
    }

    # /redfish/v1/Chassis
    chassis_path = host_dir / "Chassis.json"
    chassis_data = _read_json(chassis_path)
    
    if not chassis_data:
        result["message"] = "No chassis info exposed via Redfish"
        return result
    
    members = safe_get(chassis_data, "Members", default=[]) or []
    
    if not members:
        result["message"] = "No chassis members exposed via Redfish"
        return result
    
    # iterate over each chassis member
    for member in members:
        chassis_ref = safe_get(member, "@odata.id")
        chassis_id = _last_segment(chassis_ref)
        
        if not chassis_id:
            continue
        
        # read chassis details to get power state
        chassis_detail_path = host_dir / "Chassis" / f"{chassis_id}.json"
        chassis_detail = _read_json(chassis_detail_path)
        
        if chassis_detail:
            power_state = safe_get(chassis_detail, "PowerState", default="NA")
            if power_state != "NA":
                result["power_states"].append(power_state.lower())
        
        # read Thermal.json for this chassis
        thermal_path = host_dir / "Chassis" / chassis_id / "Thermal.json"
        thermal_data = _read_json(thermal_path)
        
        if not thermal_data:
            continue
        
        # extract Temperatures array
        temperatures = safe_get(thermal_data, "Temperatures", default=[]) or []
        
        for temp_sensor in temperatures:
            reading = safe_get(temp_sensor, "ReadingCelsius", default="NA")
            
            name = safe_get(temp_sensor, "Name", default="-")
            physical_context = safe_get(temp_sensor, "PhysicalContext", default="-")
            
            sensor_info = {
                "chassis_id": chassis_id,
                "name": name,
                "reading": reading,
                "physical_context": physical_context,
            }
            
            result["temperatures"].append(sensor_info)
    
    # set message
    if result["temperatures"]:
        result["message"] = f"Found {len(result['temperatures'])} temperature sensor(s)"
    else:
        result["message"] = "No temperature sensors found"
    
    return result


def main():
    # base directory containing information collected using Redfish
    base_dir = Path(__file__).parents[1] / "data" / "redfish-dump-2025-12-17"
    
    all_results: list[dict[str, Any]] = []
    
    # iterate over datacenters and machines
    for datacenter_dir in base_dir.iterdir():
        if not datacenter_dir.is_dir():
            continue
        
        for host_dir in sorted(datacenter_dir.iterdir()):
            if not host_dir.is_dir():
                continue
            
            res = get_temperature_information(host_dir, datacenter_dir.name)
            all_results.append(res)
    
    # display results
    #   Output pattern (for each machine):
    #   [<power state chassis0>, <power state chassis1>...] <datacenter/hostname>: <summary message>
    #     [<chassis ID>] <temperature sensor name>°C (Context: <PhysicalContext>)
    #     ...
    for r in all_results:
        power_states_str = (
            ", ".join(r["power_states"])
            if r["power_states"]
            else "NA"
        )
        print(f"[{power_states_str}] {r['datacenter']}/{r['hostname']}: {r['message']}")
        
        for temp in r["temperatures"]:
            print(
                f"  [{temp['chassis_id']}] {temp['name']}: "
                f"{temp['reading']}°C "
                f"(Context: {temp['physical_context']})"
            )


if __name__ == "__main__":
    main()
