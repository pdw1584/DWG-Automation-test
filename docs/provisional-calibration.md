# Provisional Anchor Calibration

## Purpose

This step creates a rough GPS estimate from one known point. It is useful for
checking whether the extracted facility locations appear around the expected
site in Google Earth.

This is not survey-grade calibration. A precise calibration still needs at
least three non-collinear control points.

## Anchor Used

```text
anchor_x: 39901.9198
anchor_y: -207468.5708
anchor_latitude: 35.301563
anchor_longitude: 126.784563
unit assumption: mm
rotation assumption: 0 degrees
```

## Command

```powershell
python -m drawing_mapper.cli apply-provisional-anchor --locations data/final/facility-locations-basis.csv --anchor-x 39901.9198 --anchor-y -207468.5708 --anchor-latitude 35.301563 --anchor-longitude 126.784563 --unit mm --rotation-degrees 0 --output data/final/facility-locations-provisional.csv --report data/final/provisional-calibration-report.json --kml-output data/final/facility-locations-provisional.kml
```

## Outputs

```text
data/final/facility-locations-provisional.csv
data/final/facility-locations-provisional.kml
data/final/provisional-calibration-report.json
```

## Current Result

```text
Input locations: 1,885
Provisional GPS estimates: 1,885
Skipped: 0
Basis-coordinate rows: 1,837
Drawing-coordinate fallback rows: 48
Latitude range: 35.30030410 to 35.31331647
Longitude range: 126.77588217 to 126.81489749
```

Rows where `provisional_coordinate_source=basis` are more reliable than rows
where `provisional_coordinate_source=drawing`. The drawing fallback rows come
from source drawings where no common XREF basis was found.

## Review

Open `data/final/facility-locations-provisional.kml` in Google Earth and check:

1. Whether the points appear near the intended site.
2. Whether the point cloud direction looks rotated relative to the site.
3. Whether the point cloud size looks too large or too small.

If the direction is wrong, rerun the command with a manual
`--rotation-degrees` value. If the size is wrong, the unit assumption may need
to change from `mm` to `cm` or `m`.
