# Drawing Facility Mapper 진행 보고

## 1. 프로젝트 목적

Google Drive에 저장된 도면 파일을 자동 수집하고, DWG 도면을 DXF/JSON으로 변환한 뒤, 도면 내 설비 텍스트와 좌표를 추출하여 층별 설비 위치 후보를 만드는 것을 목표로 한다.

최종 목표 데이터는 아래 형태이다.

```text
floor, equipment_name, drawing_x, drawing_y, latitude, longitude, source_drawing
```

현재는 도면 내부 좌표 기반의 설비 위치 후보까지 생성한 상태이며, 실제 GPS 좌표 변환을 위한 기준점 보정 단계가 남아 있다.

## 2. 현재까지 완료된 작업

### Google Drive 도면 수집

- Google Drive 서비스 계정 기반 접근 구현
- Drive 하위 폴더 재귀 탐색 구현
- DWG 파일 중심 수집
- `Archive` 포함 폴더와 정확히 `OLD`인 폴더 제외
- Drive 메타데이터 기준 DWG 파일 수: `2,187`

### 도면 변환 및 파싱

- ODA File Converter 연동
- 우선순위 도면 범위 설정: `04_설계도서/01~04`
  - `01_건축_구조`
  - `02_전기`
  - `03_기계`
  - `04_통신`
- 우선순위 DWG -> DXF 변환 완료: `752`
- DXF -> JSON 파싱 완료

### 설비 후보 추출

- 전원, 냉각, 통신 관제, 전기, 기계, 소방, 배관, 통신 키워드 기반 설비 후보 추출
- 전체 설비 후보: `64,160`
- 정제된 설비 후보: `11,866`
- 위치 도면 기반 후보: `4,279`
- 시설 위치 초안: `3,532`
- 고신뢰 시설 위치 후보: `2,360`

### 파일명 정리

기존에는 Google Drive 파일 ID가 로컬 파일명 앞에 붙어 있었다.

```text
1EvnFqg8HjefSzcWxMD64Oc6v5nN0j27c_E-T73_EPMS 평면도.dxf
```

이 방식은 CAD XREF 참조가 원본 파일명을 기준으로 연결되는 경우 문제가 될 수 있어, 로컬 DWG/DXF/JSON 파일명에서 Drive ID prefix를 제거했다.

```text
E-T73_EPMS 평면도.dxf
```

현재 RAW 폴더와 CONVERTED 폴더의 실제 경로가 서로 달라 직접 경로 지정이 필요한 경우는 있으나, XREF 연결 가능성은 확인된 상태이다.

## 3. 주요 산출물

```text
data/metadata/dwg-inventory.csv
data/metadata/equipment-candidates.csv
data/metadata/equipment-candidates-summary.csv
data/metadata/equipment-candidates-refined.csv
data/metadata/equipment-location-candidates.csv
data/metadata/facility-location-draft.csv
data/metadata/facility-location-high-confidence.csv
data/review/facility-location-review-clean.csv
data/final/facility-locations.csv
data/final/facility-locations-calibrated.csv
data/final/coordinate-calibration-template.csv
data/final/coordinate-calibration-report.json
```

현재 최종 후보 테이블은 아래 파일이다.

```text
data/final/facility-locations.csv
```

해당 파일에는 건물명, 주소, 층, 설비명, 도면 좌표, 신뢰도, 원본 도면 경로가 포함되어 있다.

## 4. 현재 좌표 관련 핵심 이슈

현재 추출된 `drawing_x`, `drawing_y`는 각 원본 DWG/DXF 파일 내부에 그려진 도면 좌표를 의미한다.

즉, 이 값은 실제 지어질 건물의 GPS 좌표 또는 현장 절대 좌표를 직접 가리키지 않는다.

예를 들어 같은 `1F` 설비라 하더라도 도면 파일마다 원점, 축척, 회전, 배치 기준이 다를 수 있다. 따라서 현재 좌표만으로는 실제 부지 위의 위치를 바로 계산할 수 없다.

실제 좌표화를 위해서는 다음 기준이 필요하다.

1. 건축 부지 전체 기준 도면 선정
2. 각 층 또는 주요 도면별 기준점 선정
3. 기준점의 도면 좌표 입력
4. 기준점의 실제 GPS 좌표 또는 현장 기준 좌표 입력
5. 기준점을 이용한 affine transform 등 좌표 보정 계산
6. 설비별 `drawing_x`, `drawing_y`를 실제 `latitude`, `longitude`로 변환

현재 이를 위해 아래 템플릿을 생성해둔 상태이다.

```text
data/final/coordinate-calibration-template.csv
```

현재 기준점이 입력되지 않아 보정 결과는 아직 생성되지 않았다.

```text
Calibration transforms: 0
Calibrated facility locations: 0
Skipped facility locations: 2,360
```

## 5. XREF 분석 결과

DXF 내부 외부참조 구조를 분석하여 아래 산출물을 생성했다.

```text
data/metadata/xref-inventory.csv
data/metadata/xref-plan-candidates.csv
docs/xref-analysis.md
```

전체 XREF 추출 결과는 다음과 같다.

```text
XREF inventory rows: 15,716
PLAN/SITE candidate rows: 1,579
XR-PLAN references: 56
XR-PLAN identity inserts: 36
```

특히 여러 전기/통신 평면도에서 `XR-PLAN`이 아래 조건으로 삽입되어 있었다.

```text
insert_x = 0
insert_y = 0
xscale = 1
yscale = 1
rotation = 0
```

따라서 이 도면들은 현재 추출된 `drawing_x`, `drawing_y`가 `XR-PLAN` 기준 좌표와 동일한 좌표계일 가능성이 높다.

`XR-PLAN`은 설비 도면들을 공통 건축 평면 기준으로 묶는 데 사용할 수 있으며, 최종 GPS 좌표 보정은 `X-SITE` 또는 건축 배치도와 연결하여 수행하는 것이 적절하다.

## 6. 다음 단계

### 1차 우선 작업

- `xref-plan-candidates.csv`에서 `XR-PLAN`, `X-SITE`, `X-1F-PLAN` 계열 검토
- 건축 부지 전체 기준 도면 선정
- 각 층별 기준점 최소 3개 선정
- 기준점별 `drawing_x`, `drawing_y`, `latitude`, `longitude` 입력
- `coordinate-calibration-template.csv` 작성

### 이후 작업

- `apply-calibration` 명령으로 좌표 보정 실행
- `facility-locations-calibrated.csv` 생성
- 샘플 설비 좌표를 지도 또는 GIS에서 검증
- 오차가 크면 층별/도면별 기준점 추가
- 필요 시 검수 CSV를 통해 설비 후보 승인/제외 반영

보정 실행 명령은 아래와 같다.

```powershell
python -m drawing_mapper.cli apply-calibration --locations data/final/facility-locations.csv --calibration data/final/coordinate-calibration-template.csv --output data/final/facility-locations-calibrated.csv --report data/final/coordinate-calibration-report.json
```

## 7. 현재 판단

도면 수집, 변환, 파싱, 설비 후보 추출, 고신뢰 후보 생성까지는 MVP 수준으로 동작한다.

다만 현재 좌표는 도면 내부 좌표이므로, 실제 건물 좌표로 활용하기 위해서는 건축 부지 기준 도면과 기준점 기반 좌표 보정 과정이 필수이다.

현재 분석상 `XR-PLAN`은 공통 평면 좌표계 후보로 유효하며, identity insert 도면부터 우선 적용하는 것이 가장 안정적인 접근으로 보인다.
