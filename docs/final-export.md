# Final Export Guide

검수를 건너뛰는 동안에는 고신뢰 후보를 임시 최종 설비 위치 테이블로 사용합니다.

## Export Command

```powershell
python -m drawing_mapper.cli export-final --config config/project.json --input data/metadata/facility-location-high-confidence.csv --output data/final/facility-locations.csv --calibration-output data/final/coordinate-calibration-template.csv
```

## Output Files

- `data/final/facility-locations.csv`: 자동 추출된 임시 최종 설비 위치 테이블입니다.
- `data/final/coordinate-calibration-template.csv`: 도면 좌표를 GPS 좌표로 보정하기 위한 기준점 입력 템플릿입니다.

## Coordinate Calibration Template

각 층마다 최소 3개 기준점이 필요합니다.

기준점은 도면에서 식별 가능한 지점이어야 합니다.
예를 들면 건물 모서리, 기둥 교차점, 기준 Grid 교차점처럼 도면 좌표와 실제 GPS 좌표를 함께 알 수 있는 위치가 좋습니다.

```text
floor, control_point_name, drawing_x, drawing_y, latitude, longitude, note
```

이 템플릿이 채워지면 다음 단계에서 도면 좌표를 실제 위도/경도로 변환하는 보정 함수를 붙일 수 있습니다.

## Apply Calibration

`coordinate-calibration-template.csv`에 각 층별 기준점 3개 이상을 채운 뒤 아래 명령을 실행합니다.

```powershell
python -m drawing_mapper.cli apply-calibration --locations data/final/facility-locations.csv --calibration data/final/coordinate-calibration-template.csv --output data/final/facility-locations-calibrated.csv --report data/final/coordinate-calibration-report.json
```

출력 파일:

- `data/final/facility-locations-calibrated.csv`: `latitude`, `longitude`가 채워진 설비 위치 파일입니다.
- `data/final/coordinate-calibration-report.json`: 층별 보정식과 보정/스킵 건수 리포트입니다.

현재 템플릿이 비어 있으면 보정식이 만들어지지 않으므로 모든 설비가 스킵됩니다.
