# IAS Kubernetes 리소스 및 운영 현황

> **목적**: IAS 시스템을 처음 접하는 개발자가 현재 Kubernetes 운영 환경, CI/배포 방식, 이미지 관리 및 로깅 현황을 빠르게 파악하기 위한 문서이다.  
> 확인되지 않은 사내 URL/플랫폼 정보는 `<PLACEHOLDER>` 또는 `확인 필요`로 표기한다.

## 1. 시스템 구성

IAS는 Spring Boot API Server가 분석 요청을 받아 Spark Operator에 `SparkApplication` CR을 제출하고, PySpark 분석 결과를 Iceberg에 적재하는 구조다.

```text
Client
 ├─ Presigned URL 요청 → IAS API Server → MinIO
 └─ 분석 요청 → IAS API Server → SparkApplication CR
                                  ↓
                            Spark Operator
                                  ↓
                         PySpark 분석 Application
                 regression / clustering / tttmpca / tttmrf
                                  ↓
                              Iceberg
```

API Server와 Python 분석 코드는 동일 Git Repository에서 관리하며 Python 코드는 `python/` 디렉터리에 있다. Client가 생성한 Job ID는 파일명, Spark Job ID 및 Python 분석 코드까지 전달된다.

## 2. Kubernetes 주요 리소스 현황

| 구분 | 리소스/구성 | 역할 | 상태 |
|---|---|---|---|
| API | IAS API Server | 분석 API 및 SparkApplication CR 제출 | 운영 중 |
| Deployment | `ias-api-server-deployment.yaml` | API Server 배포 | 수동 적용 |
| Spark | Spark Operator | SparkApplication 실행/관리 | 구축됨 |
| Spark Job | SparkApplication | PySpark 분석 Job | API Server가 동적 생성 |
| Storage | MinIO | 분석 파일 저장 및 Presigned URL | 구축됨 |
| Table | Iceberg | 분석 결과 적재 | 사용 중 |
| Registry | Nexus | Container Image 저장 | 구축됨 |
| Logging | OpenSearch | API/Spark/Python 로그 저장 | 구축됨 |
| Dashboard | Grafana | OpenSearch 로그 조회 | 구축됨 |

Spark Driver/Executor의 CPU·Memory 등 상세 리소스 모니터링은 별도 플랫폼에서 제공한다.

## 3. Jenkins CI 현황

| 항목 | 정보 |
|---|---|
| Source Repository | `<SOURCE_REPOSITORY_URL>` |
| Jenkins | `<JENKINS_URL>` |
| IAS Pipeline | `<IAS_JENKINS_PIPELINE_URL>` |
| Container Registry | `<NEXUS_URL>` |

IAS API Server는 Jenkins CI가 구성되어 있다.

```text
Git Source
   ↓
Jenkins
   ├─ Build
   ├─ Test / Pipeline에 정의된 검증
   └─ Container Image Build
              ↓
         Nexus Registry
```

정확한 Stage와 명령은 현재 `Jenkinsfile` 또는 Jenkins Pipeline 설정을 기준으로 확인한다.

반면 `python/`의 Spark/Python 분석 이미지는 아직 Jenkins CI가 구성되지 않았다. 현재 개발자가 로컬 Dockerfile로 직접 build하여 Nexus에 올리는 방식이다.

현재 분석 이미지에는 Java 17, Scala 2.12, Python 3, Spark 3.5.3, Miniconda/Mamba, Python ML 라이브러리, Iceberg Spark Runtime JAR, Hadoop AWS JAR, AWS Java SDK Bundle JAR 및 분석 Python 코드가 포함되어 있다. Dockerfile의 정확한 dependency/version과 CI 적용 범위는 별도 검토가 필요하다.

## 4. Kubernetes 배포 / Argo CD 현황

현재 IAS API Server의 Argo CD 배포는 **구성되어 있지 않다.**

현재 배포는 다음과 같이 수동으로 적용한다.

```bash
kubectl apply -f ias-api-server-deployment.yaml
```

```text
Jenkins CI
   ↓
Nexus Image
   ↓
ias-api-server-deployment.yaml
   ↓
kubectl apply
   ↓
Kubernetes
```

| 항목 | 상태 |
|---|---|
| API Server Jenkins CI | 구성됨 |
| Kubernetes 수동 배포 | 사용 중 |
| IAS Argo CD Application | 미구축 |
| Argo CD 기반 CD | 미구축 / 구축 필요 |
| Argo CD URL | `<ARGOCD_URL>` |

본 문서에서는 Argo CD 구축 방법을 설계하지 않고, 현재 미구축 상태와 향후 구축 대상이라는 점만 기록한다.

## 5. Grafana / OpenSearch 로깅 현황

Grafana와 OpenSearch는 플랫폼에 이미 구축되어 있으며, Grafana에서 OpenSearch를 Data Source로 사용하여 IAS 로그를 조회하는 대시보드가 현재 구성되어 있다.

| 로그 | 수집 현황 |
|---|---|
| IAS API Server / Spring Boot | OpenSearch 수집됨 |
| Spark 로그 | 수집됨 |
| Python `print` 로그 | 수집됨 |
| Dask Cluster 로그 | 일부 미수집으로 보임 / 확인 필요 |

현재 확인된 검색 방식 중 하나는 `log` 필드 문자열 검색이다.

```text
AND log:*검색할문자열*
```

이를 이용해 필요한 문자열을 포함한 로그를 필터링할 수 있다.

현재 추가 확인이 필요한 사항:

- IAS 로그가 저장되는 OpenSearch Index / Index Pattern
- OpenSearch Mapping 및 실제 사용 가능한 Field
- Kubernetes 로그 수집 Agent와 수집 경로
- Dask Cluster 로그 일부가 수집되지 않는 원인
- Job ID가 모든 Python `print` 로그에 포함되지는 않는 상태

현재 문서에서는 새로운 Dashboard/Metric 설계를 제안하지 않고 **현재 구축된 로깅 환경과 미확인 사항만 기록한다.**

## 6. Spark/Python 분석 이미지 현황

Spark Operator에서 사용하는 분석 이미지는 현재 개발자 로컬에서 Dockerfile로 build한다.

```text
Spark Analysis Image
├─ Ubuntu 기반 Base Image
├─ Java 17
├─ Scala 2.12
├─ Python 3
├─ Spark 3.5.3
├─ Miniconda / Mamba
├─ numpy / pandas / 기타 ML Library
├─ Iceberg Spark Runtime JAR
├─ Hadoop AWS JAR
├─ AWS Java SDK Bundle JAR
└─ regression.py / clustering.py / tttmpca.py / tttmrf.py
```

| 항목 | 상태 |
|---|---|
| Dockerfile | 존재, 일부 정리 필요 |
| Image Build | 개발자 Local Build |
| Image Registry | 사내 Nexus |
| Jenkins CI | 미구축 |
| Spark Operator 실행 | 사용 중 |

Dockerfile 자체의 개선안이나 Jenkins 전환 설계는 이 현황 문서 범위에서 제외하고 별도 검토한다.

## 7. 시스템 바로가기

실제 사내 URL 확인 후 `<PLACEHOLDER>`를 교체한다.

| 시스템 | 용도 | URL |
|---|---|---|
| Source Repository | IAS API/Python Source | `<SOURCE_REPOSITORY_URL>` |
| Jenkins | CI | `<JENKINS_URL>` |
| IAS Jenkins Pipeline | API Server CI | `<IAS_JENKINS_PIPELINE_URL>` |
| Nexus | Container Registry | `<NEXUS_URL>` |
| Argo CD | Kubernetes CD (IAS 미구축) | `<ARGOCD_URL>` |
| Grafana | Monitoring/Logging | `<GRAFANA_URL>` |
| IAS Grafana Dashboard | IAS 로그 조회 | `<IAS_GRAFANA_DASHBOARD_URL>` |
| OpenSearch | 로그 저장/검색 | `<OPENSEARCH_URL>` |

## 8. 미구축 / 추가 확인 항목

| 항목 | 상태 |
|---|---|
| IAS API Server Jenkins CI | 구성됨 |
| IAS API Server Kubernetes 배포 | `kubectl apply` 수동 적용 |
| IAS Argo CD Application/CD | 미구축 |
| Spark/Python Image Jenkins CI | 미구축 |
| Spark/Python Image Build | Local Docker Build |
| Grafana + OpenSearch Logging | 구성됨 |
| OpenSearch IAS Index/Mapping | 확인 필요 |
| Dask 로그 수집 | 일부 누락 추정 / 확인 필요 |
| Job ID 로그 일관성 | 모든 Python 로그에는 포함되지 않음 |
| Grafana/OpenSearch/Argo/Jenkins 정확한 버전 | 확인 필요 |
