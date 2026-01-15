#!/usr/bin/env python3
"""Identify device types from Redfish data dumps.

This script scans a local dataset under data/redfish-dump-2025-12-17/
and identifies device types based on the Chassis endpoint information.

Device identification:
- RackMount/Rack ChassisType → Standard Server
- Card ChassisType → DPU (Data Processing Unit)
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


# def classify_device_type(chassis_type: str | None) -> str:
#     """Classify device type based on ChassisType."""
#     if not chassis_type:
#         return "Unknown"
    
#     chassis_type_lower = chassis_type.lower()
    
#     if chassis_type_lower in ["rackmount", "rack"]:
#         return "Server"
#     elif chassis_type_lower == "card":
#         return "DPU"
#     else:
#         return f"Other ({chassis_type})"


def get_device_information(host_dir: Path, datacenter: str) -> dict[str, Any]:
    """Extract device type information from Chassis endpoint."""
    hostname = host_dir.name
    
    result: dict[str, Any] = {
        "datacenter": datacenter,
        "hostname": hostname,
        "chassis_info": [],  # list of chassis with their details
        "message": "",
    }
    
    # read Chassis.json
    chassis_path = host_dir / "Chassis.json"
    chassis_data = _read_json(chassis_path)
    
    if not chassis_data:
        result["message"] = "No chassis info exposed via Redfish"
        return result
    
    members = safe_get(chassis_data, "Members", default=[]) or []
    
    if not members:
        result["message"] = "No chassis members found"
        return result
    
    # iterate over each chassis member
    for member in members:
        chassis_ref = safe_get(member, "@odata.id")
        chassis_id = _last_segment(chassis_ref)
        
        if not chassis_id:
            continue
        
        # read individual chassis detail
        chassis_detail_path = host_dir / "Chassis" / f"{chassis_id}.json"
        chassis_detail = _read_json(chassis_detail_path)
        
        if not chassis_detail:
            continue
        
        chassis_type = safe_get(chassis_detail, "ChassisType")
        manufacturer = safe_get(chassis_detail, "Manufacturer")
        model = safe_get(chassis_detail, "Model")
        serial = safe_get(chassis_detail, "SerialNumber")
        
        chassis_info = {
            "chassis_id": chassis_id,
            "chassis_type": chassis_type or "Unknown",
            "manufacturer": manufacturer or "Unknown",
            "model": model or "Unknown",
            "serial": serial or "Unknown",
        }
        
        result["chassis_info"].append(chassis_info)
    
    # message
    if result["chassis_info"]:
        chassis_summary = ", ".join([
            f"{c['chassis_type']}" 
            for c in result["chassis_info"]
        ])
        result["message"] = f"found {len(result['chassis_info'])} chassis: {chassis_summary}"
    else:
        result["message"] = "No chassis details available"
    
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
            
            res = get_device_information(host_dir, datacenter_dir.name)
            all_results.append(res)
    
    # display results
    for r in all_results:
        print(f"{r['datacenter']}/{r['hostname']}: {r['message']}")
        
        for c in r["chassis_info"]:
            print(
                f"  [{c['chassis_id']}]: "
                f"{c['manufacturer']} | {c['model']} "
                f"(ChassisType: {c['chassis_type']}, S/N: {c['serial']})"
            )


if __name__ == "__main__":
    main()
