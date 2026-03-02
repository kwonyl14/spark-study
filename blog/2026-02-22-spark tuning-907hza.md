---
slug: 주요 성능 최적화 요소
title: "주요 성능 최적화 요소"
authors: [907hza]
tags: [spark, scala]
---
# 주요 성능 최적화 요소

- **실행 방법**
    
    ```scala
    // --- [준비] Spark의 자동 최적화 기능 끄기 ---
    ./spark-shell --driver-memory 1g --executor-memory 1g \
    --conf "spark.serializer=org.apache.spark.serializer.KryoSerializer" \
    --conf "spark.kryo.registrationRequired=false" \
    --conf "spark.kryo.classesToRegister=org.apache.spark.sql.execution.columnar.DefaultCachedBatch,org.apache.spark.sql.catalyst.expressions.GenericInternalRow" \
    --conf "spark.memory.offHeap.enabled=true" \
    --conf "spark.memory.offHeap.size=512m" \
    --conf "spark.sql.adaptive.enabled=false" \
    --conf "spark.sql.autoBroadcastJoinThreshold=-1"
    ```
    

1. **Partitioning vs Repartition 성능 비교 (초기 설정 vs 재설정)**
    
    데이터를 처음부터 원하는 개수로 만드는 것과, 나중에 repartition() 을 호출하여 강제로 셔플을 일으키는 것의 차이
    
    ```scala
    val numData = 20000000
    val targetPartitions = 100
    
    // [Case A] 최적의 초기 파티셔닝 (Initial Partitioning)
    // 데이터를 생성할 때부터 100개로 나누어 저장함. 셔플 없음.
    val t1 = System.currentTimeMillis()
    val initialPartitioned = spark.range(0, numData, 1, targetPartitions)
    initialPartitioned.count()
    println(s">> Initial Partitioning Time: ${System.currentTimeMillis() - t1}ms")
    ```
    
    ![스크린샷 2026-03-02 오후 2.28.02.png](%EC%A3%BC%EC%9A%94%20%EC%84%B1%EB%8A%A5%20%EC%B5%9C%EC%A0%81%ED%99%94%20%EC%9A%94%EC%86%8C/%E1%84%89%E1%85%B3%E1%84%8F%E1%85%B3%E1%84%85%E1%85%B5%E1%86%AB%E1%84%89%E1%85%A3%E1%86%BA_2026-03-02_%E1%84%8B%E1%85%A9%E1%84%92%E1%85%AE_2.28.02.png)
    
    ![스크린샷 2026-03-02 오후 2.25.58.png](%EC%A3%BC%EC%9A%94%20%EC%84%B1%EB%8A%A5%20%EC%B5%9C%EC%A0%81%ED%99%94%20%EC%9A%94%EC%86%8C/%E1%84%89%E1%85%B3%E1%84%8F%E1%85%B3%E1%84%85%E1%85%B5%E1%86%AB%E1%84%89%E1%85%A3%E1%86%BA_2026-03-02_%E1%84%8B%E1%85%A9%E1%84%92%E1%85%AE_2.25.58.png)
    
    ```scala
    // [Case B] 나중에 다시 나누기 (Repartitioning)
    // 1개로 생성된 데이터를 강제로 100개로 쪼개기 위해 '전체 셔플' 발생.
    val t2 = System.currentTimeMillis()
    val repartitioned = spark.range(0, numData, 1, 1).repartition(targetPartitions)
    repartitioned.count()
    println(s">> Repartitioning Time: ${System.currentTimeMillis() - t2}ms")
    ```
    
    ![스크린샷 2026-03-02 오후 2.28.21.png](%EC%A3%BC%EC%9A%94%20%EC%84%B1%EB%8A%A5%20%EC%B5%9C%EC%A0%81%ED%99%94%20%EC%9A%94%EC%86%8C/%E1%84%89%E1%85%B3%E1%84%8F%E1%85%B3%E1%84%85%E1%85%B5%E1%86%AB%E1%84%89%E1%85%A3%E1%86%BA_2026-03-02_%E1%84%8B%E1%85%A9%E1%84%92%E1%85%AE_2.28.21.png)
    
    ![스크린샷 2026-03-02 오후 2.27.02.png](%EC%A3%BC%EC%9A%94%20%EC%84%B1%EB%8A%A5%20%EC%B5%9C%EC%A0%81%ED%99%94%20%EC%9A%94%EC%86%8C/%E1%84%89%E1%85%B3%E1%84%8F%E1%85%B3%E1%84%85%E1%85%B5%E1%86%AB%E1%84%89%E1%85%A3%E1%86%BA_2026-03-02_%E1%84%8B%E1%85%A9%E1%84%92%E1%85%AE_2.27.02.png)
    
    - repartition 은 모든 데이터를 네트워크로 다시 뿌리는 **Exchange(Full Shuffle)** 을 일으켜서 속도에 차이가 큽니다.

1. **Predicate Pushdown 적용 전·후 비교**
    
    필터를 엔진 레벨에서 미리 처리하는 것의 속도 차이
    
    ```scala
    // 테스트용 데이터 생성
    spark.range(1, 10000000).selectExpr("id", "id % 10 as key").write.mode("overwrite").parquet("/tmp/pushdown_test")
    
    // [Before] Pushdown 미적용 (필터 기능을 강제로 끄기)
    spark.conf.set("spark.sql.parquet.filterPushdown", "false")
    val t1 = System.currentTimeMillis()
    spark.read.parquet("/tmp/pushdown_test").filter("key = 5").count()
    println(s"Pushdown 미적용 시간: ${System.currentTimeMillis() - t1}ms")
    ```
    
    ![스크린샷 2026-03-02 오후 2.33.43.png](%EC%A3%BC%EC%9A%94%20%EC%84%B1%EB%8A%A5%20%EC%B5%9C%EC%A0%81%ED%99%94%20%EC%9A%94%EC%86%8C/%E1%84%89%E1%85%B3%E1%84%8F%E1%85%B3%E1%84%85%E1%85%B5%E1%86%AB%E1%84%89%E1%85%A3%E1%86%BA_2026-03-02_%E1%84%8B%E1%85%A9%E1%84%92%E1%85%AE_2.33.43.png)
    
    ```scala
    // [After] Pushdown 적용 (기본값)
    spark.conf.set("spark.sql.parquet.filterPushdown", "true")
    val t2 = System.currentTimeMillis()
    val pushedDF = spark.read.parquet("/tmp/pushdown_test").filter("key = 5")
    pushedDF.count()
    println(s"Pushdown 적용 시간: ${System.currentTimeMillis() - t2}ms")
    ```
    
    ![스크린샷 2026-03-02 오후 2.34.25.png](%EC%A3%BC%EC%9A%94%20%EC%84%B1%EB%8A%A5%20%EC%B5%9C%EC%A0%81%ED%99%94%20%EC%9A%94%EC%86%8C/%E1%84%89%E1%85%B3%E1%84%8F%E1%85%B3%E1%84%85%E1%85%B5%E1%86%AB%E1%84%89%E1%85%A3%E1%86%BA_2026-03-02_%E1%84%8B%E1%85%A9%E1%84%92%E1%85%AE_2.34.25.png)
    
    ![스크린샷 2026-03-02 오후 2.34.58.png](%EC%A3%BC%EC%9A%94%20%EC%84%B1%EB%8A%A5%20%EC%B5%9C%EC%A0%81%ED%99%94%20%EC%9A%94%EC%86%8C/%E1%84%89%E1%85%B3%E1%84%8F%E1%85%B3%E1%84%85%E1%85%B5%E1%86%AB%E1%84%89%E1%85%A3%E1%86%BA_2026-03-02_%E1%84%8B%E1%85%A9%E1%84%92%E1%85%AE_2.34.58.png)
    
    - 실행 계획의 FileScan 부분에 **PushedFilters: [EqualTo(key,5)]가 표시**됩니다. 이는 스파크가 데이터를 메모리로 다 읽어오기 전에, 파일 엔진 수준에서 90%의 데이터를 미리 걸러내어 I/O 시간을 획기적으로 줄였음을 보여줍니다.

1. **Off-heap Memory 사용 시 GC 영향 분석**
    
    JVM 힙 외부 메모리를 사용했을 때의 GC 부하 차이
    
    ```scala
    // --conf "spark.memory.offHeap.enabled=true" 설정으로 시작해야 함
    val hugeData = spark.range(1, 10000000).map(i => (i, "payload" * 10)).toDF("id", "val")
    
    // [Before] On-heap 캐싱 (GC 대상)
    hugeData.persist(org.apache.spark.storage.StorageLevel.MEMORY_ONLY)
    hugeData.count()
    ```
    
    ![스크린샷 2026-03-02 오후 2.47.14.png](%EC%A3%BC%EC%9A%94%20%EC%84%B1%EB%8A%A5%20%EC%B5%9C%EC%A0%81%ED%99%94%20%EC%9A%94%EC%86%8C/%E1%84%89%E1%85%B3%E1%84%8F%E1%85%B3%E1%84%85%E1%85%B5%E1%86%AB%E1%84%89%E1%85%A3%E1%86%BA_2026-03-02_%E1%84%8B%E1%85%A9%E1%84%92%E1%85%AE_2.47.14.png)
    
    ```scala
    // [After] Off-heap 캐싱 (GC 대상 제외) 
    // off heap 할 때 Kryo 명시적 등록 필수
    hugeData.unpersist()
    hugeData.persist(org.apache.spark.storage.StorageLevel.OFF_HEAP)
    hugeData.count()
    ```
    
    ![스크린샷 2026-03-02 오후 2.47.39.png](%EC%A3%BC%EC%9A%94%20%EC%84%B1%EB%8A%A5%20%EC%B5%9C%EC%A0%81%ED%99%94%20%EC%9A%94%EC%86%8C/%E1%84%89%E1%85%B3%E1%84%8F%E1%85%B3%E1%84%85%E1%85%B5%E1%86%AB%E1%84%89%E1%85%A3%E1%86%BA_2026-03-02_%E1%84%8B%E1%85%A9%E1%84%92%E1%85%AE_2.47.39.png)
    
    - 데이터가 힙 외부에 저장되므로 힙 메모리 압박이 줄어들어 Full GC 발생 빈도가 낮아지고, 결과적으로 애플리케이션의 멈춤 현상(Pause)이 개선됩니다.

1. **Serialization (Java vs Kryo) 성능 비교**
    
    ```scala
    // [Case A] Java 직렬화 (기본값)
    ./spark-shell --driver-memory 1g --executor-memory 1g
    
    // 두 세션 모두에서 먼저 클래스를 정의합니다.
    case class Person(name: String, age: Int)
    val data = (1 to 10000).map(i => Person(s"User$i", i % 100))
    val rdd = sc.parallelize(data)
    rdd.setName("JavaBenchmark")
    
    import org.apache.spark.storage.StorageLevel
    
    // MEMORY_ONLY_SER: 데이터를 직렬화하여 메모리에 저장 
    rdd.persist(StorageLevel.MEMORY_ONLY_SER)
    val t1 = System.currentTimeMillis()
    rdd.count() 
    println(s"Java Serialization Time: ${System.currentTimeMillis() - t1}ms")
    ```
    
    ```scala
    // [Case B] Kryo 직렬화 (성공: 최적화 적용)
    ./spark-shell --driver-memory 1g --executor-memory 1g \
    --conf "spark.serializer=org.apache.spark.serializer.KryoSerializer" \
    --conf "spark.kryo.registrationRequired=false"
    
    case class Person(name: String, age: Int)
    val data = (1 to 10000).map(i => Person(s"User$i", i % 100))
    val rdd = sc.parallelize(data)
    rdd.setName("KryoBenchmark")
    
    import org.apache.spark.storage.StorageLevel
    rdd.persist(StorageLevel.MEMORY_ONLY_SER)
    
    val t2 = System.currentTimeMillis()
    rdd.count()
    println(s"Kryo Serialization Time: ${System.currentTimeMillis() - t2}ms")
    ```
    
    - Kryo 는 모든 객체를 직렬화할 수 없으므로 클래스와 배열을 명시적으로 등록해야 성능이 극대화됩니다.
    - Kryo 를 적용하면 Java 기본 직렬화 대비 **성능은 10~20% 향상**되고, **메모리 사용량은 20~30% 감소**합니다.

---

| **최적화 항목** | **핵심 액션 플랜** | **기대 효과 (최대)** |
| --- | --- | --- |
| **직렬화** | Kryo 활성화 및 클래스/배열 등록 | **메모리 30% 절감, 성능 20% 향상** |
| **파티셔닝** | 초기 파티션 수 최적화로 셔플 제거 | 셔플 비용(Exchange) 100% 제거 |
| **푸시다운** | 저장소 레벨 필터링(PushedFilters) 적용 | I/O 시간 및 데이터 로드량 급감 |
| **메모리** | Off-heap 활성화로 GC 오버헤드 관리 | 시스템 안정성 및 Pause 시간 단축 |