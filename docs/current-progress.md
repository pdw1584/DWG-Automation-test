# Current Progress

## Pipeline Status

| Step | Status | Output |
| --- | --- | --- |
| Google Drive sync | Done | `data/raw` |
| DWG inventory | Done | `data/metadata/dwg-inventory.csv` |
| Priority selection | Done | `04_설계도서/01~04` |
| DWG to DXF | Done | `data/converted/dxf/04_설계도서` |
| DXF to JSON | Done | `data/parsed/dxf/04_설계도서` |
| Equipment extraction | Done | `data/metadata/equipment-candidates.csv` |
| Location candidate filtering | Done | `data/metadata/equipment-location-candidates.csv` |
| Facility location draft | Done | `data/metadata/facility-location-draft.csv` |
| High-confidence location list | Done | `data/metadata/facility-location-high-confidence.csv` |
| Human review CSV | Done | `data/review/facility-location-review.csv` |
| Interim final export | Done | `data/final/facility-locations.csv` |
| Coordinate calibration template | Done | `data/final/coordinate-calibration-template.csv` |
| Drive ID filename cleanup | Done | `data/metadata/drive-id-cleanup.json` |
| Coordinate calibration command | Done | `data/final/coordinate-calibration-report.json` |
| XREF inventory | Done | `data/metadata/xref-inventory.csv` |
| PLAN/SITE XREF candidates | Done | `data/metadata/xref-plan-candidates.csv` |
| Coordinate basis mapping | Done | `data/final/facility-locations-basis.csv` |
| Basis-aware calibration command | Done | `data/final/coordinate-calibration-basis-report.json` |
| Provisional anchor calibration | Done | `data/final/facility-locations-provisional.csv` |

## Counts

```text
Downloaded DWG: 2,187
Priority converted DXF: 752
Raw equipment candidates: 64,160
Equipment refined candidates: 8,742
Location candidates: 3,063
Facility location draft: 2,985
Facility location high confidence: 1,885
Review CSV rows: 1,885
Interim final facility locations: 1,885
Calibration template rows: 27
Calibration transforms: 0
Calibrated facility locations: 0
XREF inventory rows: 15,716
PLAN/SITE XREF candidate rows: 1,579
XR-PLAN references: 56
XR-PLAN identity inserts: 36
Coordinate basis mapped locations: 1,837
Coordinate basis unmapped locations: 48
Basis-aware calibration transforms: 0
Basis-aware calibrated locations: 0
Provisional anchor calibrated locations: 1,885
Provisional coordinate source basis: 1,837
Provisional coordinate source drawing fallback: 48
```

High-confidence location candidates by floor:

```text
1F: 308
2F: 93
3F: 565
4F: 143
5F: 599
6F: 141
PH: 3
PIT: 24
ROOF: 9
```

## Important Files

```text
data/metadata/equipment-location-candidates.csv
data/metadata/equipment-location-by-floor/1F.csv
data/metadata/equipment-location-by-floor/2F.csv
data/metadata/equipment-location-by-floor/3F.csv
data/metadata/equipment-location-by-floor/4F.csv
data/metadata/equipment-location-by-floor/5F.csv
data/metadata/equipment-location-by-floor/6F.csv
data/metadata/equipment-location-by-floor/PH.csv
data/metadata/equipment-location-by-floor/PHR.csv
data/metadata/equipment-location-by-floor/PIT.csv
data/metadata/equipment-location-by-floor/unknown.csv
data/metadata/facility-location-draft.csv
data/metadata/facility-location-high-confidence.csv
data/review/facility-location-review.csv
data/review/facility-location-review-clean.csv
data/final/facility-locations.csv
data/final/facility-locations-basis.csv
data/final/coordinate-calibration-template.csv
data/final/facility-locations-calibrated.csv
data/final/coordinate-calibration-report.json
data/final/coordinate-basis-report.json
data/final/facility-locations-basis-calibrated.csv
data/final/coordinate-calibration-basis-report.json
data/final/facility-locations-provisional.csv
data/final/facility-locations-provisional.kml
data/final/provisional-calibration-report.json
data/metadata/drive-id-cleanup.json
data/metadata/xref-inventory.csv
data/metadata/xref-plan-candidates.csv
docs/location-review.md
docs/final-export.md
docs/xref-analysis.md
docs/coordinate-basis.md
docs/provisional-calibration.md
```

## Next Work

1. Review `data/metadata/xref-plan-candidates.csv` and select the base plan reference.
2. Prefer `XR-PLAN` identity inserts for common drawing-coordinate alignment.
3. Use `data/final/facility-locations-basis.csv` as the calibration input where `basis_status=mapped`.
4. Open `data/final/facility-locations-provisional.kml` in Google Earth and check rough placement.
5. If the provisional points are rotated or scaled incorrectly, rerun provisional calibration with adjusted rotation/unit.
6. Fill `data/final/coordinate-calibration-template.csv` with real control points from `XR-PLAN` or `X-SITE` when more control points are available.
7. Re-run `apply-calibration` after control points are filled.
8. Verify sample calibrated points on a map or GIS.
