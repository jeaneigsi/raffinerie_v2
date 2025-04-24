# Correction du système de métriques KPI

Ce document détaille les problèmes rencontrés avec le système de métriques de performance et les solutions mises en œuvre pour les résoudre.

## Problèmes identifiés

1. **Erreur d'indentation dans `write_to_timescaledb`**
   - Des problèmes d'indentation dans le bloc `try-except` empêchaient l'exécution correcte du code
   - Les lignes concernées étaient mal indentées après la déclaration `try:`

2. **Module `psycopg2` manquant**
   - Le conteneur Spark ne disposait pas du module `psycopg2` nécessaire pour les connexions directes à TimescaleDB
   - Les métriques étaient calculées mais ne pouvaient pas être stockées

3. **Fonction SQL `get_pipeline_latency_stats` incorrecte**
   - La fonction faisait référence à une table non existante (`pipeline_latency`)
   - Elle devait être modifiée pour utiliser la table `pipeline_kpi` existante

## Solutions implémentées

### 1. Correction des erreurs d'indentation

Le code a été reformaté avec une indentation cohérente dans toutes les fonctions, en particulier `write_to_timescaledb`:

```python
# Avant (problématique)
try:
    print(f"✅ Préparation des données pour le lot {epoch_id}...")
    
    # Convertir le timestamp Unix en timestamp SQL pour compatibilité TimescaleDB
batch_df = batch_df.withColumn("time", to_timestamp(col("timestamp")))

# Après (corrigé)
try:
    print(f"✅ Préparation des données pour le lot {epoch_id}...")
    
    # Convertir le timestamp Unix en timestamp SQL pour compatibilité TimescaleDB
    batch_df = batch_df.withColumn("time", to_timestamp(col("timestamp")))
```

### 2. Installation de `psycopg2`

Installation du module nécessaire dans le conteneur Spark :

```bash
docker exec spark-processor pip install psycopg2-binary
```

Le code `spark_app.py` inclut déjà un mécanisme de détection de la disponibilité du module :

```python
PSYCOPG2_AVAILABLE = False
try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    logger.warning("Module psycopg2 non disponible. Le stockage des KPI en base de données sera limité.")
```

### 3. Correction de la fonction SQL `get_pipeline_latency_stats`

Création d'un fichier SQL pour remplacer la fonction existante :

```sql
CREATE OR REPLACE FUNCTION get_pipeline_latency_stats(
    time_window INTERVAL DEFAULT '1 hour'::INTERVAL
)
RETURNS TABLE (
    stage TEXT,
    avg_ms DOUBLE PRECISION,
    min_ms DOUBLE PRECISION,
    max_ms DOUBLE PRECISION,
    p95_ms DOUBLE PRECISION,
    p99_ms DOUBLE PRECISION
) AS $$
BEGIN
    RETURN QUERY
    
    -- MQTT to Kafka latency
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
        metric_name = 'mqtt_to_kafka' AND
        time > now() - time_window
    
    UNION ALL
    
    -- Kafka to Spark latency
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
        metric_name = 'kafka_to_spark' AND
        time > now() - time_window
    
    UNION ALL
    
    -- Spark to TimescaleDB latency
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
        metric_name = 'spark_to_timescaledb' AND
        time > now() - time_window
    
    UNION ALL
    
    -- Total pipeline latency
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
        metric_name = 'total_pipeline_latency' AND
        time > now() - time_window;
END;
$$ LANGUAGE plpgsql;
```

## Vérification de la solution

Après avoir mis en œuvre ces corrections, nous avons vérifié le bon fonctionnement avec les commandes suivantes :

```bash
# Vérifier que les données arrivent dans la table pipeline_kpi
docker exec timescaledb psql -U sensor_user -d sensordb -c "SELECT count(*) FROM pipeline_kpi;"

# Vérifier le contenu des dernières entrées
docker exec timescaledb psql -U sensor_user -d sensordb -c "SELECT metric_name, value_ms, message_count, time FROM pipeline_kpi ORDER BY time DESC LIMIT 10;"

# Tester la fonction d'analyse des statistiques de latence
docker exec timescaledb psql -U sensor_user -d sensordb -c "SELECT * FROM get_pipeline_latency_stats('1 hour'::interval);"
```

## Résultat

La fonction `get_pipeline_latency_stats` fonctionne maintenant correctement, permettant de :

- Agréger les données de latence par étape du pipeline
- Calculer les statistiques (moyenne, min, max, p95, p99) pour chaque étape
- Afficher les résultats dans un format adapté aux tableaux de bord Grafana

Les valeurs de latence sont maintenant enregistrées pour chaque lot de données traité et peuvent être utilisées pour surveiller les performances du système en temps réel. 