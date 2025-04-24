-- Script d'initialisation pour TimescaleDB
-- Ce script crée les tables nécessaires pour stocker les données des capteurs
-- et les métriques de performance du pipeline

-- Création de la table principale pour les données des capteurs
CREATE TABLE IF NOT EXISTS sensor_data (
    time TIMESTAMP WITH TIME ZONE NOT NULL,
    sensor_id TEXT NOT NULL,
    temperature DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    raw_data JSONB,
    spark_receive_time DOUBLE PRECISION,
    mqtt_receive_time DOUBLE PRECISION,
    kafka_send_time DOUBLE PRECISION
);

-- Conversion en hypertable TimescaleDB (optimisée pour les séries temporelles)
SELECT create_hypertable('sensor_data', 'time', if_not_exists => TRUE);

-- Création d'index pour accélérer les requêtes
CREATE INDEX IF NOT EXISTS idx_sensor_data_sensor_id ON sensor_data (sensor_id, time DESC);

-- Création d'une table pour les métriques de performance
CREATE TABLE IF NOT EXISTS processing_metrics (
    time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    batch_id VARCHAR(50),
    processing_time FLOAT,           -- Temps total de traitement en secondes
    avg_processing_time FLOAT,       -- Temps moyen sur les N derniers lots
    min_processing_time FLOAT,       -- Temps minimum
    max_processing_time FLOAT,       -- Temps maximum
    sample_size INTEGER              -- Nombre d'échantillons utilisés
);

-- Conversion de la table des métriques en hypertable
SELECT create_hypertable('processing_metrics', 'time', if_not_exists => TRUE);

-- Création d'une vue pour calculer les temps de bout en bout du pipeline
CREATE OR REPLACE VIEW pipeline_latency AS
SELECT 
    time,
    sensor_id,
    temperature,
    humidity,
    spark_receive_time,
    mqtt_receive_time,
    kafka_send_time,
    -- Calcul des délais à chaque étape du pipeline (en millisecondes)
    (kafka_send_time - mqtt_receive_time) * 1000 AS mqtt_to_kafka_ms,
    (spark_receive_time - kafka_send_time) * 1000 AS kafka_to_spark_ms,
    (EXTRACT(EPOCH FROM time) - spark_receive_time) * 1000 AS spark_to_db_ms,
    -- Délai total de bout en bout
    (EXTRACT(EPOCH FROM time) - mqtt_receive_time) * 1000 AS total_latency_ms
FROM 
    sensor_data
WHERE 
    mqtt_receive_time IS NOT NULL;

-- Fonction pour obtenir les statistiques de latence du pipeline
CREATE OR REPLACE FUNCTION get_pipeline_latency_stats(
    time_window INTERVAL DEFAULT INTERVAL '2 minutes'
)
RETURNS TABLE (
    stage TEXT,
    avg_ms FLOAT,
    min_ms FLOAT,
    max_ms FLOAT,
    p95_ms FLOAT,
    p99_ms FLOAT
)
AS $$
BEGIN
    RETURN QUERY
    
    -- Statistiques MQTT vers Kafka
    SELECT 
        'MQTT → Kafka' AS stage,
        AVG(mqtt_to_kafka_ms) AS avg_ms,
        MIN(mqtt_to_kafka_ms) AS min_ms,
        MAX(mqtt_to_kafka_ms) AS max_ms,
        percentile_cont(0.95) WITHIN GROUP (ORDER BY mqtt_to_kafka_ms) AS p95_ms,
        percentile_cont(0.99) WITHIN GROUP (ORDER BY mqtt_to_kafka_ms) AS p99_ms
    FROM 
        pipeline_latency
    WHERE 
        time > NOW() - time_window
        
    UNION ALL
    
    -- Statistiques Kafka vers Spark
    SELECT 
        'Kafka → Spark' AS stage,
        AVG(kafka_to_spark_ms) AS avg_ms,
        MIN(kafka_to_spark_ms) AS min_ms,
        MAX(kafka_to_spark_ms) AS max_ms,
        percentile_cont(0.95) WITHIN GROUP (ORDER BY kafka_to_spark_ms) AS p95_ms,
        percentile_cont(0.99) WITHIN GROUP (ORDER BY kafka_to_spark_ms) AS p99_ms
    FROM 
        pipeline_latency
    WHERE 
        time > NOW() - time_window
        
    UNION ALL
    
    -- Statistiques Spark vers TimescaleDB
    SELECT 
        'Spark → TimescaleDB' AS stage,
        AVG(spark_to_db_ms) AS avg_ms,
        MIN(spark_to_db_ms) AS min_ms,
        MAX(spark_to_db_ms) AS max_ms,
        percentile_cont(0.95) WITHIN GROUP (ORDER BY spark_to_db_ms) AS p95_ms,
        percentile_cont(0.99) WITHIN GROUP (ORDER BY spark_to_db_ms) AS p99_ms
    FROM 
        pipeline_latency
    WHERE 
        time > NOW() - time_window
        
    UNION ALL
    
    -- Statistiques de latence totale
    SELECT 
        'Total (bout en bout)' AS stage,
        AVG(total_latency_ms) AS avg_ms,
        MIN(total_latency_ms) AS min_ms,
        MAX(total_latency_ms) AS max_ms,
        percentile_cont(0.95) WITHIN GROUP (ORDER BY total_latency_ms) AS p95_ms,
        percentile_cont(0.99) WITHIN GROUP (ORDER BY total_latency_ms) AS p99_ms
    FROM 
        pipeline_latency
    WHERE 
        time > NOW() - time_window;
END;
$$ LANGUAGE plpgsql;

-- Création d'une table spécifique pour les KPI de temps du pipeline
CREATE TABLE IF NOT EXISTS pipeline_kpi (
    time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metric_name TEXT NOT NULL,       -- Nom du KPI (ex: 'mqtt_to_kafka', 'kafka_to_spark', 'spark_to_db', 'total_latency')
    value_ms DOUBLE PRECISION,       -- Valeur du KPI en millisecondes
    batch_id TEXT,                   -- Identifiant du lot (si applicable)
    message_count INTEGER,           -- Nombre de messages dans le lot
    metadata JSONB                   -- Métadonnées supplémentaires (détails, contexte, etc.)
);

-- Conversion en hypertable TimescaleDB
SELECT create_hypertable('pipeline_kpi', 'time', if_not_exists => TRUE);

-- Création d'index pour accélérer les requêtes
CREATE INDEX IF NOT EXISTS idx_pipeline_kpi_metric_name ON pipeline_kpi (metric_name, time DESC);

-- Fonction pour insérer des KPI
CREATE OR REPLACE FUNCTION insert_pipeline_kpi(
    p_metric_name TEXT,
    p_value_ms DOUBLE PRECISION,
    p_batch_id TEXT DEFAULT NULL,
    p_message_count INTEGER DEFAULT NULL,
    p_metadata JSONB DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    INSERT INTO pipeline_kpi (metric_name, value_ms, batch_id, message_count, metadata)
    VALUES (p_metric_name, p_value_ms, p_batch_id, p_message_count, p_metadata);
END;
$$ LANGUAGE plpgsql;

-- Vue pour l'analyse des KPI par période et par métrique
CREATE OR REPLACE VIEW pipeline_kpi_stats AS
WITH kpi_periods AS (
    SELECT 
        metric_name,
        time_bucket('1 minute', time) AS minute,
        AVG(value_ms) AS avg_ms,
        MIN(value_ms) AS min_ms,
        MAX(value_ms) AS max_ms,
        percentile_cont(0.95) WITHIN GROUP (ORDER BY value_ms) AS p95_ms,
        percentile_cont(0.99) WITHIN GROUP (ORDER BY value_ms) AS p99_ms,
        COUNT(*) AS sample_count
    FROM 
        pipeline_kpi
    GROUP BY 
        metric_name, minute
)
SELECT 
    metric_name,
    minute,
    avg_ms,
    min_ms,
    max_ms,
    p95_ms,
    p99_ms,
    sample_count,
    -- Variation par rapport à la période précédente (si disponible)
    100.0 * (avg_ms - LAG(avg_ms) OVER (PARTITION BY metric_name ORDER BY minute)) / 
           NULLIF(LAG(avg_ms) OVER (PARTITION BY metric_name ORDER BY minute), 0) AS pct_change
FROM 
    kpi_periods
ORDER BY 
    metric_name, minute;

-- Création d'une fonction d'agrégation personnalisée pour calculer les KPI
CREATE OR REPLACE FUNCTION calculate_pipeline_kpis(
    time_window INTERVAL DEFAULT INTERVAL '2 minutes'
) RETURNS TABLE (
    time TIMESTAMP WITH TIME ZONE,
    mqtt_to_kafka_ms DOUBLE PRECISION,
    kafka_to_spark_ms DOUBLE PRECISION,
    spark_to_db_ms DOUBLE PRECISION,
    total_latency_ms DOUBLE PRECISION,
    processing_efficiency_pct DOUBLE PRECISION
) AS $$
BEGIN
    RETURN QUERY
    WITH metrics AS (
        SELECT
            time_bucket('10 seconds', time) AS bucket_time,
            -- Temps moyens pour chaque étape
            AVG((kafka_send_time - mqtt_receive_time) * 1000) AS avg_mqtt_to_kafka_ms,
            AVG((spark_receive_time - kafka_send_time) * 1000) AS avg_kafka_to_spark_ms,
            AVG((EXTRACT(EPOCH FROM time) - spark_receive_time) * 1000) AS avg_spark_to_db_ms,
            -- Temps total moyen
            AVG((EXTRACT(EPOCH FROM time) - mqtt_receive_time) * 1000) AS avg_total_ms,
            -- Nombre de messages
            COUNT(*) AS message_count
        FROM
            sensor_data
        WHERE
            time > NOW() - time_window
            AND mqtt_receive_time IS NOT NULL
            AND kafka_send_time IS NOT NULL
            AND spark_receive_time IS NOT NULL
        GROUP BY
            bucket_time
    )
    SELECT
        bucket_time,
        avg_mqtt_to_kafka_ms,
        avg_kafka_to_spark_ms,
        avg_spark_to_db_ms,
        avg_total_ms,
        -- Efficacité de traitement: pourcentage du temps total consacré au traitement utile
        -- Formule: (1 - (temps d'attente/temps total)) * 100
        (1 - (avg_kafka_to_spark_ms / NULLIF(avg_total_ms, 0))) * 100 AS processing_efficiency_pct
    FROM
        metrics
    ORDER BY
        bucket_time;
END;
$$ LANGUAGE plpgsql; 