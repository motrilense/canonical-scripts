# Redfish investigation

Study of Redfish RESTful API for potential usage in some projects.

## Overview

This script extracts power consumption metrics from Redfish data dumps. It processes JSON files from multiple data centers and machines, extracting:
- Redfish version
- Power states
- Power consumption metrics (current, min, max, average)

## Usage

```bash
python3 ./redfish_investigation/script.py
```

The script expects data to be placed under `data/redfish-dump-2025-12-17` with subdirectories representing data centers, each containing hostname directories with Redfish JSON dumps. 
