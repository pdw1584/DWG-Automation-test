# Drawing Overlay Plan

## Why This Step Exists

The one-point GPS estimate was too unstable. The next reliable step is to check
how drawings overlap each other before trying GPS calibration again.

This plan uses DXF XREF information to group drawings by their referenced base
plan and insert transform.

## Command

```powershell
python -m drawing_mapper.cli build-overlay-plan --xref-inventory data/legacy/metadata/xref-inventory.csv --facility-locations data/legacy/metadata/facility-location-high-confidence.csv --output-dir data/overlay
```

## Outputs

```text
data/overlay/drawing-overlay-groups.csv
data/overlay/drawing-overlay-drawings.csv
data/overlay/drawing-overlay-report.json
data/overlay/xr-plan-identity-review-list.csv
```

## Current Result

```text
Overlay groups: 936
Overlay drawing rows: 1,937
Identity insert groups: 6
```

Priority breakdown:

```text
A_XR_PLAN_IDENTITY: 1 group
B_XR_PLAN_TRANSFORMED: 17 groups
C_SITE_WITH_FACILITIES: 2 groups
D_FLOOR_PLAN_WITH_FACILITIES: 94 groups
E_OTHER_WITH_FACILITIES: 222 groups
Z_REFERENCE_ONLY: 600 groups
```

## First Review Target

Start with this group:

```text
overlay_group_id: xr-plan_0_0_1_1_0
priority: A_XR_PLAN_IDENTITY
basis: XR-PLAN.dwg
insert_x: 0
insert_y: 0
xscale: 1
yscale: 1
rotation: 0
drawing_count: 36
facility_count: 1,052
```

These drawings should be directly comparable with `XR-PLAN` coordinates because
their XREF insert is identity. Open the drawings listed in:

```text
data/overlay/xr-plan-identity-review-list.csv
```

Review the highest `facility_count` drawings first.

## Manual CAD Check

1. Open `XR-PLAN.dwg` or the converted `XR-PLAN.dxf` if available.
2. Open one high-priority drawing from `xr-plan-identity-review-list.csv`.
3. Confirm that building outlines, grid lines, and major equipment rooms overlap.
4. If the overlay is correct, trust the `basis_x` and `basis_y` values for that group.
5. If the overlay is shifted, inspect the XREF insert values and whether the opened file is a duplicated folder version.

## Second Review Target

After the identity group is confirmed, review `B_XR_PLAN_TRANSFORMED` groups.
Those need an inverse insert transform before comparing with `XR-PLAN`.

The transformed group with the most equipment is:

```text
overlay_group_id: xr-plan_0_356400.000642_1_1_0
facility_count: 48
sample drawing: E-K02_AC & DC Control 전원설비 평면도.dxf
```

## Important Note

The old GPS provisional outputs were moved under `data/legacy` and should not be
used as reliable final coordinates. The useful legacy outputs are the floor-based
equipment CSVs and the XREF/facility metadata used to build this overlay plan.
