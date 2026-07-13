# Location Review Guide

`data/review/facility-location-review.csv`는 설비 위치 후보를 사람이 검수하기 위한 파일입니다.

## Review Columns

- `review_status`: 검수 결과입니다. `approved`, `rejected`, `needs_check` 중 하나를 입력합니다.
- `review_note`: 판단 근거나 보정할 내용을 적습니다.
- `canonical_equipment_name`: 최종 설비명입니다. 원본 `label`이 애매하면 사람이 읽기 좋은 이름으로 정리합니다.
- `review_id`: 후보를 안정적으로 추적하기 위한 ID입니다. 직접 수정하지 않습니다.

## Suggested Review Flow

1. `confidence`가 높은 항목부터 확인합니다.
2. `floor`, `label`, `primary_source_path`를 보고 실제 설비 위치인지 판단합니다.
3. 실제 설비 위치가 맞으면 `review_status`에 `approved`를 입력합니다.
4. 도면 주석, 범례, 배관 설명문, 축척 텍스트처럼 위치가 아니면 `rejected`를 입력합니다.
5. 판단이 애매하면 `needs_check`로 두고 `review_note`에 이유를 적습니다.

## Regenerate Review CSV

```powershell
python -m drawing_mapper.cli build-review --input data/metadata/facility-location-high-confidence.csv --output data/review/facility-location-review.csv
```

