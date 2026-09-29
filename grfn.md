# IAS Grafana 대시보드 표준화 설계안

## 1. 목적

IAS 대시보드의 조회 기준을 표준화하고, WAS / Analyzer / 분석 작업 / Pod 단위로 상태를 빠르게 확인할 수 있도록 구성한다.

## 2. 대상 아키텍처

IAS는 WAS에서 요청을 받은 뒤 Redis를 통해 분석 요청 상태를 관리하고, Python Analyzer는 Kubernetes Deployment 형태로 운영한다.

KEDA는 Redis 상태를 기준으로 Analyzer Pod 수를 조정하며, 기본 1개부터 최대 4개까지 확장한다.

```text
WAS
 ↓
Redis
 ↓
Python Analyzer Deployment
 ├─ Pod
 ├─ Pod
 ├─ Pod
 └─ Pod
      ↑
     KEDA
```

## 3. 대시보드 조회 기준

상단 Variable은 다음 기준으로 구성한다.

```text
Component    [ All | WAS | Analyzer ]
AnalysisType [ All | ... ]
Pod          [ All | ... ]
```

- `component`: 애플리케이션 역할 구분
- `analysis_type`: 분석 종류 구분
- `pod`: 개별 인스턴스 확인

## 4. 표준 라벨

공통 Metric Label은 아래와 같이 구성한다.

```text
app=ias
component=was | analyzer
analysis_type=<분석종류>
```

Kubernetes에서 수집되는 다음 정보도 함께 활용한다.

```text
namespace
deployment
pod
container
```

`pod`는 특정 인스턴스의 CPU, Memory, Restart, Error 등을 확인할 때 사용한다.

## 5. Job ID 관리

`job_id`는 개별 분석 작업 추적에 사용한다.

Metric Label에는 포함하지 않고 WAS와 Analyzer 로그에 동일한 `job_id`를 기록한다.

```json
{
  "app": "ias",
  "component": "analyzer",
  "analysis_type": "regression",
  "job_id": "regression-20260929090100-12345",
  "level": "INFO",
  "message": "analysis started"
}
```

로그는 OpenSearch에 저장하고 `job_id` 기준으로 검색한다.

```text
WAS
job_id=X
 ↓
Redis
job_id=X
 ↓
Analyzer
job_id=X
```

이를 통해 특정 Job의 요청 수신부터 분석 시작, 처리 결과, 오류까지 동일한 Job ID로 조회한다.

## 6. Analyzer 모니터링

Analyzer 상태는 다음 지표를 확인한다.

```text
Total Analyzer
Busy Analyzer
Idle Analyzer

Current Replica
Desired Replica
Max Replica
```

Worker 상태는 별도 Metric으로 관리한다.

```text
ias_analyzer_workers{state="busy"} 2
ias_analyzer_workers{state="idle"} 1
```

현재 분석 중인 Worker와 즉시 요청을 받을 수 있는 Worker 수를 확인할 수 있다.

## 7. Redis 및 분석 처리 상태

Redis 기반 요청 처리 상태는 다음 항목을 확인한다.

```text
Pending Jobs
Running Jobs
Success Jobs
Failed Jobs
```

처리 시간은 다음 기준으로 확인한다.

```text
Queue Wait Time
Analysis Processing Time
Total Processing Time
```

이를 통해 요청 적체 여부와 Analyzer 처리 성능을 확인한다.

## 8. KEDA 상태

KEDA Scale-out 상태는 다음 항목을 확인한다.

```text
Current Replica
Desired Replica
Max Replica
```

예:

```text
Current Replica : 2
Desired Replica : 3
Max Replica     : 4
```

- `Current Replica`: 현재 실행 중인 Analyzer Pod 수
- `Desired Replica`: 현재 상태를 기준으로 필요한 Pod 수
- `Max Replica`: 최대로 확장 가능한 Pod 수

## 9. 대시보드 구성

```text
-------------------------------------------------
Component [All] | AnalysisType [All] | Pod [All]
-------------------------------------------------

[ Job Status ]
Pending | Running | Success | Failed

[ Analyzer ]
Total | Busy | Idle

[ KEDA ]
Current Replica | Desired Replica | Max Replica

[ Performance ]
Queue Wait Time
Analysis Processing Time
Total Processing Time

[ Resource ]
CPU
Memory
Pod Restart

[ Error ]
WAS Error
Analyzer Error
Failed Analysis
```

## 10. 조회 기준 정리

```text
서비스 역할
→ component

분석 종류
→ analysis_type

인스턴스 확인
→ pod

개별 작업 추적
→ job_id / OpenSearch
```

Metric은 전체 서비스 상태와 추이를 확인하는 데 사용하고, 개별 Job의 상세 내용은 OpenSearch에서 `job_id` 기준으로 조회한다.
