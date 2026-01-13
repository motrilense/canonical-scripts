#!/usr/bin/env python3
"""Report hardware RAID usage and configuration from Redfish data dumps.

This script scans a local dataset under
  data/redfish-dump-2025-12-17/
It inspects Redfish Systems -> Storage -> Storage/<id> -> Volumes to determine
if hardware RAID is supported and configured on each machine.
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
    if not odata_id:
        return None
    parts = odata_id.rstrip("/").split("/")
    return parts[-1] if parts else None


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        if not path.exists():
            return None
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return None


def _bytes_to_gib(num_bytes: int | None) -> float | None:
    if isinstance(num_bytes, int):
        return round(num_bytes / (1024 ** 3), 2)
    return None


def get_raid_information(host_dir: Path, datacenter: str) -> dict[str, Any]:
    """Extract information about RAID capability and configuration."""
    hostname = host_dir.name

    result: dict[str, Any] = {
        "datacenter": datacenter,
        "hostname": hostname,
        "raid_detected": False,
        "raid_capable": False,
        "message": "",
        "controllers": [],  # list[dict]
        "volumes": [],  # list[dict]
    }

    # 1) /redfish/v1/Systems -> choose first system
    systems_path = host_dir / "Systems.json"
    systems = _read_json(systems_path)
    if not systems:
        result["message"] = "No systems info exposed via Redfish"
        return result

    members = safe_get(systems, "Members", default=[]) or []
    if not members:
        result["message"] = "No systems info exposed via Redfish"
        return result

    first_system_ref = safe_get(members, 0, "@odata.id")
    system_id = _last_segment(first_system_ref)
    if not system_id:
        result["message"] = "No systems info exposed via Redfish"
        return result

    # 2) /redfish/v1/Systems/<SystemId>/Storage (try both singular and plural forms)
    storage_collection_path = host_dir / "Systems" / system_id / "Storage.json"
    storage_collection = _read_json(storage_collection_path)
    storage_dir_name = "Storage"
    
    if not storage_collection:
        # pluran from (Storages) has been found to be used in some machines
        storage_collection_path = host_dir / "Systems" / system_id / "Storages.json"
        storage_collection = _read_json(storage_collection_path)
        storage_dir_name = "Storages"
    
    if not storage_collection:
        result["message"] = "No storage info exposed via Redfish"
        return result

    storage_members = safe_get(storage_collection, "Members", default=[]) or []
    if not storage_members:
        result["message"] = "No storage info exposed via Redfish"
        return result

    # iterate storages
    for member in storage_members:
        storage_ref = safe_get(member, "@odata.id")
        storage_id = _last_segment(storage_ref)
        if not storage_id:
            continue

        storage_path = host_dir / "Systems" / system_id / storage_dir_name / f"{storage_id}.json"
        storage = _read_json(storage_path)
        if not storage:
            continue

        # inspect controllers for RAID capability
        controllers = safe_get(storage, "StorageControllers", default=[]) or []
        for ctrl in controllers:
            supported = safe_get(ctrl, "SupportedRAIDTypes", default=[]) or []
            name = safe_get(ctrl, "Name") or safe_get(ctrl, "Model") or "Controller"
            model = safe_get(ctrl, "Model")
            description = safe_get(ctrl, "Description") or ""
            ctrl_info = {
                "name": name,
                "model": model,
                "supported_raid_types": supported,
            }
            result["controllers"].append(ctrl_info)
            
            # detect RAID capability from SupportedRAIDTypes or controller name/description
            if (isinstance(supported, list) and len(supported) > 0) or \
               "raid" in name.lower() or \
               "raid" in description.lower():
                result["raid_capable"] = True

        # volumes collection (if present)
        volumes_ref = safe_get(storage, "Volumes", "@odata.id")
        if not volumes_ref:
            continue

        volumes_path = host_dir / "Systems" / system_id / storage_dir_name / storage_id / "Volumes.json"
        volumes_collection = _read_json(volumes_path)
        if not volumes_collection:
            continue

        volume_members = safe_get(volumes_collection, "Members", default=[]) or []

        for vmem in volume_members:
            vol_ref = safe_get(vmem, "@odata.id")
            vol_id = _last_segment(vol_ref)
            if not vol_id:
                continue
            vol_path = host_dir / "Systems" / system_id / "Storage" / storage_id / "Volumes" / f"{vol_id}.json"
            vol = _read_json(vol_path)
            if not vol:
                continue

            vol_name = safe_get(vol, "Name")
            vol_raid = safe_get(vol, "RAIDType")
            vol_cap_bytes = safe_get(vol, "CapacityBytes")
            vol_cap_gib = _bytes_to_gib(vol_cap_bytes)
            drive_links = safe_get(vol, "Links", "Drives", default=[]) or []
            drive_ids: list[str] = []
            for d in drive_links:
                d_ref = safe_get(d, "@odata.id")
                d_id = _last_segment(d_ref)
                if d_id:
                    drive_ids.append(d_id)

            result["volumes"].append(
                {
                    "name": vol_name,
                    "raid_type": vol_raid,
                    "capacity_bytes": vol_cap_bytes,
                    "capacity_gib": vol_cap_gib,
                    "drives": drive_ids,
                }
            )

            result["raid_detected"] = vol_raid is not None

    if result["raid_detected"]:
        result["message"] = "Hardware RAID detected"
    elif result["raid_capable"]:
        if result["volumes"]:
            # volumes exist but no RAID type is set (HBA/passthrough mode)
            result["message"] = "RAID-capable controller with volumes in HBA mode"
        else:
            # RAID-capable controller but no volumes configured
            result["message"] = "RAID supported but not configured"
    else:
        result["message"] = "No hardware RAID detected (possible HBA or software RAID)"

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

            res = get_raid_information(host_dir, datacenter_dir.name)
            all_results.append(res)

    # display results
    for r in all_results:
        head = f"{r['datacenter']}/{r['hostname']}"
        status = (
            f"raid_detected={r['raid_detected']}, raid_capable={r['raid_capable']}"
        )
        print(f"{head}: {status} --> {r['message']}")

        # Controllers
        if r["controllers"]:
            for c in r["controllers"]:
                sup = c.get("supported_raid_types") or []
                sup_str = ", ".join(sup) if sup else "-"
                print(
                    f"  controller: {c.get('name') or c.get('model') or 'Controller'} | supported: {sup_str}"
                )

        # Volumes
        if r["volumes"]:
            for v in r["volumes"]:
                cap = f"{v['capacity_gib']} GiB" if v.get("capacity_gib") is not None else "NA"
                drives = ", ".join(v.get("drives", [])) if v.get("drives") else "-"
                print(
                    f"  volume: {v.get('name') or '-'} | raid={v.get('raid_type')} | capacity={cap} | drives=[{drives}]"
                )


if __name__ == "__main__":
    main()
