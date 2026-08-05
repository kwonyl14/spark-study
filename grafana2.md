# 4가지 분석 프로세스 관제 대시보드 및 메트릭 설계서

## 1. Stat 패널 4 추천안 및 단계별 소요시간 기록 방식

### Stat 패널 4 추천: [ 최근 24시간 전체 분석 성공률 (%) ]
* **이유:** 처리량(Throughput) 대신 **시스템의 종합 건전성**을 한눈에 파악하기에 가장 좋은 지표입니다. 
* **표시 예시:** `98.5%` (95% 미만 시 경고 색상 적용)
* *(대안: 최근 24시간 전체 평균 분석 소요시간)*

### 단계별 소요시간(1~8단계) 기록 방식
* **추천 메트릭 종류:** **Histogram**
* **이유:** 단순 평균뿐만 아니라 특정 단계가 갑자기 지연되는 상위 99%(p99) 지연 시간까지 정확하게 측정할 수 있습니다.
* **기록 라벨(Label):** `type` (`clustering`, `regression`)과 `step` (`step1`, `step2` ... 또는 `1`, `2` ... `8`) 라벨을 부여하여 수집합니다.
* **가장 오래 걸리는 단계 확인 패널:** Grafana의 **Bar Chart** 또는 **Horizontal Bar Gauge** 패널을 사용하여 `step`별 평균 소요 시간을 내림차순 정렬하면 병목 단계를 즉시 식별할 수 있습니다.

---

## 2. 프로메테우스 메트릭 설계 명세서

| 메트릭 이름 | 메트릭 타입 | 라벨 (Labels) | 설명 |
| :--- | :--- | :--- | :--- |
| `analysis_jobs_active` | **Gauge** | `type` | 현재 진행 중인 분석 작업 수 (시작 시 `+1`, 종료 시 `-1`) |
| `analysis_jobs_total` | **Counter** | `type`, `status` | 종료된 분석 작업 누적 수 (`status`: `success`, `failure`) |
| `analysis_job_duration_seconds` | **Histogram** | `type` | 전체 분석 작업 1건당 소요 시간(초) |
| `analysis_job_step_duration_seconds` | **Histogram** | `type`, `step` | 각 단계(1~8단계)별 소요 시간(초) (`clustering`, `regression` 전용) |

---

## 3. 그라파나 대시보드 레이아웃 구조

### Row 1: 전체 시스템 요약 (Global Stat Overview)
* **Stat 패널 1:** 현재 총 진행 중인 작업 수 (`sum(analysis_jobs_active)`)
* **Stat 패널 2:** 최근 24시간 완료(성공)한 작업 수
* **Stat 패널 3:** 최근 24시간 실패한 작업 수
* **Stat 패널 4:** 최근 24시간 전체 분석 성공률 (`%`)

---

### Row 2: Clustering 분석 상세
* **Stat / Gauge 패널:** 현재 진행 중인 Clustering 작업 수
* **Time Series 패널:** 성공 / 실패 건수 추이 (Stacked Bar)
* **Time Series 패널:** Clustering 전체 분석 소요 시간 추이 (p50, p95, p99)
* **Bar Chart 패널 (핵심):** **1~8단계별 평균 소요 시간 비교** (어떤 단계가 병목인지 시각화)

---

### Row 3: Regression 분석 상세
* **Stat / Gauge 패널:** 현재 진행 중인 Regression 작업 수
* **Time Series 패널:** 성공 / 실패 건수 추이 (Stacked Bar)
* **Time Series 패널:** Regression 전체 분석 소요 시간 추이 (p50, p95, p99)
* **Bar Chart 패널 (핵심):** **1~8단계별 평균 소요 시간 비교** (어떤 단계가 병목인지 시각화)

---

### Row 4: PCA 분석 상세
* **Stat / Gauge 패널:** 현재 진행 중인 PCA 작업 수
* **Time Series 패널:** 성공 / 실패 건수 추이 (Stacked Bar)
* **Time Series 패널:** PCA 전체 분석 소요 시간 추이 (p50, p95, p99)

---

### Row 5: RandomForest 분석 상세
* **Stat / Gauge 패널:** 현재 진행 중인 RandomForest 작업 수
* **Time Series 패널:** 성공 / 실패 건수 추이 (Stacked Bar)
* **Time Series 패널:** RandomForest 전체 분석 소요 시간 추이 (p50, p95, p99)
