# XREF Analysis

## Purpose

DXF 도면에서 어떤 외부참조(XREF)를 사용하고 있는지 확인하여, 설비 좌표를 공통 평면 기준으로 정리할 수 있는지 판단하기 위한 분석이다.

## Generated Files

```text
data/metadata/xref-inventory.csv
data/metadata/xref-inventory.json
data/metadata/xref-summary.csv
data/metadata/xref-summary.json
data/metadata/xref-plan-candidates.csv
data/metadata/xref-plan-candidates.json
```

## Current Result

전체 `04_설계도서` DXF를 대상으로 XREF를 추출했다.

```text
XREF inventory rows: 15,716
PLAN/SITE candidate rows: 1,579
Identity inserts: 592
Failed drawings: 0
```

주요 PLAN/SITE 계열 참조:

```text
S100-03.구조평면도: 158
100-01. 평면도(확대 평면도): 128
X-1F-PLAN: 116
X-2F-PLAN: 115
X-2MF-PLAN: 65
X-SITE: 64
XR-PLAN: 56
XS-1F-PLAN: 56
X-6F-PLAN: 50
```

`XR-PLAN`은 56건 발견되었고, 이 중 36건은 아래 조건을 만족했다.

```text
insert_x = 0
insert_y = 0
xscale = 1
yscale = 1
rotation = 0
```

따라서 해당 도면들은 설비 도면의 `drawing_x`, `drawing_y`가 `XR-PLAN` 기준 좌표와 거의 같은 좌표계일 가능성이 높다.

## Interpretation

`XR-PLAN`은 전기/통신 평면도에서 공통 건축 평면 기준 역할을 하고 있는 것으로 보인다.

`A-101~109` 전체평면도는 `X-1F-PLAN`, `X-SITE` 등을 직접 참조하고, 다른 설비 도면은 이를 합친 `XR-PLAN`을 참조하는 구조로 추정된다.

따라서 좌표 보정은 모든 설비 도면마다 개별 기준점을 잡기보다, 아래 순서로 접근하는 것이 좋다.

1. `XR-PLAN` 또는 층별 `X-?F-PLAN`을 공통 기준 도면으로 선정
2. `XR-PLAN`이 identity insert로 들어간 설비 도면을 우선 좌표 보정 대상에 포함
3. `insert_x`, `insert_y`, `scale`, `rotation`이 다른 도면은 별도 변환 적용
4. 최종 GPS 보정은 `X-SITE` 또는 건축 배치도를 기준으로 수행

## Next Step

`data/metadata/xref-plan-candidates.csv`에서 `XR-PLAN`, `X-SITE`, `X-1F-PLAN` 계열을 우선 검토한다.

이후 기준점은 `XR-PLAN` 또는 `X-SITE` 위에서 잡고, 설비 좌표는 XREF 삽입 변환값을 통해 공통 좌표계로 옮기는 방식으로 확장한다.
