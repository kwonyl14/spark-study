---
slug: week-1-caching-vs-checkpointing
title: "1주차: Spark Caching과 Checkpointing의 차이와 실전 활용법"
authors: [kwonyl14]
tags: [spark, scala, optimization, caching, checkpointing]
description: "Spark 성능 최적화의 핵심인 Caching(StorageLevel)과 Checkpointing의 내부 동작 원리를 깊이 있게 비교하고, 실무 적용 기준을 정리한다."
---

스파크(Spark) 애플리케이션을 개발하다 보면 Join이나 정렬(Sort) 같은 무거운(Expensive) 연산 결과를 여러 번 재사용해야 하는 상황이 반드시 발생한다. 이때 아무 처리도 하지 않으면 액션(Action)이 호출될 때마다 데이터를 처음부터 다시 읽고 계산하는 엄청난 비효율이 발생한다.

이 문제를 해결하는 두 가지 핵심 무기가 바로 **캐싱(Caching)** 과 **체크포인팅(Checkpointing)** 이다. 두 기법은 비슷해 보이지만 내부 동작 원리와 목적이 완전히 다르다. 코드를 통해 이 둘의 차이를 확인한다.

---

## 1. Caching: 빠른 재사용을 위한 메모리 최적화

캐싱은 계산이 끝난 DataFrame이나 RDD를 메모리나 디스크에 임시로 저장해 두는 기법이다. 가장 큰 특징은 **데이터의 계산 족보(Lineage)를 그대로 유지**한다는 점이다. 즉, 캐시된 데이터가 날아가면 스파크는 언제든 처음부터 다시 계산해서 복구할 수 있다.

### 1-1. DataFrame 캐싱과 StorageLevel
스파크는 상황에 맞게 데이터를 어디에, 어떻게 저장할지 결정하는 다양한 `StorageLevel`을 제공한다.

```scala
import org.apache.spark.sql.SparkSession
import org.apache.spark.storage.StorageLevel

val spark = SparkSession.builder()
  .appName("CachingDemo")
  .config("spark.memory.offHeap.enabled", "true")
  .config("spark.memory.offHeap.size", 10000000)
  .master("local")
  .getOrCreate()

val flightsDF = spark.read.option("inferSchema", "true").json("src/main/resources/data/flights")
val orderedFlightsDF = flightsDF.orderBy("dist") // 무거운 연산 가정

// 다양한 캐싱 옵션 적용
orderedFlightsDF.persist(
  // 1. 메모리에 원본 객체로 저장 (가장 빠름, OOM 위험)
  // StorageLevel.MEMORY_ONLY 
  
  // 2. 디스크에만 저장 (메모리 절약, I/O로 인해 느림)
  // StorageLevel.DISK_ONLY 
  
  // 3. 메모리에 먼저 채우고, 넘치면 디스크로 Spill (DF 기본값)
  // StorageLevel.MEMORY_AND_DISK 

  // 4. 가비지 컬렉터(GC)를 회피하는 Off-Heap 메모리 저장 (Tungsten 엔진 활용)
  StorageLevel.OFF_HEAP 
)

orderedFlightsDF.count() // 첫 번째 액션: 계산 후 캐시 메모리에 적재됨
orderedFlightsDF.count() // 두 번째 액션: 캐시에서 바로 읽어와서 훨씬 빠름!

// 캐시 메모리 해제
orderedFlightsDF.unpersist()
```

### 1-2. RDD 직렬화 캐싱 (메모리 다이어트)
오래된 RDD API를 사용할 때는 `_SER`(Serialized) 옵션이 필수적이다.

```scala
val flightsRDD = orderedFlightsDF.rdd

// 자바 객체 대신 바이트 배열로 직렬화하여 메모리 용량 극적 절감
flightsRDD.persist(StorageLevel.MEMORY_ONLY_SER)
flightsRDD.count()
```
RDD는 무거운 JVM 객체를 생성하기 때문에 `MEMORY_ONLY`를 쓰면 OOM이 터지기 쉽다. 하지만 DataFrame을 쓰면 스파크 카탈리스트(Catalyst) 엔진이 알아서 효율적인 바이너리 포맷으로 저장해주기 때문에 굳이 RDD로 변환해서 캐싱할 필요는 없다.

---

## 2. Checkpointing: DAG를 끊어내는 단두대

체크포인팅은 메모리 부족이나 노드 장애를 대비해, 데이터를 임시가 아닌 **HDFS나 로컬 디스크 같은 영구적이고 안전한 저장소에 물리적으로 기록**해 버리는 기법이다. 

가장 중요한 차이는 **계산 족보(Lineage, DAG)를 싹둑 끊어버린다**는 것이다.



### 2-1. Checkpointing 코드 구현
체크포인팅을 사용하려면 반드시 스파크 컨텍스트(`sc`)에 저장할 디렉토리를 먼저 지정해야 한다.

```scala
val sc = spark.sparkContext
// 체크포인트 저장 경로 설정 (실무에서는 HDFS나 S3 경로 사용)
sc.setCheckpointDir("spark-warehouse")

val orderedFlights = flightsDF.orderBy("dist")

// checkpoint() 자체가 액션(Action)을 트리거하며 디스크에 데이터를 쓴다.
val checkpointedFlights = orderedFlights.checkpoint() 

checkpointedFlights.count() // 디스크에서 바로 읽어옴
```

### 2-2. 실행 계획(Physical Plan) 비교 분석
캐싱과 체크포인팅의 근본적인 차이는 `explain()`을 통해 실행 계획을 열어봤을 때 명확하게 드러난다.

**[일반 DF 또는 캐싱된 DF의 실행 계획]**
```text
orderedFlights.explain()
/*
== Physical Plan ==
*(1) Sort [dist#16 ASC NULLS FIRST], true, 0
+- *(1) Project [_id#7, arrdelay#8, ... ]
   +- BatchScan[...] JsonScan Location: InMemoryFileIndex[...]
*/
```
위처럼 캐시를 쓰더라도 스파크는 "여차하면 내가 파일부터 다시 읽어서 Sort할게"라며 전체 계획(Lineage)을 길게 들고 있다.

**[체크포인트된 DF의 실행 계획]**
```text
checkpointedFlights.explain()
/*
== Physical Plan ==
*(1) Scan ExistingRDD[_id#7,arrdelay#8, ... ]
*/
```
체크포인트 이후의 데이터프레임은 이전의 `Sort`, `Project`, `JsonScan` 같은 복잡한 과거를 완전히 잊어버린다. 오직 디스크에 저장된 결과물(`ExistingRDD`)을 새로운 시작점(Source)으로 삼는다.

---

## 3. 요약 및 실전 결론: 언제 무엇을 써야 할까?

| 구분 | Caching (캐싱) | Checkpointing (체크포인팅) |
| :--- | :--- | :--- |
| **저장 위치** | 메모리 중심 (설정에 따라 디스크 혼용) | 영구 저장소 (HDFS, S3, 로컬 디스크 등) |
| **Lineage (족보)** | 유지됨 (장애 시 처음부터 다시 계산) | **단절됨** (과거 연산 기록 삭제) |
| **속도** | 매우 빠름 (특히 메모리 Hit 시) | 상대적으로 느림 (디스크 I/O 발생) |
| **목적** | 반복 연산 속도 향상 | 장애 복구, 긴 연산 체인 끊기 |

### 🚀 Caching을 써야 할 때 (Performance Focus)
* 동일한 잡(Job) 안에서 머신러닝 모델을 반복 학습시킬 때.
* 룩업 테이블(Lookup Table)처럼 자주 조인되는 작은 DataFrame을 재사용할 때.
* 연산 속도를 쥐어짜야 하는 상황일 때.

### 🛡️ Checkpointing을 써야 할 때 (Reliability Focus)
* **배치 작업 시간이 너무 길어서** 중간에 에러가 났을 때 처음부터 다시 돌리는 것이 재앙인 경우.
* DataFrame의 `withColumn`이나 `join` 변환이 수십, 수백 번 겹쳐서 **실행 계획(DAG)이 너무 길어지고 메모리를 많이 먹어 드라이버에서 `StackOverflowError`가 터질 위험**이 있을 때. (이때 체크포인트를 한 번씩 찍어주면 DAG가 초기화되어 에러를 막을 수 있다.)
* Spark Structured Streaming 운영 시 장애 복구를 위해.

### 💡 실무 운영 팁
현업에서는 긴 데이터 파이프라인을 설계할 때, 중간중간 무거운 셔플(Shuffle)이 끝나는 지점에 **캐싱과 체크포인팅을 함께 사용**하기도 한다. 데이터를 메모리에 올려 빠르게 재사용하면서도, 디스크에 안전하게 백업해두어 DAG를 자르고 장애에 대비하는 훌륭한 전략이다.