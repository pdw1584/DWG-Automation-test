# V2 오버레이 워크플로우

## 목표

V2에서는 GPS 좌표를 너무 이른 단계에서 강제로 맞추려 하지 않는다. 목표는 사용할 수 있는 도면 좌표 기반 워크플로우를 만드는 것이다.

```text
XR-PLAN 또는 x-plan = 기준 도면
XR-PLAN을 참조하는 평면도 = 오버레이 후보
상세도/확대도 = 기준 도면 위에 수동 배치
사용자는 확정된 오버레이 도면 세트에서 좌표를 읽음
```

## 현재 작업 폴더

```text
data/legacy/                 이전 metadata/final/review 결과
data/raw/                    원본 DWG 파일
data/converted/dxf/          변환된 DXF 파일
data/overlay/                V2 오버레이 작업 영역
data/overlay/v2/             XR-PLAN RAW 수집 및 수동 검토 파일
```

## 오버레이 계획 생성

```powershell
python -m drawing_mapper.cli build-overlay-plan --xref-inventory data/legacy/metadata/xref-inventory.csv --facility-locations data/legacy/metadata/facility-location-high-confidence.csv --output-dir data/overlay
```

중요 출력 파일:

```text
data/overlay/drawing-overlay-groups.csv
data/overlay/drawing-overlay-drawings.csv
data/overlay/xr-plan-identity-review-list.csv
```

## XR-PLAN RAW DWG 수집

```powershell
python -m drawing_mapper.cli collect-xr-plan-raw --overlay-drawings data/overlay/drawing-overlay-drawings.csv --raw-root data/raw --output-dir data/overlay/v2
```

현재 결과:

```text
XR-PLAN 참조 행: 56
누락된 RAW 파일: 0
복사된 고유 DWG 파일: 46
Identity 행: 36
Transformed 행: 20
```

중요 출력 파일:

```text
data/overlay/v2/xr-plan-raw/
data/overlay/v2/xr-plan-raw-manifest.csv
data/overlay/v2/xr-plan-identity-raw-list.csv
data/overlay/v2/xr-plan-transformed-raw-list.csv
data/overlay/v2/xr-plan-unique-copied-files.csv
data/overlay/v2/manual-placement-template.csv
```

## CAD 검토 순서

먼저 다음 파일부터 확인한다.

```text
data/overlay/v2/xr-plan-identity-raw-list.csv
```

이 행들은 다음 조건으로 `XR-PLAN`을 참조한다.

```text
insert_x = 0
insert_y = 0
xscale = 1
yscale = 1
rotation = 0
```

`facility_count`가 가장 높은 도면부터 먼저 확인한다.

```text
E-T73_EPMS 평면도.dwg
E-J03_전력간선설비 평면도(BUS DUCT).dwg
E-H03_전력간선설비 평면도(LV).dwg
E-I03_전력간선설비 평면도(UPS).dwg
E-G03_전력간선설비 평면도(HV).dwg
```

이 도면들이 `XR-PLAN`과 정확히 겹친다면, 해당 도면에서 추출된 설비 위치는 XR-PLAN 도면 좌표로 취급할 수 있다.

## 수동 배치

기준 좌표계를 공유하지 않는 상세도 또는 확대도는 `XR-PLAN` 위에 수동으로 배치하고, 그 변환값을 다음 파일에 기록한다.

```text
data/overlay/v2/manual-placement-template.csv
```

필수 필드:

```text
detail_drawing
insert_x
insert_y
xscale
yscale
rotation_degrees
review_status
review_note
```

이렇게 하면 수동 배치 결과가 데이터로 보존되므로, 이후 설비 좌표를 기준 도면 좌표계로 다시 변환할 수 있다.

## 아직 사용하지 말 것

기존 임시 GPS 결과를 최종 좌표로 사용하지 않는다. 해당 결과는 1점 GPS 앵커 방식이 충분히 신뢰할 수 없다는 것을 확인하는 데에는 유용했다.

GPS 보정은 기준 도면 좌표 워크플로우가 확정되고, 실제 기준점이 최소 3개 이상 확보된 뒤에 다시 진행해야 한다.
