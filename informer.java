import io.fabric8.kubernetes.api.model.GenericKubernetesResource;
import io.fabric8.kubernetes.client.KubernetesClient;
import io.fabric8.kubernetes.client.informers.ResourceEventHandler;
import io.fabric8.kubernetes.client.informers.SharedIndexInformer;
import io.fabric8.kubernetes.client.informers.SharedInformerFactory;
import io.fabric8.kubernetes.client.dsl.base.CustomResourceDefinitionContext;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

import java.util.Map;

@Component
public class SparkInformerManager implements CommandLineRunner {

    private final KubernetesClient kubernetesClient;

    public SparkInformerManager(KubernetesClient kubernetesClient) {
        this.kubernetesClient = kubernetesClient;
    }

    @Override
    public void run(String... args) {
        // 1. SparkApplication CRD Context 설정
        CustomResourceDefinitionContext crdContext = new CustomResourceDefinitionContext.Builder()
                .withGroup("sparkoperator.k8s.io")
                .withVersion("v1beta2")
                .withPlural("sparkapplications")
                .withScope("Namespaced")
                .build();

        // 2. Informer Factory 생성 및 GenericKubernetesResource용 Informer 생성
        SharedInformerFactory informerFactory = kubernetesClient.informers();
        SharedIndexInformer<GenericKubernetesResource> sparkInformer =
                informerFactory.sharedIndexInformerForCustomResource(crdContext, 30 * 1000L); // 30초 Resync

        // 3. 이벤트 핸들러 등록
        sparkInformer.addEventHandler(new ResourceEventHandler<GenericKubernetesResource>() {
            @Override
            public void onAdd(GenericKubernetesResource obj) {
                String name = obj.getMetadata().getName();
                System.out.println("[Informer] SparkApplication 생성 감지: " + name);
            }

            @Override
            public void onUpdate(GenericKubernetesResource oldObj, GenericKubernetesResource newObj) {
                String name = newObj.getMetadata().getName();
                
                // GenericKubernetesResource에서 status.applicationState.state 추출
                String currentState = extractSparkState(newObj);
                String previousState = extractSparkState(oldObj);

                if (!currentState.equals(previousState)) {
                    System.out.printf("[Informer] SparkJob [%s] 상태 변경: %s -> %s%n", 
                            name, previousState, currentState);

                    // TODO: DB 상태 업데이트 (예: COMPLETED, FAILED 처리)
                    if ("COMPLETED".equals(currentState)) {
                        System.out.println("작업 완료 로직 실행");
                    } else if ("FAILED".equals(currentState)) {
                        System.out.println("작업 실패 알림 처리");
                    }
                }
            }

            @Override
            public void onDelete(GenericKubernetesResource obj, boolean deletedFinalStateUnknown) {
                System.out.println("[Informer] SparkApplication 삭제 감지: " + obj.getMetadata().getName());
            }
        });

        // 4. 모든 인포머 백그라운드 실행 (비동기로 K8s API 감시 시작)
        informerFactory.startAllRegisteredInformers();
        System.out.println("SparkApplication Informer가 성공적으로 시작되었습니다.");
    }

    // GenericKubernetesResource Map 구조에서 Status 내의 applicationState 읽기
    private String extractSparkState(GenericKubernetesResource resource) {
        if (resource == null) return "UNKNOWN";
        
        Map<String, Object> additionalProperties = resource.getAdditionalProperties();
        if (additionalProperties.containsKey("status")) {
            Map<String, Object> status = (Map<String, Object>) additionalProperties.get("status");
            if (status != null && status.containsKey("applicationState")) {
                Map<String, Object> appState = (Map<String, Object>) status.get("applicationState");
                if (appState != null && appState.containsKey("state")) {
                    return (String) appState.get("state");
                }
            }
        }
        return "UNKNOWN";
    }
}
