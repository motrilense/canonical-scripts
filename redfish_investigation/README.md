# Redfish investigation

Small utilities to analyze Redfish data dumps for power and storage (RAID) information.

## Data Layout
- Root dataset: `data/redfish-dump-2025-12-17`
- Structure: `<datacenter>/<hostname>/...` mirroring a Redfish service root (index.json, Systems.json, Chassis.json, etc.)
- Both scripts auto-discover datacenters and hosts by walking the folder tree.

## Power Report
Analyzes chassis power data and reports current/min/max/average power plus observed power states.

- Script: [redfish_investigation/report_power.py](redfish_investigation/report_power.py)
- Extracts: Redfish version, power states, PowerConsumedWatts, Min/Max/AverageConsumedWatts
- Run:
```bash
python3 redfish_investigation/report_power.py
```

## RAID Report
Determines whether hardware RAID is supported and configured, and summarizes controllers and volumes.

- Script: [redfish_investigation/report_raid.py](redfish_investigation/report_raid.py)
- Logic (per host):
  - Read `/redfish/v1/Systems` and pick the first system.
  - Read `/redfish/v1/Systems/<SystemId>/Storage`; if missing/empty → "No storage info exposed via Redfish".
  - For each storage member, inspect `StorageControllers[].SupportedRAIDTypes` and the `Volumes` collection.
  - For each volume, extract `Name`, `RAIDType`, `CapacityBytes`, and referenced `Drives`. A non-null `RAIDType` indicates RAID in use.
  - If a RAID-capable controller exists but no volumes → "RAID supported but not configured".
  - If no RAID-capable controller → "No hardware RAID detected (possible HBA or software RAID)".
- Run:
```bash
python3 redfish_investigation/report_raid.py
```
