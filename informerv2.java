@Override
public void run(String... args) {
    this.sparkInformer = kubernetesClient
            .genericKubernetesResources("sparkoperator.k8s.io/v1beta2", "SparkApplication")
            .inAnyNamespace()
            // ★ 지정한 라벨이 있는 SparkApplication 이벤트만 필터링하여 감시
            .withLabel("app.kubernetes.io/managed-by", "ias-spring-server")
            .inform(new ResourceEventHandler<GenericKubernetesResource>() {

                @Override
                public void onAdd(GenericKubernetesResource obj) {
                    String jobName = obj.getMetadata().getName();
                    System.out.println("[Informer] ias 작업 감지 및 등록: " + jobName);
                }

                @Override
                public void onUpdate(GenericKubernetesResource oldObj, GenericKubernetesResource newObj) {
                    String jobName = newObj.getMetadata().getName();
                    String newState = extractState(newObj);
                    String oldState = extractState(oldObj);

                    if (!newState.equals(oldState)) {
                        // ★ DB 업데이트 수행
                        // sparkJobRepository.updateStatus(jobName, newState);
                        System.out.printf("[DB Sync] 작업[%s] 상태 변경: %s -> %s%n", jobName, oldState, newState);
                    }
                }

                @Override
                public void onDelete(GenericKubernetesResource obj, boolean deletedFinalStateUnknown) {
                    String jobName = obj.getMetadata().getName();
                    // 삭제 시 DB 상태 변경 또는 소프트 딜리트 처리
                }
            });
}
