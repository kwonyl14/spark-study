from datetime import datetime
from typing import Dict, Any, List
from airflow.decorators import dag, task
from airflow.providers.cncf.kubernetes.hooks.kubernetes import KubernetesHook
from kubernetes.client import ApiException

# ==========================================
# [Infrastructure Layer] Kubernetes API 통신 함수부
# ==========================================

def get_k8s_spark_apps(hook: KubernetesHook, namespace: str) -> List[Dict[str, Any]]:
    """
    KubernetesHook을 사용하여 SparkApplication CRD 인스턴스 목록을 조회합니다.
    """
    try:
        # sparkoperator.k8s.io/v1beta2 Custom Resource Definition 표준 API 엔드포인트 사용
        response = hook.get_custom_object_client().list_namespaced_custom_object(
            group="sparkoperator.k8s.io",
            version="v1beta2",
            namespace=namespace,
            plural="sparkapplications"
        )
        return response.get("items", [])
    except ApiException as e:
        print(f"[{namespace}] SparkApplication 리스트 조회 실패: {e}")
        return []

def get_spark_pods(hook: KubernetesHook, namespace: str, app_name: str) -> List[Any]:
    """
    KubernetesHook을 사용하여 특정 Spark Application에 속한 Pod 리스트를 조회합니다.
    """
    try:
        # spark-role(driver/executor) 및 spark-app-selector 라벨을 활용한 필터링
        label_selector = f"spark-app-name={app_name}"
        pod_list = hook.core_v1_client.list_namespaced_pod(
            namespace=namespace,
            label_selector=label_selector
        )
        return pod_list.items
    except ApiException as e:
        print(f"[{namespace}] {app_name}의 Pod 리스트 조회 실패: {e}")
        return []

def delete_k8s_spark_app(hook: KubernetesHook, namespace: str, app_name: str) -> None:
    """
    KubernetesHook을 사용하여 특정 SparkApplication 커스텀 오브젝트를 삭제합니다.
    """
    try:
        hook.get_custom_object_client().delete_namespaced_custom_object(
            group="sparkoperator.k8s.io",
            version="v1beta2",
            namespace=namespace,
            plural="sparkapplications",
            name=app_name
        )
        print(f"[{namespace}] SparkApplication '{app_name}' 삭제 요청 성공.")
    except ApiException as e:
        if e.status == 404:
            print(f"[{namespace}] '{app_name}' 오브젝트가 클러스터에 이미 존재하지 않습니다.")
        else:
            print(f"[{namespace}] '{app_name}' 삭제 중 오류 발생: {e}")


# ==========================================
# [Business Logic Layer] 스트리밍 애플리케이션 상태 판별
# ==========================================

def evaluate_spark_health(hook: KubernetesHook, namespace: str, target_app_name: str) -> Dict[str, Any]:
    """
    정해진 비즈니스 규칙에 따라 Spark Application의 헬스를 판단합니다.
    규칙: 
      - Pod 목록 중 'driver' 역할을 하는 Pod와 'executor' 역할을 하는 Pod가 동시에 'Running' 상태여야 함.
      - 하나라도 없거나 비정상이면 재시작 대상(needs_cleanup=True)으로 판단.
    """
    pods = get_spark_pods(hook, namespace, target_app_name)
    
    has_driver = False
    has_executor = False
    
    for pod in pods:
        # SparkOperator가 생성하는 Pod의 핵심 라벨 및 상태 확인
        labels = pod.metadata.labels or {}
        role = labels.get("spark-role")
        pod_phase = pod.status.phase  # 'Running', 'Pending', 'Failed', 'Success' 등
        
        if role == "driver" and pod_phase == "Running":
            has_driver = True
        elif role == "executor" and pod_phase == "Running":
            has_executor = True

    # Driver와 Executor가 모두 최소 1개 이상 Running 상태인지 검증
    is_healthy = has_driver and has_executor
    
    if is_healthy:
        return {
            "app_name": target_app_name,
            "is_running": True,
            "needs_cleanup": False,
            "reason": "Driver와 Executor가 모두 Running 상태입니다."
        }
    else:
        # 둘 중 하나라도 만족하지 못하는 경우 복구 절차 필요
        reason_msg = f"조건 미충족 (Driver Running: {has_driver}, Executor Running: {has_executor})"
        return {
            "app_name": target_app_name,
            "is_running": False,
            "needs_cleanup": True,
            "reason": reason_msg
        }


# ==========================================
# [Airflow DAG Layer] DAG 및 테스크 흐름 정의
# ==========================================

@dag(
    dag_id="spark_streaming_k8s_recovery_manager",
    start_date=datetime(2026, 1, 1),
    schedule_interval="*/5 * * * *",  # 5분마다 헬스체크 및 동적 복구 수행
    catchup=False,
    max_active_runs=1,
    tags=["spark", "k8s", "smartbig"]
)
def spark_streaming_recovery_dag():

    NAMESPACE = "smartbig"
    STREAMING_APPS = ["oes-parsing-stream", "oes-wafer-stream"]
    
    # 기본 구성된 kubernetes connection 사용 (필요시 conn_id 지정 가능)
    k8s_hook = KubernetesHook()

    for app_name in STREAMING_APPS:
        
        @task(task_id=f"check_status_{app_name.replace('-', '_')}")
        def check_status_task(target_app: str) -> Dict[str, Any]:
            health_status = evaluate_spark_health(k8s_hook, NAMESPACE, target_app)
            print(f"[{target_app}] 분석 결과 -> {health_status['reason']}")
            return health_status

        @task(task_id=f"reconcile_pod_{app_name.replace('-', '_')}")
        def reconcile_task(health_status: Dict[str, Any]):
            target_app = health_status["app_name"]
            
            # 파드가 정상 조건을 충족하지 못해 클린업이 필요한 경우
            if health_status["needs_cleanup"]:
                print(f"[{target_app}] 비정상 감지로 인한 정리 절차 착수. 사유: {health_status['reason']}")
                
                # 1. k8s 클러스터에 실제로 SparkApplication CRD 오브젝트가 존재하는지 확인
                app_list = get_k8s_spark_apps(k8s_hook, NAMESPACE)
                existing_app_names = [app["metadata"]["name"] for app in app_list if "metadata" in app]
                
                if target_app in existing_app_names:
                    print(f"[{target_app}] 클러스터 내에 SparkApplication 오브젝트가 존재함을 확인했습니다. 삭제를 시작합니다.")
                    # 2. 존재한다면 안전하게 삭제 진행
                    delete_k8s_spark_app(k8s_hook, NAMESPACE, target_app)
                else:
                    print(f"[{target_app}] 클러스터 내에 이미 SparkApplication 오브젝트가 없습니다. 삭제 단계를 건너뜁니다.")
                
                # 3. 새로운 스파크 애플리케이션 재포드 트리거 로직 배치 위치
                print(f"[{target_app}] 새로운 인스턴스를 정상화하기 위한 재배포 파이프라인을 준비합니다.")
                # TODO: 여기에 신규 SparkApplication 배포 명령어(오퍼레이터 호출 등) 추가
                
            else:
                print(f"[{target_app}] 스트리밍 파이프라인이 정상적으로 동작 중입니다.")

        # Task 흐름 연결
        status_res = check_status_task(app_name)
        reconcile_task(status_res)

spark_streaming_recovery_dag()
