# Drawing Facility Mapper

Google Drive에 있는 DWG 도면을 자동 수집하고, DXF/JSON으로 변환한 뒤
층별 설비 위치 후보를 추출하는 프로젝트입니다.

현재 목표는 아래 흐름을 자동화하는 것입니다.

```text
Google Drive
  -> DWG download
  -> DWG inventory
  -> DWG to DXF conversion
  -> DXF to JSON parsing
  -> equipment candidate extraction
  -> floor-based equipment location candidates
  -> interim final facility location table
```

## Current Progress

완료된 작업:

- Google Drive 서비스 계정 기반 동기화 구현
- Drive 하위 폴더 재귀 탐색 구현
- `.dwg`만 수집하도록 필터링
- `Archive` 포함 폴더와 정확히 `OLD`인 폴더 제외
- 전체 DWG 다운로드 완료: `2,187`개
- 우선순위 도면 범위 선정: `04_설계도서/01~04`
- ODA File Converter 연동
- 우선순위 DWG -> DXF 변환 완료: `752`개
- DXF -> JSON 파싱 완료
- 설비 후보 추출/요약/정제 완료
- 위치 도면 중심 설비 후보 생성 완료
- 중복 후보를 합친 시설 위치 초안 생성 완료
- 바로 검토하기 좋은 고신뢰 시설 위치 후보 생성 완료
- 승인/제외/메모를 입력할 수 있는 검수용 CSV 생성 완료
- 검수를 건너뛴 임시 최종 설비 위치 테이블 생성 완료
- 층별 좌표 보정 기준점 템플릿 생성 완료
- CAD XREF가 깨지지 않도록 로컬 DWG/DXF/JSON 파일명에서 Drive ID prefix 제거 완료

주요 결과:

```text
data/metadata/dwg-inventory.csv
data/metadata/equipment-candidates.csv
data/metadata/equipment-candidates-summary.csv
data/metadata/equipment-candidates-refined.csv
data/metadata/equipment-location-candidates.csv
data/metadata/equipment-location-by-floor/
data/metadata/facility-location-draft.csv
data/metadata/facility-location-high-confidence.csv
data/review/facility-location-review.csv
data/review/facility-location-review-clean.csv
data/final/facility-locations.csv
data/final/coordinate-calibration-template.csv
data/final/facility-locations-calibrated.csv
data/final/coordinate-calibration-report.json
```

현재 위치 후보 수:

```text
raw equipment candidates: 64,160
refined equipment candidates: 11,866
location candidates: 4,279
facility location draft: 3,532
facility location high confidence: 2,360

high confidence by floor:
1F: 433
2F: 98
3F: 721
4F: 187
5F: 764
6F: 148
ROOF: 9
```

## Directory Guide

```text
config/
```

프로젝트 설정 파일이 있습니다.

- `project.json`: 실제 실행 설정입니다. Drive folder ID, ODA 경로, 변환 우선순위가 들어갑니다.
- `project.example.json`: 예시 설정입니다.
- `equipment-keywords.example.json`: 설비 후보 추출에 쓰는 키워드 사전입니다.

```text
data/raw/
```

Google Drive에서 내려받은 원본 DWG가 저장됩니다.
Drive 폴더 구조를 최대한 보존합니다.

```text
data/converted/
```

ODA File Converter로 변환한 DXF 파일이 저장됩니다.

```text
data/parsed/
```

DXF/PDF/SVG를 파싱해서 만든 JSON 파일이 저장됩니다.

```text
data/metadata/
```

파이프라인 중간 산출물이 모입니다.
검수는 대부분 이 폴더의 CSV 파일을 보면 됩니다.

```text
data/review/
```

사람이 검수할 CSV가 저장됩니다.
`review_status`, `review_note`, `canonical_equipment_name` 컬럼을 채우면 됩니다.

```text
data/final/
```

외부 시스템에 넘기거나 GPS 보정을 붙일 최종 산출물이 저장됩니다.

```text
docs/
```

설계 문서, 실행 가이드, 진행상황 문서가 있습니다.

```text
scripts/
```

수동 점검이나 따라쓰기용 보조 스크립트가 있습니다.

```text
src/drawing_mapper/
```

실제 Python 코드입니다.

- `drive.py`: Google Drive 탐색/다운로드
- `inventory.py`: DWG 인벤토리 생성
- `conversion.py`: ODA 기반 DWG -> DXF 변환
- `parsers/`: DXF/PDF/SVG 파서
- `equipment.py`: 설비 후보 추출/정제
- `cli.py`: 명령어 진입점

```text
secrets/
```

Google 서비스 계정 JSON 같은 민감한 파일이 들어갑니다.
`.gitignore`에 포함되어 있어야 하며, 외부 공유하면 안 됩니다.

## Main Commands

Drive에서 DWG 동기화:

```powershell
python -m drawing_mapper.cli sync-drive --config config/project.json --verbose
```

DWG 인벤토리 생성:

```powershell
python -m drawing_mapper.cli build-inventory --config config/project.json
```

우선순위 DWG를 DXF로 변환:

```powershell
python -m drawing_mapper.cli convert-dwg --config config/project.json
```

변환된 DXF를 JSON으로 파싱:

```powershell
python -m drawing_mapper.cli parse-drawings --config config/project.json --input-dir "data/converted/dxf/04_설계도서" --output-dir "data/parsed/dxf/04_설계도서"
```

설비 후보 추출:

```powershell
python -m drawing_mapper.cli extract-equipment --config config/project.json --input-dir "data/parsed/dxf/04_설계도서" --keywords config/equipment-keywords.example.json --output-dir data/metadata
```

검수용 CSV 생성:

```powershell
python -m drawing_mapper.cli build-review --input data/metadata/facility-location-high-confidence.csv --output data/review/facility-location-review.csv
```

Drive ID prefix 제거:

```powershell
python -m drawing_mapper.cli remove-drive-id-prefixes --config config/project.json --parsed-dir data/parsed/dxf
```

임시 최종 설비 위치 테이블 생성:

```powershell
python -m drawing_mapper.cli export-final --config config/project.json --input data/metadata/facility-location-high-confidence.csv --output data/final/facility-locations.csv --calibration-output data/final/coordinate-calibration-template.csv
```

좌표 보정 적용:

```powershell
python -m drawing_mapper.cli apply-calibration --locations data/final/facility-locations.csv --calibration data/final/coordinate-calibration-template.csv --output data/final/facility-locations-calibrated.csv --report data/final/coordinate-calibration-report.json
```

## Next Steps

1. `data/final/coordinate-calibration-template.csv`에 층별 기준점 입력
2. 주소 -> GPS 변환 연결
3. `apply-calibration`으로 `facility-locations-calibrated.csv` 생성
4. 보정 결과 샘플 검증
5. 필요하면 나중에 `data/review/facility-location-review-clean.csv`로 검수 결과 반영
