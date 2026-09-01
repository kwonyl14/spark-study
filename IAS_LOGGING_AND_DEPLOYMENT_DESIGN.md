# IAS 로깅 대시보드 및 배포 체계 현황·설계

> 문서 목적  
> IAS 시스템의 현재 Kubernetes 배포·로그 수집 구조를 비플랫폼 개발자도 이해할 수 있도록 설명하고,  
> **1차 구축 범위인 Grafana + OpenSearch 기반 최소 로깅 대시보드**와  
> **향후 Jenkins / Helm / Argo CD 기반 배포 체계 고도화 방향**을 정의한다.
>
> 본 문서는 현재 확인된 사실과 향후 확인이 필요한 사항을 구분한다.  
> 확인되지 않은 플랫폼 설정, OpenSearch index/field 구조, 사내 URL 등은 임의로 가정하지 않는다.

---

## 1. 문서 범위

### 1.1 이번 구축 범위

이번 단계에서는 다음을 목표로 한다.

1. IAS 시스템 현황 정리
2. OpenSearch 로그 수집 현황 조사
3. Grafana에서 IAS 로그를 검색·필터링할 수 있는 최소 로깅 대시보드 구성
4. Job ID 기반으로 API Server 로그와 Spark/Python 분석 로그를 추적할 수 있도록 로그 규격 개선
5. Dask 로그 누락 여부 및 수집 경로 확인
6. 현재 수동 Kubernetes 배포 구조를 Helm + Argo CD 기반으로 전환하기 위한 구조 설계
7. API Server와 Spark 분석 이미지의 Jenkins CI 적용 범위 정리
8. 향후 Prometheus 지표 대시보드 고도화 방향 제시

### 1.2 이번 구축 범위에서 제외

다음은 1차 구축 완료 후 고도화 항목으로 둔다.

- Prometheus 기반 상세 성능 지표 설계
- 분석 알고리즘별 P50/P95/P99 처리 시간
- Spark Driver/Executor CPU/Memory 상세 모니터링
- 분석량(row/column/feature) 대비 처리시간 분석
- Job 단계별 State Timeline
- Alerting 정책 상세 설계

---

# 2. 시스템 개요

IAS는 API 요청을 기반으로 Spark 분석 Job을 생성하여 Kubernetes 환경에서 실행하는 시스템이다.

## 2.1 주요 처리 흐름

```text
Client
  │
  │ 1. Upload URL 요청
  ▼
IAS API Server (Spring Boot)
  │
  │ MinIO Presigned URL 반환
  ▼
Client
  │
  │ Presigned URL로 분석 파일 Upload
  ▼
MinIO
  │
  │ 2. 분석 요청
  ▼
IAS API Server
  │
  │ SparkApplication CR 생성
  ▼
Spark Operator
  │
  ▼
Spark Driver / Executor
  │
  ├─ regression.py
  ├─ clustering.py
  ├─ tttmpca.py
  └─ tttmrf.py
       │
       ├─ Python ML / Dask
       └─ Spark 처리
             │
             ▼
       Iceberg Table
```

### 2.2 Job ID

Job ID는 Client에서 생성한다.

예:

```text
regression-20260831135305-<employee-id>
```

동일 Job ID가 다음 영역에서 공통으로 사용 가능하다.

- 분석 요청 식별자
- Spark Job ID
- 파일명
- Python 분석 코드 입력값

따라서 향후 로그 추적의 **Correlation ID**로 Job ID를 사용하는 것이 적합하다.

단, 현재 Python `print` 로그에는 Job ID가 항상 포함되어 있지 않다.

또한 Job ID에 사번이 포함되므로 Grafana/OpenSearch 접근권한과 로그 노출 정책을 확인할 필요가 있다.

---

# 3. 현재 구성(AS-IS)

## 3.1 Source Repository

현재 IAS API Server와 Python 분석 코드는 **동일 Git Repository**에서 관리한다.

예상 논리 구조:

```text
ias/
├── API Server source
├── deployment yaml
├── Dockerfile(s)
└── python/
    ├── regression.py
    ├── clustering.py
    ├── tttmpca.py
    └── tttmrf.py
```

실제 repository 구조는 프로젝트 기준으로 별도 확인한다.

---

## 3.2 IAS API Server CI/CD

### 현재

Jenkins CI Pipeline은 구성되어 있다.

배포는 아직 Argo CD까지 연결되지 않았으며 수동 명령으로 수행한다.

```bash
kubectl apply -f ias-api-server-deployment.yaml
```

현재 구조:

```text
Git
 │
 ▼
Jenkins CI
 │
 ▼
Container Image
 │
 ▼
사내 Nexus Registry
 │
 │
 │  현재 자동 CD 미구성
 ▼
kubectl apply -f ias-api-server-deployment.yaml
 │
 ▼
Kubernetes
```

### 문제점

- 운영 배포가 담당자의 수동 명령에 의존
- 실제 배포 상태와 Git manifest 상태의 차이가 발생할 수 있음
- 배포 이력 및 rollback 경로가 일관되지 않을 수 있음
- 환경별 설정 관리가 복잡해질 가능성
- Argo CD가 구축되어 있지만 IAS 배포에는 아직 활용되지 않음

---

# 4. Spark/Python 분석 이미지 현황

## 4.1 현재 상태

Spark/Python 분석 이미지는 개발자가 로컬에서 Dockerfile을 직접 build하고 있다.

완성된 Jenkins CI Pipeline은 아직 없다.

이미지는 사내 Nexus Registry를 사용한다.

### 현재 Dockerfile에 포함된 것으로 파악된 항목

- Ubuntu 기반 환경
- Java 17
- Scala 2.12
- Python 3
- Spark 3.5.3
- `apt-get update`
- OS dependency 설치
- `ca-certificates`
- Miniconda installer
- Conda 환경
- Mamba
- numpy
- pandas
- 기타 Python/ML library
- Iceberg Spark Runtime JAR
- Hadoop AWS JAR
- AWS Java SDK Bundle JAR
- dependency/version 확인
- 분석 Python 파일 COPY
- ENV 설정
- 최종 `USER spark`

정확한 버전과 설치 순서는 실제 Dockerfile 리뷰가 필요하다.

---

## 4.2 Jenkins 도입 시 기본 원칙

**Jenkins 도입은 Dockerfile의 Runtime 구성 책임을 Jenkins로 옮기는 작업이 아니다.**

역할을 다음과 같이 분리한다.

### Dockerfile 책임

```text
"분석 Container가 어떤 실행 환경을 가져야 하는가"
```

예:

- Java 설치
- Spark 설치
- Python runtime
- Conda/Mamba
- Python dependency
- Iceberg/Hadoop JAR
- 분석 프로그램
- OS dependency
- 실행 사용자

### Jenkins 책임

```text
"그 Docker image를 언제, 어떤 검증 절차로 build하고 배포 가능한 artifact로 만들 것인가"
```

예:

```text
Checkout
   ↓
Dockerfile / dependency validation
   ↓
Docker Build
   ↓
Container Smoke Test
   ↓
Library / Spark Runtime Test
   ↓
Nexus Push
   ↓
Immutable Image Tag 기록
```

따라서 `numpy`, `pandas`, Spark 등을 Jenkins node에 직접 설치하여 이미지를 구성하는 방식은 권장하지 않는다.

---

# 5. Dockerfile 개선 검토 포인트

실제 Dockerfile을 기반으로 별도 상세 리뷰가 필요하다.

## 5.1 Version Pinning

다음 버전이 명시적으로 관리되는지 확인한다.

- Ubuntu/Base Image
- Java
- Scala
- Python
- Spark 3.5.3
- Miniconda
- Mamba
- numpy
- pandas
- scipy
- scikit-learn
- 기타 ML library
- Iceberg Spark Runtime
- Hadoop AWS
- AWS Java SDK Bundle

동일 Git commit을 다시 build했을 때 dependency가 임의로 바뀌지 않도록 하는 것이 목적이다.

---

## 5.2 Spark / Scala / Iceberg Compatibility

특히 다음 조합을 반드시 검증한다.

```text
Spark 3.5.3
    ↕
Scala 2.12
    ↕
Iceberg Spark Runtime Artifact
```

Iceberg runtime artifact는 Spark/Scala binary version과 관계가 있으므로 JAR 이름과 버전을 명시적으로 검증해야 한다.

Hadoop AWS와 AWS SDK Bundle 역시 사용 중인 Hadoop/Spark 환경과 compatibility를 확인한다.

---

## 5.3 Dependency 선언 분리

Dockerfile 내부에 Python package 목록을 직접 길게 작성하고 있다면 다음과 같은 분리를 검토한다.

```text
python/
├── environment.yml
├── regression.py
├── clustering.py
├── tttmpca.py
└── tttmrf.py
```

예:

```dockerfile
COPY python/environment.yml /tmp/environment.yml
RUN mamba env update -n base -f /tmp/environment.yml
```

이를 통해 dependency 변경 이력을 source와 분리해 관리할 수 있다.

실제 적용 여부는 현재 Dockerfile 검토 후 결정한다.

---

## 5.4 Docker Layer Cache

변경 빈도가 낮은 단계부터 앞쪽에 배치하고 분석 source는 뒤쪽에서 COPY하는 방향을 권장한다.

```text
Base Image
→ OS package
→ Java/Spark/Python runtime
→ Python dependency
→ External JAR
→ Analysis source COPY
```

Python source만 변경된 경우 dependency 전체를 재설치하지 않도록 한다.

---

## 5.5 Image 검증

Dockerfile 내부의 단순 version 출력이 build 검증 목적으로만 존재한다면 Jenkins의 Smoke Test Stage로 이동할 수 있다.

검증 예:

```bash
java -version
python --version
spark-submit --version

python -c "import numpy"
python -c "import pandas"
python -c "import sklearn"
```

그리고 필요한 Iceberg/Hadoop JAR이 실제 container에 존재하는지 확인한다.

중요한 것은 **버전을 출력하는 것**이 아니라 **요구 버전/라이브러리가 없을 때 Pipeline을 실패시키는 것**이다.

---

# 6. Logging 현황

## 6.1 구축 완료된 플랫폼

다음 플랫폼은 이미 Kubernetes 환경에 구축되어 있다.

- Grafana
- OpenSearch

따라서 이번 작업에서 Grafana/OpenSearch 자체를 신규 설치하는 것은 범위가 아니다.

목표는 **기존 Grafana 및 OpenSearch를 IAS에 활용하는 것**이다.

---

## 6.2 현재 OpenSearch 로그

현재 다음 로그가 OpenSearch로 유입되고 있다.

### IAS API Server

```text
Spring Boot Application Log
→ OpenSearch
```

### Spark/Python

```text
Spark Operator
→ Spark Driver/Executor
→ Python print/log
→ OpenSearch
```

Python 분석 프로그램의 로그 또한 OpenSearch에 들어가는 것을 확인했다.

### Dask

`regression.py` 내부에서 사용하는 Dask cluster 관련 로그는 일부가 OpenSearch에 유입되지 않는 것으로 보인다.

현재 정확한 원인은 확인되지 않았다.

따라서 다음을 조사해야 한다.

- Dask scheduler log
- Dask worker log
- stdout/stderr 출력 위치
- Kubernetes Pod/container 구성
- Dask worker가 별도 Pod인지 여부
- 현재 로그 수집 Agent가 어떤 Pod/container를 대상으로 하는지
- multiline 처리 여부
- 로그 collection filter/exclude 정책

---

# 7. OpenSearch 현황 조사 필요 사항

현재 확인된 사용 방식 중 하나는 다음과 같은 문자열 검색이다.

```text
AND log:*검색문자열*
```

이를 통해 `log` field에 특정 문자열을 포함하는 문서를 찾을 수 있는 것으로 보인다.

그러나 다음 정보는 아직 확인되지 않았다.

## 7.1 반드시 확인할 항목

### Index

- IAS 로그가 저장되는 OpenSearch index 이름
- index pattern
- 일자별 index인지
- Kubernetes 전체 공용 index인지
- IAS 전용 index 생성이 필요한지
- index lifecycle/retention 정책

예:

```text
확인 필요:
logs-*
kubernetes-*
ias-*
...
```

**IAS 전용 index를 반드시 새로 만들어야 한다고 현 단계에서 단정하지 않는다.**

현재 사내 로그 수집 플랫폼의 정책을 먼저 확인한다.

---

## 7.2 Mapping / Field

최소 다음 field가 존재하는지 확인한다.

```text
@timestamp
log / message
namespace
pod
pod_name
container
container_name
application
level
```

실제 field 명칭은 OpenSearch mapping 또는 기존 Grafana query를 통해 확인한다.

---

## 7.3 로그 수집 구조

다음 component를 확인한다.

```text
Kubernetes Pod
   ↓
stdout/stderr
   ↓
<로그 수집 Agent 확인 필요>
   ↓
OpenSearch
   ↓
Grafana
```

로그 수집 Agent 예시는 Fluent Bit, Fluentd, Vector 등이 있을 수 있으나 **현재 IAS 환경에서 무엇을 사용하는지는 확인 후 기록한다.**

---

# 8. 현재 Logging의 핵심 GAP

현재 가장 중요한 문제는 다음 세 가지다.

## GAP-1. Job ID가 모든 로그에 존재하지 않음

현재 Job ID는 Python까지 전달되지만 모든 `print` 로그에 포함되지는 않는다.

따라서 운영자가 다음을 하고 싶어도:

```text
Job ID = regression-20260831135305-XXXX

→ 이 Job의 API 요청
→ Spark 제출
→ Python 분석
→ 알고리즘 실행
→ Error
```

하나의 조건으로 모든 로그를 완전하게 찾을 수 없다.

### 개선

Job ID를 모든 IAS application log의 공통 correlation key로 사용한다.

---

## GAP-2. Structured Logging이 미흡함

현재 Python 코드에서 `print` 기반 로그가 사용된다.

예:

```text
Random Forest Start
```

보다 다음과 같은 구조가 더 적합하다.

```json
{
  "timestamp": "...",
  "job_id": "regression-20260831135305-XXXX",
  "analysis_type": "regression",
  "component": "spark-analysis",
  "algorithm": "random_forest",
  "event": "start",
  "level": "INFO",
  "message": "Random Forest analysis started"
}
```

다만 JSON Structured Logging 전환은 기존 사내 로그 수집 Agent가 JSON parsing을 어떻게 하는지 확인 후 적용한다.

### 1차 최소안

Structured JSON까지 즉시 적용하기 어려우면 최소한 모든 주요 Python 로그에 다음 prefix를 일관되게 넣는다.

```text
[job_id=regression-20260831135305-XXXX]
[analysis_type=regression]
[algorithm=random_forest]
```

장기적으로 structured field화를 권장한다.

---

## GAP-3. Dask 로그 일부 누락

Spark/Python 로그가 OpenSearch로 들어오더라도 별도 Dask worker/scheduler의 stdout/stderr가 동일 collection path에 포함되지 않을 수 있다.

이는 Grafana Dashboard 문제가 아니라 **수집 Pipeline 문제**일 가능성이 있다.

따라서 대시보드 구축과 병행하여 별도 조사한다.

---

# 9. Logging 표준 제안

## 9.1 공통 필드

향후 IAS application log에는 가능한 한 다음 field를 표준으로 사용한다.

| Field | 설명 | 필수 여부 |
|---|---|---|
| `timestamp` | 로그 발생 시각 | 필수 |
| `level` | INFO/WARN/ERROR | 필수 |
| `job_id` | Client에서 전달된 Job ID | 분석 관련 로그 필수 |
| `analysis_type` | regression/clustering/tttmpca/tttmrf | 분석 로그 필수 |
| `component` | api-server/spark-analysis/dask 등 | 권장 |
| `algorithm` | random_forest/lasso 등 | 알고리즘 로그 권장 |
| `event` | submit/start/end/error 등 | 권장 |
| `message` | 상세 로그 | 필수 |
| `error_code` | 업무/분석 오류 코드 | 오류 시 |
| `duration_ms` | 단계 소요시간 | 향후 고도화 |

---

## 9.2 Analysis Type

현재 분석 유형:

```text
regression
clustering
tttmpca
tttmrf
```

`regression`과 `clustering`은 약 5개의 주요 ML 단계가 존재한다.

`tttmpca`, `tttmrf`는 약 2개의 주요 단계로 구성된다.

정확한 algorithm/stage 목록은 Python source 기준으로 정리한다.

---

# 10. 1차 Grafana Logging Dashboard 설계

## 10.1 목표

1차 Dashboard의 목표는 **예쁜 시각화가 아니라 장애 발생 시 필요한 로그를 빠르게 찾는 것**이다.

따라서 다음 질문에 답할 수 있어야 한다.

- 지금 IAS에서 어떤 Error가 발생하고 있는가?
- 특정 Job ID의 로그를 한 번에 찾을 수 있는가?
- API Server와 Spark 분석 로그를 구분할 수 있는가?
- 특정 분석 유형의 로그만 볼 수 있는가?
- 특정 알고리즘의 로그만 볼 수 있는가?
- 특정 Error Code 관련 로그만 볼 수 있는가?
- 최근 Spark 분석 Job이 어떤 로그를 남겼는가?

---

## 10.2 Dashboard 이름

권장:

```text
IAS - Log Explorer
```

---

## 10.3 Dashboard Variables

가능한 경우 다음 변수를 구성한다.

```text
namespace
component
analysis_type
job_id
algorithm
level
```

단, 실제 변수 생성 가능 여부는 OpenSearch mapping과 field 존재 여부를 확인한 후 결정한다.

특히 현재 `job_id`가 structured field가 아니라 message 내부 문자열이라면 초기에는 자유 입력 검색 변수 또는 Lucene query 기반으로 구현하고, 로그 표준화 후 field 기반 변수로 전환한다.

---

# 11. Grafana Panel 구성

## Panel 1. Log Search

가장 핵심 패널.

Grafana Logs 또는 Table 형태 사용.

표시 권장 필드:

```text
timestamp
level
component
job_id
analysis_type
algorithm
message
```

현재 structured field가 부족하다면:

```text
timestamp
log
kubernetes metadata
```

수준부터 시작한다.

---

## Panel 2. ERROR/WARN Logs

최근 Error/Warning 로그만 표시한다.

검색 기준 예:

```text
level:ERROR OR level:WARN
```

실제 field가 존재하지 않으면 문자열 query를 임시 사용한다.

예:

```text
log:*ERROR*
```

단, 문자열 검색은 정확도가 떨어질 수 있으므로 장기적으로 `level` field화한다.

---

## Panel 3. Selected Job Logs

Job ID를 입력/선택하면 해당 Job 로그만 표시한다.

목표 형태:

```text
Job ID:
regression-20260831135305-XXXX

Time       Component        Algorithm       Level    Message
13:53:01   api-server                       INFO     analysis requested
13:53:02   api-server                       INFO     SparkApplication submitted
13:53:10   spark-analysis                   INFO     analysis start
13:53:15   spark-analysis   random_forest   INFO     start
...
```

현재 모든 로그에 Job ID가 포함되지 않으므로 **로그 표준화 후 완성되는 패널**이다.

---

## Panel 4. Analysis Type Logs

```text
regression
clustering
tttmpca
tttmrf
```

중 하나를 선택해 해당 분석 로그를 필터링한다.

---

## Panel 5. Error Code Logs

Oracle에 저장하는 `error_code`가 Python 로그에도 함께 출력되도록 하는 것을 권장한다.

예:

```text
error_code:E1024
```

그러면 Grafana/OpenSearch에서 동일 Error Code가 발생한 Job들의 로그를 빠르게 찾을 수 있다.

Oracle은 업무 상태 저장소로 유지하고, OpenSearch는 운영 로그 검색 용도로 활용한다.

---

# 12. 1차 Dashboard에서 하지 않을 것

현재 최소 Logging Dashboard 단계에서는 다음을 억지로 구현하지 않는다.

- 알고리즘 처리시간 Histogram
- Job State Timeline
- P95/P99 분석시간
- 성공률/실패율 Metric
- Spark Resource Dashboard
- Prometheus 기반 Alert
- row_count vs duration Scatter Plot

필요한 로그 및 field 구조가 안정화된 후 2차 고도화로 진행한다.

---

# 13. 향후 Logging Dashboard 고도화

로그 구조가 안정화되면 다음 기능을 추가할 수 있다.

## Job Detail Dashboard

```text
Job ID 선택
   ↓
API 요청
   ↓
Spark CR Submit
   ↓
Pending
   ↓
Running
   ↓
Random Forest
   ↓
Lasso
   ↓
...
   ↓
Iceberg Write
```

추후 start/end event를 구조적으로 기록하면 Grafana State Timeline 등을 이용하여 Job 실행 흐름을 시각화할 수 있다.

---

# 14. Helm 도입 목적

현재:

```bash
kubectl apply -f ias-api-server-deployment.yaml
```

방식은 manifest가 늘어날수록 관리가 어려워진다.

Helm을 통해 Kubernetes manifest를 template과 values로 분리한다.

개념:

```text
현재
ias-api-server-deployment.yaml

        ↓ Helm 적용

Chart.yaml
values.yaml
templates/
    deployment.yaml
    service.yaml
    configmap.yaml
    ...
```

Helm은 Kubernetes application의 manifest를 재사용 가능한 Chart 형태로 관리하는 도구다.

---

# 15. IAS Helm Chart 권장 구조

API Server는 장기 실행 Application이므로 Helm + Argo CD 관리 대상으로 적합하다.

권장 예:

```text
deploy/
└── helm/
    └── ias-api-server/
        ├── Chart.yaml
        ├── values.yaml
        ├── values-dev.yaml
        ├── values-prod.yaml
        └── templates/
            ├── deployment.yaml
            ├── service.yaml
            ├── configmap.yaml
            ├── serviceaccount.yaml
            └── ingress.yaml       # 필요 시
```

실제 사용하지 않는 resource는 만들지 않는다.

---

# 16. values.yaml에서 분리할 설정 예

```yaml
image:
  repository: <NEXUS_REGISTRY>/ias-api-server
  tag: "<IMAGE_TAG>"
  pullPolicy: IfNotPresent

replicaCount: 1

service:
  type: ClusterIP
  port: <PORT>

resources:
  requests:
    cpu: "<CPU_REQUEST>"
    memory: "<MEMORY_REQUEST>"
  limits:
    cpu: "<CPU_LIMIT>"
    memory: "<MEMORY_LIMIT>"

config:
  <NON_SECRET_CONFIGURATION>: "<VALUE>"
```

Secret은 일반 `values.yaml`에 평문으로 저장하지 않는다.

사내 secret 관리 정책을 확인한 뒤 Kubernetes Secret, External Secret, Vault 계열 등 기존 플랫폼 방식을 따른다.

---

# 17. SparkApplication과 Helm의 관계

현재 IAS API Server는 분석 요청 시 **동적으로 SparkApplication CR을 생성**한다.

따라서 개별 분석 Job마다 생성되는 SparkApplication CR을 Helm/Argo CD가 직접 lifecycle 관리하도록 설계하는 것은 권장하지 않는다.

권장 책임:

```text
Helm + Argo CD
    │
    └─ IAS API Server 배포/설정 관리

IAS API Server
    │
    └─ 분석 요청마다 SparkApplication CR 동적 생성

Spark Operator
    │
    └─ SparkApplication 실행/상태 관리
```

즉 Helm Chart에는 API Server가 SparkApplication을 생성하는 데 필요한 **공통 설정**은 포함할 수 있지만 런타임 Job 자체를 GitOps resource로 관리하지 않는다.

---

# 18. Argo CD 적용 목표 구조

현재:

```text
Git
 ↓
Jenkins
 ↓
Nexus
 ↓
kubectl apply
 ↓
Kubernetes
```

목표:

```text
Application Source Git
        │
        ▼
     Jenkins
   Build / Test
        │
        ▼
 Nexus Registry
        │
        │ immutable image
        ▼
Deployment Git / Helm Values
        │
        ▼
     Argo CD
        │
        ▼
    Kubernetes
```

Argo CD에서는 Helm Chart를 이용해 manifest를 rendering하고, 실제 Kubernetes application lifecycle 및 sync를 관리한다.

---

# 19. CI와 CD 책임 분리

## Jenkins - CI

권장 책임:

```text
Source Checkout
→ Compile / Unit Test
→ Docker Build
→ Container Test
→ Nexus Push
→ Image Tag 생성
```

Spark 분석 image:

```text
Source Checkout
→ Dependency Validation
→ Docker Build
→ Spark/Python Smoke Test
→ Analysis 최소 Test
→ Nexus Push
```

---

## Argo CD - CD

권장 책임:

```text
Git에 정의된 Kubernetes 원하는 상태 확인
→ Helm rendering
→ 실제 Cluster 상태와 비교
→ Sync
→ Deployment rollout
```

Jenkins에서 직접 `kubectl apply`를 수행하는 구조를 최종 목표로 하지 않는다.

---

# 20. Image Tag 전략

운영 image에는 `latest` 사용을 지양한다.

예:

```text
<NEXUS_REGISTRY>/ias-api-server:<git-sha>
<NEXUS_REGISTRY>/ias-spark-analysis:<git-sha>
```

또는:

```text
<version>-<jenkins-build-number>
```

Argo CD가 어떤 source commit/image를 배포했는지 추적 가능해야 한다.

---

# 21. API Server와 Spark 분석 Image CI 분리

두 코드는 같은 Git Repository에 있지만 build artifact 성격이 다르다.

따라서 Jenkins Pipeline 안에서 최소한 논리적으로 분리하는 것을 권장한다.

예:

```text
Repository
   │
   ├─ API Server 변경
   │      ↓
   │   API Build/Test
   │      ↓
   │   API Image Build
   │
   └─ python/ 변경
          ↓
       Analysis Test
          ↓
       Spark Analysis Image Build
```

가능하다면 path 기반 변경 감지로 불필요한 image rebuild를 줄일 수 있다.

실제 Jenkins 운영 방식과 plugin/pipeline 정책에 맞춰 적용한다.

---

# 22. 권장 Repository 구조 예시

현재 같은 repository를 유지한다는 전제에서 예시:

```text
ias/
├── api/
│   └── ...
├── python/
│   ├── regression.py
│   ├── clustering.py
│   ├── tttmpca.py
│   ├── tttmrf.py
│   └── environment.yml
│
├── docker/
│   └── spark-analysis/
│       └── Dockerfile
│
├── deploy/
│   └── helm/
│       └── ias-api-server/
│           ├── Chart.yaml
│           ├── values.yaml
│           └── templates/
│
└── Jenkinsfile
```

현재 repository 구조를 반드시 이 구조로 변경해야 한다는 의미는 아니다.

기존 layout을 확인하고 적용 가능한 수준으로 정리한다.

---

# 23. 단계별 적용 계획

## Phase 0. 현황 조사

가장 먼저 수행한다.

### OpenSearch

- [ ] IAS 로그 index/index pattern 확인
- [ ] mapping 확인
- [ ] timestamp field 확인
- [ ] message/log field 확인
- [ ] Kubernetes metadata field 확인
- [ ] retention 확인
- [ ] Grafana OpenSearch datasource 설정 확인

### Logging Pipeline

- [ ] Kubernetes 로그 수집 Agent 확인
- [ ] API Server log 경로 확인
- [ ] Spark Driver log 확인
- [ ] Spark Executor log 확인
- [ ] Dask scheduler/worker log 확인
- [ ] Dask 일부 로그 누락 원인 확인

### Deployment

- [ ] 현재 API Deployment YAML 분석
- [ ] Service/ConfigMap/Secret/ServiceAccount 확인
- [ ] Nexus image naming/tag 정책 확인
- [ ] 현재 Jenkins Pipeline 분석
- [ ] Argo CD project/repository 등록 방식 확인
- [ ] 사내 Helm 버전 및 Chart 운영 정책 확인

---

## Phase 1. Logging 최소 표준화

- [ ] Job ID를 API Server 주요 로그에 기록
- [ ] Job ID를 Python 주요 로그에 기록
- [ ] analysis_type 기록
- [ ] algorithm/stage 기록
- [ ] error_code 기록
- [ ] log level 통일
- [ ] Dask 로그 collection 가능 여부 확인

이 단계에서는 완전한 JSON Structured Logging이 어렵다면 검색 가능한 prefix 표준부터 적용할 수 있다.

---

## Phase 2. Grafana IAS Log Explorer 구축

- [ ] OpenSearch datasource/index 확인
- [ ] 기본 Log Panel 생성
- [ ] ERROR/WARN Panel 생성
- [ ] Job ID 검색
- [ ] Analysis Type 검색
- [ ] Algorithm 검색
- [ ] Error Code 검색
- [ ] Dashboard 접근권한 확인
- [ ] Dashboard JSON/Git 관리 방식 확인

---

## Phase 3. Spark Analysis Image CI

- [ ] Dockerfile 리뷰
- [ ] dependency version pinning
- [ ] Docker layer 개선
- [ ] Smoke Test 정의
- [ ] Jenkins image build
- [ ] Jenkins Nexus push
- [ ] immutable tag 적용
- [ ] 로컬 수동 build 제거

---

## Phase 4. Helm + Argo CD

- [ ] 기존 Deployment YAML Helm template 전환
- [ ] values 분리
- [ ] dev/prod 설정 분리
- [ ] `helm lint`
- [ ] `helm template` 검증
- [ ] Argo CD Application 생성
- [ ] 수동 sync 검증
- [ ] rollout/rollback 검증
- [ ] 운영 정책 확인 후 자동 sync 여부 결정
- [ ] `kubectl apply` 수동 배포 종료

---

## Phase 5. Observability 고도화

추후 요구사항으로 관리한다.

- Prometheus metrics
- Job 성공/실패율
- Pending/Running Job
- 분석 유형별 처리시간
- 알고리즘별 처리시간
- P50/P95/P99
- State Timeline
- row/feature 수와 처리시간 상관관계
- Alerting

---

# 24. 완료 기준

## Logging 1차 완료

다음 시나리오가 가능하면 1차 목표를 달성한 것으로 본다.

> 장애 문의로 특정 Job ID를 전달받았을 때  
> Grafana IAS Log Explorer에서 Job ID를 검색하여  
> API 요청 → Spark 분석 → Python 알고리즘 → 오류 로그를 확인할 수 있다.

추가로:

- 분석 유형 검색 가능
- ERROR/WARN 검색 가능
- Error Code 검색 가능
- 필요한 경우 원본 OpenSearch query 확인 가능

---

## Deployment 고도화 완료

다음 상태를 목표로 한다.

```text
개발자 Commit
  ↓
Jenkins Build/Test
  ↓
Nexus Immutable Image
  ↓
Git의 Helm Values/Deployment State
  ↓
Argo CD
  ↓
Kubernetes
```

운영 배포자가 직접 `kubectl apply`를 실행하지 않아도 배포 이력과 원하는 상태를 Git에서 추적할 수 있어야 한다.

---

# 25. 시스템 바로가기

실제 URL 확인 후 입력한다.

| 시스템 | 목적 | URL |
|---|---|---|
| Grafana | IAS Logging Dashboard | `<GRAFANA_URL>` |
| OpenSearch | 원본 로그 검색/Index 확인 | `<OPENSEARCH_URL>` |
| Jenkins | IAS CI Pipeline | `<JENKINS_URL>` |
| Argo CD | IAS Kubernetes CD | `<ARGOCD_URL>` |
| Nexus | Container Image Registry | `<NEXUS_URL>` |
| IAS Source Repository | API/Python Source | `<SOURCE_REPOSITORY_URL>` |
| Helm Chart / Deployment Repository | Kubernetes/Helm 관리 | `<HELM_CHART_REPOSITORY_URL>` |

같은 Git Repository에서 Helm까지 관리한다면 마지막 두 URL은 동일 Repository의 서로 다른 path로 표기할 수 있다.

---

# 26. 공식 문서 바로가기

아래 링크는 사내 구성과 별개로 개념/구현 검토 시 참고할 공식 문서다.

- Grafana OpenSearch Data Source  
  https://grafana.com/docs/plugins/grafana-opensearch-datasource/latest/

- Argo CD - Helm  
  https://argo-cd.readthedocs.io/en/latest/user-guide/helm/

- Argo CD - Getting Started  
  https://argo-cd.readthedocs.io/en/latest/getting_started/

- Helm Chart Best Practices  
  https://helm.sh/docs/chart_best_practices/

- Helm General Conventions  
  https://helm.sh/docs/chart_best_practices/conventions/

- Jenkins - Using Docker with Pipeline  
  https://www.jenkins.io/doc/book/pipeline/docker/

> 버전 주의  
> 사내 Grafana / OpenSearch / Helm / Argo CD / Jenkins 버전은 아직 확인되지 않았다.  
> 실제 구현 시 사내 버전을 먼저 확인하고 해당 major/minor 버전의 공식 문서를 기준으로 적용한다.

---

# 27. Dockerfile 리뷰용 사내 LLM 프롬프트

다음 프롬프트와 실제 Dockerfile을 함께 입력한다.

```text
당신은 Kubernetes, Spark, Docker, Jenkins 기반 데이터 플랫폼을 설계·운영하는 Senior Platform/Data Engineer입니다.

첨부한 Dockerfile은 Kubernetes Spark Operator가 SparkApplication을 실행할 때 사용하는 IAS 분석용 Docker image입니다.

[현재 환경]

- Kubernetes
- Spark Operator
- Spark 3.5.3
- Scala 2.12
- Java 17
- Python 기반 ML 분석
- regression.py / clustering.py / tttmpca.py / tttmrf.py
- regression.py 내부에는 Dask cluster를 사용하는 로직도 존재
- 결과는 Iceberg 테이블에 저장
- Object Storage 사용
- Iceberg/S3 접근용 JAR 사용
- API Server와 Python 분석 코드는 동일 Git Repository에서 관리
- Container Registry는 사내 Nexus
- 현재 이 Spark 분석 image는 개발자가 로컬에서 직접 docker build
- 향후 Jenkins CI를 구성하여 build/test/Nexus push를 자동화할 계획
- IAS API Server는 이미 Jenkins CI가 있으나 현재 Kubernetes 배포는 kubectl apply 방식
- 향후 Helm + Argo CD 기반 GitOps 구조로 전환 예정

[중요 원칙]

Jenkins를 도입한다고 해서 Runtime dependency 설치를 Dockerfile 밖으로 무조건 옮기지 마세요.

Dockerfile은 실행 image의 runtime을 정의하고,
Jenkins는 Docker image를 build/test/push 하는 CI 역할을 담당한다는 원칙으로 판단하세요.

Dockerfile에서 실제로 확인되지 않는 내용은 절대로 추측하지 말고
'확인 필요'라고 표시하세요.

다음 순서로 분석해주세요.

1. 현재 Dockerfile 구조 분석

Dockerfile의 명령을 위에서 아래 순서대로 분석하고 각 단계의 목적을 설명하세요.

다음을 식별하세요.

- Base image
- OS dependency
- Java
- Scala
- Python
- Spark
- Miniconda
- Mamba
- Python ML dependency
- Iceberg Spark Runtime
- Hadoop AWS
- AWS SDK Bundle
- Analysis Python source
- ENV
- USER/permission

2. 각 항목을 다음 4개로 분류하세요.

A. Dockerfile에 유지
B. Jenkins Pipeline으로 이동
C. 별도 dependency/config 파일로 분리 권장
D. 불필요하거나 제거 검토

각 판단의 근거를 설명하세요.

3. Compatibility 검토

실제 Dockerfile에서 버전을 추출하여 다음 조합을 검증하세요.

- Spark 3.5.3
- Scala 2.12
- Java 17
- Python
- Iceberg Spark Runtime
- Hadoop AWS
- AWS SDK Bundle
- numpy
- pandas
- scipy
- scikit-learn
- Dask / distributed
- 기타 Python library

Spark / Scala / Iceberg artifact의 binary compatibility를 특히 상세히 확인하세요.

근거가 불충분하면 추측하지 말고 '확인 필요'로 남기세요.

4. Reproducible Build 분석

동일 Git commit으로 나중에 다시 build해도 동일한 runtime을 만들 수 있는지 검토하세요.

- dependency version pinning
- latest 사용 여부
- Base image tag
- Miniconda installer
- Mamba/Conda dependency
- wget JAR URL
- apt dependency
- Python dependency lock 전략

5. Docker Layer/Build Cache 분석

Python source만 변경됐을 때 Java/Spark/Conda/ML dependency를 다시 설치하지 않도록
Dockerfile 명령 순서를 검토하세요.

무거운 dependency와 자주 변경되는 source code를 분리하는 개선안을 제시하세요.

6. Security 분석

- root 사용 범위
- USER spark
- file permission
- secret/credential ENV
- Nexus credential 포함 가능성
- download artifact 무결성
- 불필요 package
- image 내부 민감정보
- base image provenance

7. Dockerfile 안의 Version Check 처리

현재 Dockerfile에 Java/Python/library version을 출력하는 명령이 있다면 각각 판단하세요.

- Image build에 유지할 검증
- Jenkins Container Smoke Test로 이동할 검증
- 단순 출력이라 제거 가능한 항목

버전이 다르면 Jenkins Build가 실패하도록 검증해야 할 항목도 제안하세요.

8. 개선 Dockerfile

현재 Dockerfile을 최대한 유지하면서
필요한 부분만 수정한 개선 Dockerfile 전체를 작성하세요.

사내 Nexus URL, credential, 사내 파일 경로 등 확인할 수 없는 값은
임의로 생성하지 말고 <PLACEHOLDER>로 표시하세요.

9. Jenkins CI Pipeline 설계

최소 다음 Stage를 검토하세요.

Checkout
→ Source/Dependency Validation
→ Docker Build
→ Container Smoke Test
→ Python Dependency Test
→ Spark Runtime Test
→ Analysis Minimal Test
→ Nexus Login
→ Image Push
→ Image Tag/Build Information 기록

각 Stage에서:
- 무엇을 실행하는지
- 실패 조건은 무엇인지
- 어떤 artifact/log를 남길지

설명하세요.

10. Image Tag 전략

latest 사용 여부를 검토하고,
Git SHA 또는 Jenkins Build Number를 사용하는 immutable image tag 전략을 제안하세요.

예:
<NEXUS_REGISTRY>/ias-spark-analysis:<git-sha>

11. Dask 관점 검토

regression.py에서 Dask cluster를 사용하는 점을 고려하여 다음을 확인하세요.

- scheduler/worker 실행에 필요한 Python dependency
- worker에서 동일 Python environment가 보장되는지
- Docker image에 추가로 필요한 runtime이 있는지
- scheduler/worker stdout/stderr가 Kubernetes logging pipeline으로 수집될 수 있는 구조인지

Dockerfile만으로 판단할 수 없는 내용은 '플랫폼 구성 확인 필요'로 구분하세요.

12. 최종 출력

다음 형식으로 작성하세요.

1) 현재 구조 요약
2) 발견된 문제
3) Dockerfile 유지/이동/분리/제거 표
4) Version Compatibility 표
5) Reproducibility 문제
6) Build Cache 개선
7) Security 개선
8) 개선 Dockerfile 전체
9) Jenkins Pipeline 설계
10) Jenkinsfile 예시
11) Image Tag 전략
12) Dask 관련 확인 사항
13) 적용 순서
14) 추가 확인 필요 사항

모든 결론은 첨부 Dockerfile의 실제 내용과 위 환경정보를 근거로 작성하세요.
```

---

# 28. 구현 전 확인이 필요한 미확정 항목

현재 설계에서 의도적으로 확정하지 않은 항목이다.

| 항목 | 상태 |
|---|---|
| Grafana 정확한 버전 | 확인 필요 |
| OpenSearch 정확한 버전 | 확인 필요 |
| Grafana OpenSearch Plugin 버전 | 확인 필요 |
| OpenSearch IAS index/index pattern | 확인 필요 |
| OpenSearch mapping | 확인 필요 |
| Kubernetes 로그 수집 Agent | 확인 필요 |
| Dask 로그 누락 원인 | 확인 필요 |
| Helm 버전 | 확인 필요 |
| Argo CD 버전 | 확인 필요 |
| Jenkins 버전 | 확인 필요 |
| Spark image Dockerfile dependency 전체 버전 | Dockerfile 리뷰 필요 |
| 사내 Secret 관리 방식 | 확인 필요 |
| Argo CD Auto Sync 사용 정책 | 확인 필요 |
| Grafana Dashboard Git 관리 방식 | 확인 필요 |

---

# 29. 권장 우선순위 요약

현재 업무에서는 다음 순서가 가장 현실적이다.

```text
1. OpenSearch index / field / 로그 수집 구조 현황 확인
                 ↓
2. Job ID 중심 IAS Logging 규칙 정의
                 ↓
3. Python/API 로그에 Job ID 및 공통 필드 추가
                 ↓
4. Dask 로그 누락 조사
                 ↓
5. Grafana IAS Log Explorer 구축
                 ↓
6. Spark 분석 Dockerfile 정리
                 ↓
7. Spark Image Jenkins CI 구성
                 ↓
8. API Server Kubernetes YAML Helm 전환
                 ↓
9. Argo CD 연결
                 ↓
10. Prometheus/성능 Dashboard 고도화
```

특히 **1~5가 현재 회의에서 정한 '최소 로깅 대시보드'의 핵심 범위**다.

Helm/Argo/Jenkins 개선은 동일 문서에서 목표 Architecture로 설명하되,
Logging Dashboard 구축과 한 번에 모두 완료해야 하는 필수 선행조건으로 묶지는 않는다.
