# Coordinate Basis Mapping

## Purpose

`facility-locations.csv` contains coordinates from each source DXF drawing. Those
coordinates are not always in the same drawing coordinate system.

This step attaches an XREF-based coordinate basis to each facility location so
later calibration can use a common plan coordinate such as `XR-PLAN`, `X-SITE`,
or floor-specific `x-plan` drawings.

## Command

```powershell
python -m drawing_mapper.cli map-coordinate-basis --locations data/final/facility-locations.csv --xref-inventory data/metadata/xref-inventory.csv --output data/final/facility-locations-basis.csv --report data/final/coordinate-basis-report.json
```

## Outputs

```text
data/final/facility-locations-basis.csv
data/final/coordinate-basis-report.json
```

`facility-locations-basis.csv` keeps the original facility columns and adds:

```text
basis_x
basis_y
coordinate_basis
basis_status
basis_confidence
basis_reason
xref_name
xref_path
xref_insert_x
xref_insert_y
xref_xscale
xref_yscale
xref_rotation
```

## Current Result

```text
Facility locations: 1,885
Mapped to an XREF basis: 1,837
Unmapped: 48
Primary basis: XR-PLAN, 1,089 rows
```

The unmapped rows are mostly drawings such as enlarged EPS/GIS/detail drawings
where no usable plan-like XREF was found in the current XREF inventory.

## Next Step

Use `basis_x` and `basis_y` for calibration instead of raw `drawing_x` and
`drawing_y` when `basis_status` is `mapped`.

For final GPS conversion, control points should be selected on the same basis
drawings, preferably `XR-PLAN` or the relevant `x-plan_*` floor plan.

After filling `data/final/coordinate-calibration-template.csv`, run calibration
with the basis-enriched location file:

```powershell
python -m drawing_mapper.cli apply-calibration --locations data/final/facility-locations-basis.csv --calibration data/final/coordinate-calibration-template.csv --output data/final/facility-locations-basis-calibrated.csv --report data/final/coordinate-calibration-basis-report.json
```

The calibration code now prefers `basis_x` and `basis_y` when
`basis_status=mapped`; otherwise it falls back to `drawing_x` and `drawing_y`.
