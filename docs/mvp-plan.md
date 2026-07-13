# MVP Plan

## Phase 1: Collect

- Google Cloud project 생성
- Drive API enable
- OAuth client or service account 구성
- 특정 Drive folder ID 기준 파일 목록 조회
- PDF/SVG 파일 다운로드

Deliverable:

- `POST /drive/sync`
- raw file storage
- file metadata table

## Phase 2: Parse

- PDF text, vector, page size 추출
- SVG element, path, text 추출
- DXF modelspace text, layer, entity 후보 추출
- DWG는 변환 필요 상태로 인벤토리 기록
- 도면별 중간 JSON 저장

Deliverable:

- `POST /drawings/{id}/parse`
- `parsed/*.json`

## Phase 3: Floor Mapping

- 파일명, 페이지 텍스트, 도면 제목란에서 층 추론
- 1~6층 매핑
- 사람이 수정 가능한 구조 유지

Deliverable:

- Floor table
- page-to-floor mapping

## Phase 4: Equipment Candidates

- 설비 키워드 사전 작성
- 텍스트 라벨 주변 bounding box 추출
- 후보 설비 좌표 저장

Deliverable:

- EquipmentCandidate table
- confidence score

## Phase 5: Address and Coordinates

- 주소 geocoding
- 도면 기준점 입력
- 도면 좌표를 실제 좌표로 변환

Deliverable:

- building latitude/longitude
- floor calibration
- equipment location query

## Phase 6: Review UI

- 층별 도면 보기
- 설비 후보 표시
- 사람이 설비 위치 확정/수정

Deliverable:

- dashboard
- verified equipment location
