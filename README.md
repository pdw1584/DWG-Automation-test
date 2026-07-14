# Drawing Facility Mapper

이 프로젝트는 건축/전기/통신 도면에서 설비 위치를 추출하고, 층별 좌표와 근접 보조이름을 붙여 검토용 HTML과 CSV 산출물로 내보내는 도구 모음입니다.

현재 도면에 대한 전처리 과정이 필요해 자동화를 위한 개선이 더 필요합니다.
현재 가능한 것은 XR-Plan 도면을 기준으로 같은 기준점을 가진 도면에 대한 자동화는 가능합니다.
이에 같은 기준점과 모형을 공윺하는 43개 도면에 대해 포인트를 추출했고, 포인트의 고유 이름은 도면 좌표 상 가장 가까운 텍스트를 추적해서 태깅합니다.

## 주요 산출물

- `v2/facility-locations-xr-plan-review.html`
- `v2/facility-locations-xr-plan-import.csv`
- `v2/facility-locations-xr-plan-final-deduped.csv`
- `v3/facility-locations-xr-plan-review.html`

## 디렉터리 안내

- `src/drawing_mapper/`: 추출, 정제, 좌표 보정, 내보내기 로직
- `tools/`: 산출물 갱신 스크립트
- `config/`: 프로젝트 설정과 키워드 예시
- `data/`: 원본, 변환본, 파싱 결과, 참고 데이터
- `v2/`, `v3/`: 버전별 최종 산출물과 리뷰 페이지
- `docs/`: 작업 흐름과 설계 문서

## 로컬 실행

의존성을 설치한 뒤 CLI를 실행합니다.

```powershell
python -m drawing_mapper.cli --help
```

자주 쓰는 작업은 아래와 같습니다.

```powershell
python -m drawing_mapper.cli sync-drive --config config/project.json --verbose
python -m drawing_mapper.cli build-inventory --config config/project.json
python -m drawing_mapper.cli convert-dwg --config config/project.json
python -m drawing_mapper.cli parse-drawings --config config/project.json --input-dir "data/converted/dxf/04_설계도서" --output-dir "data/parsed/dxf/04_설계도서"
python -m drawing_mapper.cli extract-equipment --config config/project.json --input-dir "data/parsed/dxf/04_설계도서" --keywords config/equipment-keywords.example.json --output-dir data/metadata
python -m drawing_mapper.cli export-final --config config/project.json --input data/metadata/facility-location-high-confidence.csv --output data/final/facility-locations.csv --calibration-output data/final/coordinate-calibration-template.csv
```



## 설정 파일

- `config/project.json`: 실제 실행용 설정
- `config/project.example.json`: 설정 예시
- `config/equipment-keywords.example.json`: 설비 키워드 예시

