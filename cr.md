현재 코드에서 Kubernetes API Server에 CustomResourceDefinition(CRD) 객체 자체를 생성하거나 검증(validate/apply)하려고 시도하는 로직을 전부 제거해 줘. 클러스터에는 이미 Spark Operator에 의해 sparkapplications.sparkoperator.k8s.io CRD가 존재하고 있어.
스프링 애플리케이션은 CRD를 다루는 것이 아니라, 오직 SparkApplication Custom Resource(CR) 인스턴스만 특정 네임스페이스에 제출(Create/POST)하고 조회(Get/List)하는 역할만 해야 해. Fabric8 (또는 사용 중인 클라이언트) 코드를 CRD 생성 없이 CR만 제출하는 방식으로 전면 수정해 줘.
