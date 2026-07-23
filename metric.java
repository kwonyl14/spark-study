import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import org.springframework.stereotype.Service;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

@Service
public class MetricService {

    private final MeterRegistry registry;
    
    // 분석 타입별 Running 중인 Spark 잡 수 관리를 위한 Map (Gauge용)
    private final Map<String, AtomicInteger> activeJobsMap = new ConcurrentHashMap<>();

    public MetricService(MeterRegistry registry) {
        this.registry = registry;
    }

    // ----------------------------------------------------------------
    // 1. MinIO Presigned URL 메트릭
    // ----------------------------------------------------------------
    public void recordMinioUrlRequest(String action, boolean isSuccess, long durationMs) {
        String status = isSuccess ? "success" : "fail";

        Counter.builder("minio_presigned_url_requests_total")
                .tag("action", action)
                .tag("status", status)
                .register(registry)
                .increment();

        Timer.builder("minio_presigned_url_duration_seconds")
                .tag("action", action)
                .register(registry)
                .record(durationMs, TimeUnit.MILLISECONDS);
    }

    // ----------------------------------------------------------------
    // 2. Spark CR 제출 메트릭
    // ----------------------------------------------------------------
    public void recordSparkSubmit(String analysisType, boolean isSuccess) {
        String status = isSuccess ? "success" : "fail";

        Counter.builder("spark_job_submissions_total")
                .tag("analysis_type", analysisType)
                .tag("status", status)
                .register(registry)
                .increment();
    }

    // ----------------------------------------------------------------
    // 3. Spark CR Running 상태 관리 (Gauge)
    // ----------------------------------------------------------------
    public void incrementActiveJob(String analysisType) {
        activeJobsMap.computeIfAbsent(analysisType, type -> {
            AtomicInteger count = new AtomicInteger(0);
            Gauge.builder("spark_job_active_total", count, AtomicInteger::get)
                    .tag("analysis_type", type)
                    .description("현재 실행 중인 Spark CR 개수")
                    .register(registry);
            return count;
        }).incrementAndGet();
    }

    public void decrementActiveJob(String analysisType) {
        AtomicInteger count = activeJobsMap.get(analysisType);
        if (count != null && count.get() > 0) {
            count.decrementAndGet();
        }
    }

    // ----------------------------------------------------------------
    // 4. Spark CR 최종 처리 시간 측정 (Timer)
    // ----------------------------------------------------------------
    public void recordSparkExecutionDuration(String analysisType, String finalStatus, long executionDurationMs) {
        Timer.builder("spark_job_execution_duration_seconds")
                .tag("analysis_type", analysisType)
                .tag("status", finalStatus) // SUCCESS, FAILED
                .description("Spark 잡 전체 처리 소요 시간")
                .register(registry)
                .record(executionDurationMs, TimeUnit.MILLISECONDS);
    }
}
