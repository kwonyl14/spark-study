from datetime import datetime
from typing import Dict, Any, List
from airflow.decorators import dag, task
from airflow.providers.cncf.kubernetes.hooks.kubernetes import KubernetesHook
from airflow.providers.cncf.kubernetes.operators.spark_kubernetes import SparkKubernetesOperator
from kubernetes.client import ApiException

# ==========================================
# [Infrastructure Layer] Kubernetes API 통신 함수부
# ==========================================

def get_k8s_spark_apps(hook: KubernetesHook, namespace: str) -> List[Dict[str, Any]]:
    """KubernetesHook을 사용하여 SparkApplication CRD 인스턴스 목록을 조회합니다."""
    try:
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
    """KubernetesHook을 사용하여 특정 Spark Application에 속한 Pod 리스트를 조회합니다."""
    try:
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
    """KubernetesHook을 사용하여 특정 SparkApplication 커스텀 오브젝트를 삭제합니다."""
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
    """Pod 목록 중 driver와 executor가 모두 'Running' 상태인지 검증합니다."""
    pods = get_spark_pods(hook, namespace, target_app_name)
    
    has_driver = False
    has_executor = False
    
    for pod in pods:
        labels = pod.metadata.labels or {}
        role = labels.get("spark-role")
        pod_phase = pod.status.phase
        
        if role == "driver" and pod_phase == "Running":
            has_driver = True
        elif role == "executor" and pod_phase == "Running":
            has_executor = True

    is_healthy = has_driver and has_executor
    
    if is_healthy:
        return {
            "app_name": target_app_name,
            "is_running": True,
            "needs_cleanup": False,
            "reason": "Driver와 Executor가 모두 Running 상태입니다."
        }
    else:
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
    schedule_interval="*/5 * * * *",  # 5분마다 실행
    catchup=False,
    max_active_runs=1,
    tags=["spark", "k8s", "smartbig"]
)
def spark_streaming_recovery_dag():

    NAMESPACE = "smartbig"
    STREAMING_APPS = ["oes-parsing-stream", "oes-wafer-stream"]
    k8s_hook = KubernetesHook()

    for app_name in STREAMING_APPS:
        
        # 각 앱 구분을 위한 suffix 생성 (대시를 언더바로 변환)
        app_suffix = app_name.replace('-', '_')

        @task(task_id=f"check_status_{app_suffix}")
        def check_status_task(target_app: str) -> Dict[str, Any]:
            health_status = evaluate_spark_health(k8s_hook, NAMESPACE, target_app)
            print(f"[{target_app}] 분석 결과 -> {health_status['reason']}")
            return health_status

        @task(task_id=f"reconcile_pod_{app_suffix}")
        def reconcile_task(health_status: Dict[str, Any]):
            target_app = health_status["app_name"]
            
            if health_status["needs_cleanup"]:
                print(f"[{target_app}] 비정상 감지 또는 미실행 상태 확인. 정리 절차 착수.")
                
                # 1. 기존 오브젝트가 있다면 삭제 후 진행 (Idempotency 보장)
                app_list = get_k8s_spark_apps(k8s_hook, NAMESPACE)
                existing_app_names = [app["metadata"]["name"] for app in app_list if "metadata" in app]
                
                if target_app in existing_app_names:
                    delete_k8s_spark_app(k8s_hook, NAMESPACE, target_app)
                
                # 다음 배포 오퍼레이터가 실행되도록 True 신호 반환
                return True
            
            print(f"[{target_app}] 스트리밍 파이프라인이 정상 동작 중입니다.")
            return False

        # 2. TODO 보완: 비동기 방식으로 SparkApplication CRD를 제출하는 Operator 정의
        # 템플릿(jinja)을 쓰지 않고 파이썬 dictionary 서식을 전달하기 위해 application_file 대신 yaml_template_to_application_spec 활용 가능
        deploy_spark_app = SparkKubernetesOperator(
            task_id=f"deploy_spark_{app_suffix}",
            kubernetes_conn_id="kubernetes_default",
            namespace=NAMESPACE,
            # 스트리밍 배포의 핵심: 제출 후 완료될 때까지 기다리지 않고 바로 다음으로 넘어감
            asynchronous=True, 
            application_file=None, # 파일 경로 대신 아래 dictionary 객체를 직접 주입
            template_spec={
                "apiVersion": "sparkoperator.k8s.io/v1beta2",
                "kind": "SparkApplication",
                "metadata": {
                    "name": app_name,
                    "namespace": NAMESPACE
                },
                "spec": {
                    "type": "Scala",
                    "mode": "cluster",
                    "image": "com.smartbig.registry/spark-streaming:latest", # 실제 사용 중인 이미지로 교체 필요
                    "imagePullPolicy": "Always",
                    "mainClass": f"com.smartbig.stream.{app_suffix.split('_')[1]}.MainApp", # 예시 클래스명
                    "mainApplicationFile": "local:///opt/spark/jars/streaming-app_2.12-1.0.jar",
                    "sparkVersion": "3.4.1",
                    "restartPolicy": {
                        "type": "Never" # k8s 레벨의 재시작은 무시하고, Airflow가 관리하도록 설정
                    },
                    "driver": {
                        "cores": 1,
                        "coreLimit": "1200m",
                        "memory": "1024m",
                        "labels": {
                            "version": "3.4.1",
                            "spark-app-name": app_name
                        },
                        "serviceAccount": "spark"
                    },
                    "executor": {
                        "cores": 2,
                        "instances": 2,
                        "memory": "2048m",
                        "labels": {
                            "version": "3.4.1",
                            "spark-app-name": app_name
                        }
                    }
                }
            }
        )

        # Task 흐름 연결
        status_res = check_status_task(app_name)
        cleanup_trigger = reconcile_task(status_res)
        
        # 기동이 필요한 조건일 때만 비동기 제출 오퍼레이터를 실행하도록 흐름 제어
        cleanup_trigger >> deploy_spark_app

spark_streaming_recovery_dag()
