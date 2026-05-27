import os
from airflow.decorators import task

# ... 기존 DAG 코드 생략 ...

        @task(task_id=f"deploy_spark_{app_suffix}")
        def deploy_spark_task(target_app: str):
            # -------------------------------------------------------------
            # [디버깅 구간] 현 위치와 파일 목록을 Airflow 로그에 출력
            # -------------------------------------------------------------
            print("================ [디버깅 시작] ================")
            print(f"1. 현재 작업 디렉토리(CWD): {os.getcwd()}")
            
            # 현재 이 DAG 파일이 실행되고 있는 실제 절대 경로
            current_dag_dir = os.path.dirname(os.path.abspath(__file__))
            print(f"2. 현재 DAG 파일의 위치: {current_dag_dir}")
            
            try:
                print(f"3. 현재 DAG 폴더 내부의 파일 목록: {os.listdir(current_dag_dir)}")
            except Exception as e:
                print(f"DAG 폴더 목록 조회 실패: {e}")
                
            try:
                # 상위 폴더나 루트 폴더 등 의심되는 곳도 찍어볼 수 있습니다.
                print(f"4. 현재 작업 디렉토리(CWD) 기준 파일 목록: {os.listdir('.')}")
            except Exception as e:
                print(f"CWD 목록 조회 실패: {e}")
            print("================ [디버깅 끝] ================")
            
            # -------------------------------------------------------------
            # 원래 YAML 로드 및 제출 로직
            # -------------------------------------------------------------
            # (위 디버깅 로그를 보고 출력된 절대 경로를 조합해서 아래 경로를 수정하면 됩니다!)
            yaml_file_path = f"{current_dag_dir}/kubernetes/spark_streaming_base.yaml" 
            
            with open(yaml_file_path, 'r') as file:
                manifest = yaml.safe_load(file)
            
            # ... 후속 K8s Hook 제출 코드 ...
