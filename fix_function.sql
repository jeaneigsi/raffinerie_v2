CREATE OR REPLACE FUNCTION public.get_pipeline_latency_stats(time_window interval DEFAULT '00:02:00'::interval)
 RETURNS TABLE(stage text, avg_ms double precision, min_ms double precision, max_ms double precision, p95_ms double precision, p99_ms double precision)
 LANGUAGE plpgsql
AS $function$
BEGIN
    RETURN QUERY
    
    -- Statistiques MQTT vers Kafka
    SELECT 
        'MQTT → Kafka' AS stage,
        AVG(value_ms) AS avg_ms,
        MIN(value_ms) AS min_ms,
        MAX(value_ms) AS max_ms,
        percentile_cont(0.95) WITHIN GROUP (ORDER BY value_ms) AS p95_ms,
        percentile_cont(0.99) WITHIN GROUP (ORDER BY value_ms) AS p99_ms
    FROM
        pipeline_kpi
    WHERE
        time > NOW() - time_window AND
        metric_name = 'mqtt_to_kafka'

    UNION ALL

    -- Statistiques Kafka vers Spark
    SELECT
        'Kafka → Spark' AS stage,
        AVG(value_ms) AS avg_ms,
        MIN(value_ms) AS min_ms,
        MAX(value_ms) AS max_ms,
        percentile_cont(0.95) WITHIN GROUP (ORDER BY value_ms) AS p95_ms,
        percentile_cont(0.99) WITHIN GROUP (ORDER BY value_ms) AS p99_ms
    FROM
        pipeline_kpi
    WHERE
        time > NOW() - time_window AND
        metric_name = 'kafka_to_spark'

    UNION ALL

    -- Statistiques Spark vers TimescaleDB
    SELECT
        'Spark → TimescaleDB' AS stage,
        AVG(value_ms) AS avg_ms,
        MIN(value_ms) AS min_ms,
        MAX(value_ms) AS max_ms,
        percentile_cont(0.95) WITHIN GROUP (ORDER BY value_ms) AS p95_ms,
        percentile_cont(0.99) WITHIN GROUP (ORDER BY value_ms) AS p99_ms
    FROM
        pipeline_kpi
    WHERE
        time > NOW() - time_window AND
        metric_name = 'spark_to_timescaledb'

    UNION ALL

    -- Statistiques de latence totale
    SELECT
        'Total (bout en bout)' AS stage,
        AVG(value_ms) AS avg_ms,
        MIN(value_ms) AS min_ms,
        MAX(value_ms) AS max_ms,
        percentile_cont(0.95) WITHIN GROUP (ORDER BY value_ms) AS p95_ms,
        percentile_cont(0.99) WITHIN GROUP (ORDER BY value_ms) AS p99_ms
    FROM
        pipeline_kpi
    WHERE
        time > NOW() - time_window AND
        metric_name = 'total_pipeline_latency';
END;
$function$; 