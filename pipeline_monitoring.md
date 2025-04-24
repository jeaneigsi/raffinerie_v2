# Monitoring du Pipeline IoT

Ce document contient des requêtes et configurations pour surveiller l'ensemble du pipeline de données IoT, de la collecte via MQTT jusqu'au stockage dans TimescaleDB et MinIO.

## 1. Configuration des outils de monitoring

### Spark UI
- **URL**: http://localhost:4040
- **Description**: Interface utilisateur Spark qui montre les jobs, stages, tâches, et métriques d'exécution
- **Utilisation**: Visualiser les performances du traitement Spark en temps réel

### Kafka UI
- **URL**: http://localhost:8080
- **Description**: Interface utilisateur pour monitorer Kafka
- **Utilisation**: Suivi des topics, messages, et performances des brokers Kafka

### MinIO Console
- **URL**: http://localhost:9001
- **Description**: Interface utilisateur pour MinIO
- **Utilisation**: Vérifier le stockage S3, visualiser les objets créés par Spark

### pgAdmin
- **URL**: http://localhost:5050
- **Description**: Interface d'administration pour PostgreSQL/TimescaleDB
- **Utilisation**: Exécuter des requêtes et explorer la base de données

### Tableau de bord de performance
- **URL**: http://localhost:3000/d/iot-pipeline-performance
- **Description**: Tableau de bord Grafana dédié aux métriques de performance du pipeline
- **Utilisation**: Suivi des latences et du débit de traitement à chaque étape du pipeline

## 2. Indicateurs de Performance Clés (KPI) de temps

Le pipeline IoT mesure plusieurs KPI de temps critiques pour évaluer sa performance :

### Latence par étape
Mesure le temps nécessaire à chaque étape du pipeline pour traiter les données :

```sql
-- Requête pour obtenir la latence moyenne par étape du pipeline
SELECT 
  stage as "Étape du pipeline",
  avg_ms as "Latence moyenne (ms)",
  min_ms as "Minimum (ms)",
  max_ms as "Maximum (ms)",
  p95_ms as "95e percentile (ms)"
FROM
  get_pipeline_latency_stats(INTERVAL '2 minutes')
ORDER BY
  CASE 
    WHEN stage = 'MQTT → Kafka' THEN 1
    WHEN stage = 'Kafka → Spark' THEN 2
    WHEN stage = 'Spark → TimescaleDB' THEN 3
    WHEN stage = 'Total (bout en bout)' THEN 4
    ELSE 5
  END;
```

### Latence bout en bout
Mesure le temps total entre la réception des données par MQTT et leur stockage dans TimescaleDB :

```sql
-- Requête pour obtenir la latence bout en bout moyenne au cours du temps
SELECT
  time_bucket('30 seconds', time) AS minute,
  AVG(total_latency_ms) as avg_latency_ms,
  MIN(total_latency_ms) as min_latency_ms,
  MAX(total_latency_ms) as max_latency_ms
FROM
  pipeline_latency
WHERE
  time > NOW() - INTERVAL '2 minutes'
GROUP BY
  minute
ORDER BY
  minute;
```

### Temps de traitement Spark
Mesure le temps nécessaire à Spark pour traiter un lot de données et l'écrire dans TimescaleDB :

```sql
-- Requête pour obtenir les statistiques de temps de traitement Spark
SELECT
  time_bucket('30 seconds', time) AS minute,
  AVG(processing_time) as avg_processing_time,
  MIN(processing_time) as min_processing_time,
  MAX(processing_time) as max_processing_time
FROM
  processing_metrics
WHERE
  time > NOW() - INTERVAL '2 minutes'
GROUP BY
  minute
ORDER BY
  minute;
```

### Débit de traitement
Mesure le nombre de messages traités par unité de temps :

```sql
-- Requête pour obtenir le débit de traitement par minute
SELECT
  time_bucket('30 seconds', time) AS minute,
  COUNT(*) as messages_per_minute
FROM
  sensor_data
WHERE
  time > NOW() - INTERVAL '2 minutes'
GROUP BY
  minute
ORDER BY
  minute;
```

## 3. Autres requêtes pour le monitoring du pipeline

### Monitoring de l'ingestion de données

**Titre**: Taux d'ingestion de données par source  
**Description**: Mesure le nombre de messages reçus par minute pour surveiller le flux d'entrée  
**Visualisation**: Time series (Séries temporelles)  

```sql
SELECT
  time_bucket('1 minute', time) AS minute,
  COUNT(*) as messages_per_minute
FROM
  sensor_data
WHERE
  time > NOW() - INTERVAL '1 hour'
GROUP BY
  minute
ORDER BY
  minute
```

### Monitoring des latences d'écriture

**Titre**: Latence d'écriture en base de données  
**Description**: Mesure le délai entre la collecte des données et leur écriture en base  
**Visualisation**: Gauge (Jauge) ou Time series (Séries temporelles)  

```sql
SELECT
  AVG(EXTRACT(EPOCH FROM (NOW() - time))) as avg_write_latency_seconds,
  MAX(EXTRACT(EPOCH FROM (NOW() - time))) as max_write_latency_seconds,
  MIN(EXTRACT(EPOCH FROM (NOW() - time))) as min_write_latency_seconds
FROM
  sensor_data
WHERE
  time > NOW() - INTERVAL '5 minutes'
```

### Monitoring de la taille des données

**Titre**: Volume de données par heure  
**Description**: Mesure la quantité de données collectées par heure  
**Visualisation**: Bar chart (Graphique à barres)  

```sql
SELECT
  time_bucket('1 hour', time) AS hour,
  COUNT(*) as row_count,
  pg_size_pretty(pg_total_relation_size('sensor_data')) as total_table_size
FROM
  sensor_data
WHERE
  time > NOW() - INTERVAL '24 hours'
GROUP BY
  hour
ORDER BY
  hour
```

### Monitoring des erreurs d'écriture

**Titre**: Vérification de l'intégrité des données  
**Description**: Détecte les données mal formées ou invalides  
**Visualisation**: Table (Tableau)  

```sql
SELECT
  time,
  temperature,
  humidity,
  sensor_id
FROM
  sensor_data
WHERE
  time > NOW() - INTERVAL '1 hour'
  AND (
    temperature IS NULL OR
    humidity IS NULL OR
    temperature < 0 OR
    temperature > 100 OR
    humidity < 0 OR
    humidity > 100
  )
ORDER BY
  time DESC
```

## 4. Tableau de bord de monitoring du pipeline

Pour créer un tableau de bord complet de surveillance du pipeline dans Grafana :

1. Utilisez le tableau de bord préconfiguré "Performance du Pipeline IoT" à l'URL `http://localhost:3000/d/iot-pipeline-performance`
2. Ou créez un nouveau tableau de bord personnalisé avec les sections suivantes :

### Section 1 : État du système
- État de Kafka (Stat panel connecté à Kafka via Prometheus ou JMX)
- État de Spark (Stat panel)
- État de TimescaleDB (Stat panel)
- État de MinIO (Stat panel)

### Section 2 : Métriques de performance
- Débit d'entrée (messages/seconde)
- Latence par étape du pipeline
- Latence totale bout en bout
- Temps de traitement Spark

### Section 3 : Liens rapides
- Lien vers Spark UI
- Lien vers Kafka UI
- Lien vers MinIO Console
- Lien vers pgAdmin

## 5. Scripts de surveillance pour les logs Spark

Créez un script shell pour surveiller les logs Spark :

```bash
#!/bin/bash
# monitor_spark_logs.sh

docker logs -f spark-processor | grep -E "Error|Exception|Erreur|Failed|Échec"
```

## 6. Alertes de performance

Le tableau de bord Grafana peut être configuré avec des alertes pour surveiller les performances :

1. **Alerte de latence élevée** : Se déclenche lorsque la latence totale dépasse un seuil critique (par exemple, 1000 ms)
2. **Alerte de débit faible** : Se déclenche lorsque le débit tombe en dessous d'un seuil minimum (par exemple, 10 messages/minute)
3. **Alerte d'erreur de traitement** : Se déclenche lorsque des erreurs sont détectées dans le pipeline

Configuration d'exemple pour une alerte de latence :

```yaml
name: 'Latence élevée du pipeline'
conditions:
  - type: query
    query:
      datasourceId: TimescaleDB
      model:
        rawSql: >
          SELECT
            NOW() as time,
            avg_ms
          FROM
            get_pipeline_latency_stats(INTERVAL '5 minutes')
          WHERE
            stage = 'Total (bout en bout)'
    reducer: last
    evaluator:
      type: greater
      params:
        - 1000  # Seuil en millisecondes
``` 