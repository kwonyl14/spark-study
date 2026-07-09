결론부터 말씀드리면, **"단순히 HTTP 요청을 보내서 띄우는 것까지는 어떻게든 성공할 수 있지만, 실제 운영 환경(Production)에서는 심각한 부작용과 관리 지옥을 초래할 확률이 매우 높다"**입니다.
Qwen이 RestTemplate을 제안한 이유는 예전 방식(CRD마다 Java POJO 클래스들을 일일이 생성하거나 플러그인으로 빌드하는 방식)만 생각했기 때문일 가능성이 큽니다. 하지만 앞서 설명해 드린 **GenericKubernetesResource (Typeless) 방식**을 사용하면 Fabric8로도 복잡한 타입 정의 없이 Map이나 YAML 구조 그대로 안전하게 제출할 수 있습니다.
RestTemplate으로 K8s API를 직접 호출할 때 발생하는 **4가지 핵심 문제점**은 다음과 같습니다.
## 1. 인증 및 토큰 갱신(Token Rotation) 구현의 지옥
Kubernetes API 서버와 통신하려면 강력한 보안 인증(mTLS 인증서 또는 ServiceAccount 토큰)을 거쳐야 합니다.
 * **Fabric8 사용할 때:** 로컬의 ~/.kube/config 파일이나, K8s 내부 Pod로 배포되었을 때의 /var/run/secrets/... 경로에 있는 인클러스터(In-Cluster) 인증서와 토큰을 **자동으로 감지하고 주기적인 토큰 만료 및 갱신(Rotation)까지 알아서 처리**해 줍니다.
 * **RestTemplate 사용할 때:** 인클러스터 토큰 파일의 스트링을 직접 읽어와서 HTTP Header에 Authorization: Bearer <토큰>으로 넣어주는 코드를 직접 짜야 합니다. 더 큰 문제는 **K8s의 ServiceAccount 토큰은 주기적으로 만료되고 갱신**된다는 점입니다. RestTemplate 세션이나 빈(Bean)이 만료된 옛날 토큰을 들고 있으면 어느 순간부터 401 Unauthorized 에러를 내며 통신이 터지게 되므로, 토큰 리프레시 로직을 직접 구현해야 합니다.
## 2. Spark Job 상태 모니터링(Watch API)의 한계
SparkApplication을 제출하고 나면 애플리케이션 프레임워크 특성상 **"이 Job이 현재 Running 인지, Failed 인지, Succeeded 인지"** 상태(status)를 주기적으로 추적해야 하는 경우가 대부분입니다.
 * K8s API는 이를 효율적으로 처리하기 위해 HTTP 연결을 끊지 않고 이벤트를 수신하는 **Watch API(WebSocket 또는 Chunked Streaming)**를 제공합니다.
 * Fabric8은 .watch() 메서드 한 줄로 이벤트를 리스닝할 수 있지만, RestTemplate은 기본적으로 단발성 단방향(Request-Response) 요청에 최적화되어 있어 K8s의 Watch 메커니즘을 구현하기가 매우 까다롭습니다. 결국 주기적으로 API를 폴링(Polling)하는 비효율적인 코드를 작성해야 합니다.
## 3. 불친절한 예외 처리 및 디버깅
SparkApplication 스펙 사양을 잘못 작성했거나(예: 메모리 표기 오류, 누락된 필드 등), 클러스터 리소스가 부족할 때 K8s API 서버는 상세한 에러 JSON 객체(Status Cause)를 반환합니다.
 * RestTemplate을 쓰면 단순히 422 Unprocessable Entity 같은 generic한 HttpClientErrorException이 발생하므로, 구체적으로 어떤 필드에서 에러가 났는지 알기 위해 내부 에러 바디 스트링을 직접 꺼내서 파싱하는 코드를 추가해야 합니다.
 * 반면 Fabric8은 KubernetesClientException 내부 구조에 K8s API 고유의 에러 메시지가 파싱되어 매핑되므로 디버깅이 훨씬 쉽습니다.
## 4. API 엔드포인트 URL 수동 관리
RestTemplate을 쓰면 아래와 같이 복잡한 K8s API URL 경로를 자바 코드에 하드코딩하거나 직접 문자열로 조합해야 합니다.
```text
https://<k8s-master-ip>/apis/sparkoperator.k8s.io/v1beta2/namespaces/{namespace}/sparkapplications

```
만약 향후 Spark Operator가 업데이트되어 API 버전이 v1beta2에서 v1으로 변경되거나, 네임스페이스 정책이 바뀌면 관련 문자열을 다 찾아다니며 수정해야 하므로 유지보수성이 급격히 떨어집니다.
> 💡 **결론 및 권장 방향**
> Qwen의 말대로 과거 방식의 구조화된 CRD 객체 매핑은 번거로운 게 맞습니다. 하지만 **Fabric8의 GenericKubernetesResource를 쓰면 타입 정의 없이 RestTemplate처럼 유연하게 Map 기반으로 요청을 날리면서도, K8s 인증/토큰 갱신/연결 관리는 안전하게 라이브러리에 위임**할 수 있습니다.
> 안정적인 데이터 파이프라인 운영을 위해 RestTemplate 구현은 지양하시고, Fabric8의 Generic 방식을 채택하시는 것을 강력히 권장합니다.
> 
