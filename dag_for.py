    for app_name in STREAMING_APPS:
        
        app_suffix = app_name.replace('-', '_')

        @task(task_id=f"check_status_{app_suffix}")
        def check_status_task(target_app: str) -> Dict[str, Any]:
            health_status = evaluate_spark_health(k8s_hook, NAMESPACE, target_app)
            print(f"[{target_app}] 분석 결과 -> {health_status['reason']}")
            return health_status

        # @task.short_circuit : 리턴값이 True일 때만 하위 Task를 실행하고, False면 스킵합니다.
        @task.short_circuit(task_id=f"reconcile_pod_{app_suffix}")
        def reconcile_task(health_status: Dict[str, Any]) -> bool:
            target_app = health_status["app_name"]
            
            if health_status["needs_cleanup"]:
                print(f"[{target_app}] 비정상 감지. 기존 자원 정리를 시작합니다.")
                
                app_list = get_k8s_spark_apps(k8s_hook, NAMESPACE)
                existing_app_names = [app["metadata"]["name"] for app in app_list if "metadata" in app]
                
                if target_app in existing_app_names:
                    delete_k8s_spark_app(k8s_hook, NAMESPACE, target_app)
                
                # 정리가 끝났으니 다음 단계(배포)로 넘어가라는 True 신호 반환
                return True
            
            print(f"[{target_app}] 스트리밍 앱이 정상 동작 중입니다. 배포 단계를 스킵합니다.")
            return False # False 반환 시 하위 배포 Task가 실행되지 않고 깔끔하게 종료됨

        @task(task_id=f"deploy_spark_{app_suffix}")
        def deploy_spark_task(target_app: str):
            print(f"[{target_app}] 새로운 SparkApplication CRD를 클러스터에 제출합니다 (Fire-and-Forget).")
            
            # YAML 제출용 파이썬 Dictionary (클래스명 등은 앱마다 다르게 동적 처리 가능)
            manifest = {
                "apiVersion": "sparkoperator.k8s.io/v1beta2",
                "kind": "SparkApplication",
                "metadata": {
                    "name": target_app,
                    "namespace": NAMESPACE
                },
                "spec": {
                    "type": "Scala",
                    "mode": "cluster",
                    "image": "com.smartbig.registry/spark-streaming:latest",
                    "imagePullPolicy": "Always",
                    # 예: oes-parsing-stream -> parsing 추출
                    "mainClass": f"com.smartbig.stream.{target_app.split('-')[1]}.MainApp", 
                    "mainApplicationFile": "local:///opt/spark/jars/streaming-app_2.12-1.0.jar",
                    "sparkVersion": "3.4.1",
                    "restartPolicy": {
                        "type": "Never" # k8s 재시작 대신 Airflow가 라이프사이클을 통제
                    },
                    "driver": {
                        "cores": 1,
                        "coreLimit": "1200m",
                        "memory": "1024m",
                        "labels": {
                            "version": "3.4.1",
                            "spark-app-name": target_app
                        },
                        "serviceAccount": "spark"
                    },
                    "executor": {
                        "cores": 2,
                        "instances": 2,
                        "memory": "2048m",
                        "labels": {
                            "version": "3.4.1",
                            "spark-app-name": target_app
                        }
                    }
                }
            }
            
            try:
                # k8s Custom Objects API를 직접 호출하여 리소스 생성 (오퍼레이터의 블로킹 현상 원천 차단)
                k8s_hook.get_custom_object_client().create_namespaced_custom_object(
                    group="sparkoperator.k8s.io",
                    version="v1beta2",
                    namespace=NAMESPACE,
                    plural="sparkapplications",
                    body=manifest
                )
                print(f"[{target_app}] k8s 제출 성공. Airflow Task를 즉시 완료 처리합니다.")
            except ApiException as e:
                print(f"[{target_app}] 제출 중 K8s API 오류 발생: {e}")
                raise

        # Task 의존성 연결 (리턴값을 명시적으로 넘겨주며 연결)
        status_res = check_status_task(app_name)
        do_deploy = reconcile_task(status_res)
        deploy_app = deploy_spark_task(app_name)
        
        # reconcile_task가 True를 뱉을 때만 deploy_spark_task가 실행됨
        do_deploy >> deploy_app





import yaml
import os
from airflow.decorators import task
from kubernetes.client import ApiException

# ... (기존 DAG 및 이전 Task 코드 동일) ...

        @task(task_id=f"deploy_spark_{app_suffix}")
        def deploy_spark_task(target_app: str):
            print(f"[{target_app}] YAML 파일을 로드하여 새로운 SparkApplication을 제출합니다.")
            
            # 1. Airflow Worker가 접근할 수 있는 경로의 YAML 파일 지정 (예: dags 폴더 내부)
            yaml_file_path = f"/opt/airflow/dags/repo/kubernetes/spark_streaming_base.yaml"
            
            # 2. YAML 파일을 읽어서 파이썬 Dictionary로 변환
            if not os.path.exists(yaml_file_path):
                raise FileNotFoundError(f"YAML 파일을 찾을 수 없습니다: {yaml_file_path}")
                
            with open(yaml_file_path, 'r') as file:
                manifest = yaml.safe_load(file)
            
            # 3. (선택 사항) 로드한 템플릿에 동적 변수 덮어쓰기 (Override)
            # 하나의 YAML로 여러 앱을 띄우기 위해 이름과 클래스 경로만 바꿔줍니다.
            manifest['metadata']['name'] = target_app
            manifest['metadata']['namespace'] = NAMESPACE
            manifest['spec']['driver']['labels']['spark-app-name'] = target_app
            manifest['spec']['executor']['labels']['spark-app-name'] = target_app
            
            # 앱 이름에 따라 실행할 Main Class 지정 (예: oes-parsing-stream -> parsing 추출)
            app_type = target_app.split('-')[1]
            manifest['spec']['mainClass'] = f"com.smartbig.stream.{app_type}.MainApp"

            # 4. K8s API로 제출 (Fire-and-Forget)
            try:
                k8s_hook.get_custom_object_client().create_namespaced_custom_object(
                    group="sparkoperator.k8s.io",
                    version="v1beta2",
                    namespace=NAMESPACE,
                    plural="sparkapplications",
                    body=manifest  # 로드/수정된 딕셔너리를 body에 그대로 전달
                )
                print(f"[{target_app}] k8s 제출 성공. Airflow Task를 즉시 완료 처리합니다.")
            except ApiException as e:
                print(f"[{target_app}] 제출 중 K8s API 오류 발생: {e}")
                raise

        # ... (이후 의존성 연결 코드 동일) ...
        do_deploy >> deploy_app
