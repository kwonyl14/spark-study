# 4가지 분석 프로세스 관제 대시보드 설계서

## 1. 주요 모니터링 지표 정의

| 카테고리 | 모니터링 항목 | 관리자 관점의 목적 |
| :--- | :--- | :--- |
| **작업 현황 (Workload)** | · 타입별 현재 진행 중인 작업 수 (`Active`)<br>· 대기 중인 작업 수 (`Queued`)<br>· 시간당 처리 완료 건수 (`Throughput`) | 현재 시스템 부하 수준과 특정 분석 타입의 병목 발생 여부 파악 |
| **성능 (Performance)** | · 분석 소요 시간 (p50, p90, p99 지연 시간)<br>· 대기 시간 (Queue Wait Time) | 알고리즘별 이상 지연 현상 및 처리 성능 감지 |
| **신뢰성 (Reliability)** | · 분석 성공/실패 비율 (`Success/Failure Rate`)<br>· 타임아웃 및 메모리 초과(OOM) 건수 | 데이터 이상이나 알고리즘 결함으로 인한 실시간 장애 감지 |
| **자원 사용 (Resource)** | · 분석 타입별 평균 CPU/메모리 사용량<br>· 처리 데이터 크기 (Input Dataset Size) | 인프라 스케일링 기준 마련 및 리소스 고갈 방지 |

---

## 2. 그라파나 대시보드 레이아웃 구조

### Row 1: 전체 시스템 요약 (Global Stat Overview)
* **Stat 패널 1:** 현재 총 진행 중인 작업 수 (`Active`)
* **Stat 패널 2:** 최근 24시간 분석 성공률 (`%`)
* **Stat 패널 3:** 시간당 총 처리량 (`Throughput`)
* **Stat 패널 4:** 최근 1시간 실패 건수 (`Failures`)

### Row 2: 4개 분석 타입별 실시간 비교 (Comparative Overview)
* **Bar Gauge 패널 (진행 중 작업 비교):** `clustering`, `regression`, `pca`, `randomforest` 4개 타입의 실시간 진행 중 작업 수 수평 막대 비교
* **Time Series 패널 (타입별 처리량 추이):** 시간 흐름에 따라 각 타입별 완료된 작업 건수 (Stacked Bar 형태)
* **Pie/Donut Chart 패널 (분석 요청 비율):** 전체 요청 중 4개 분석 타입이 차지하는 비중

### Row 3: 작업 소요 시간 및 성능 (Latency Analytics)
* **Time Series 패널 (타입별 평균 소요 시간):** 4개 타입의 평균 분석 소요 시간(초/분) 추이 비교
* **Heatmap 패널 (실행 시간 분포):** 소요 시간의 분포를 시각화하여 갑자기 오래 걸리는 이상치(Outlier) 작업 즉시 식별

### Row 4: 실패 및 이상 감지 (Failure & Error Analysis)
* **Time Series 패널 (타입별 실패 발생 추이):** 실패 발생 건수를 분석 타입별 Stacked Line으로 표시 (실패 급증 시 알람 연결)
* **Table 패널 (최근 실패 작업 로그 요약):** 실패한 작업의 타입, 발생 시각, 실패 사유 요약 표출

---

## 3. 분석 알고리즘 특성별 관제 포인트

* **PCA / Regression**
  * 연산 복잡도가 상대적으로 낮아 빠른 처리가 가능합니다.
  * **초당/분당 처리량(Throughput)** 및 **큐 대기 시간** 위주로 관제합니다.
* **Clustering / RandomForest**
  * 데이터 차원과 트리의 개수에 따라 CPU 및 메모리 소모가 급증할 수 있습니다.
  * **p99 소요 시간**, **메모리 초과(OOM) 실패율**, **자원 점유율**을 집중 관제합니다.
