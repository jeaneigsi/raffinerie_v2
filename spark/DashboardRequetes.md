# Requêtes des tableaux de bord Grafana

Ce document détaille les requêtes SQL utilisées dans les tableaux de bord Grafana de notre pipeline de données IoT. Ces requêtes permettent de visualiser les métriques de performance et les données des capteurs.

## Tableau de bord : KPI Dashboard (kpi_dashboard.json)

### 1. Latence par étape du pipeline

**Type de visualisation** : Graphique temporel (Time series)

**Description** : Affiche la latence pour chaque étape du pipeline (MQTT→Kafka, Kafka→Spark, Spark→TimescaleDB) ainsi que la latence totale au fil du temps.

**Requête SQL** :
```sql
SELECT
  time,
  value_ms,
  metric_name as metric
FROM
  pipeline_kpi
WHERE
  time > NOW() - INTERVAL '10 minute' AND
  metric_name IN ('mqtt_to_kafka', 'kafka_to_spark', 'spark_to_timescaledb', 'total_pipeline_latency')
ORDER BY
  time ASC
```

### 2. Latence moyenne totale (2 dernières minutes)

**Type de visualisation** : Statistique (Stat panel)

**Description** : Affiche la latence moyenne de bout en bout du pipeline sur les 2 dernières minutes, avec un code couleur (vert < 500ms, jaune 500-1000ms, rouge > 1000ms).

**Requête SQL** :
```sql
SELECT
  AVG(value_ms) as avg_latency
FROM
  pipeline_kpi
WHERE
  time > NOW() - INTERVAL '2 minutes' AND
  metric_name = 'total_pipeline_latency'
```

### 3. Latence P95 (2 dernières minutes)

**Type de visualisation** : Statistique (Stat panel)

**Description** : Affiche le 95e percentile de la latence totale sur les 2 dernières minutes, indiquant la performance pour 95% des messages.

**Requête SQL** :
```sql
SELECT
  percentile_cont(0.95) WITHIN GROUP (ORDER BY value_ms) as p95_latency
FROM
  pipeline_kpi
WHERE
  time > NOW() - INTERVAL '2 minutes' AND
  metric_name = 'total_pipeline_latency'
```

### 4. Tableau des métriques de latence par étape

**Type de visualisation** : Tableau (Table)

**Description** : Présente les statistiques détaillées de latence pour chaque étape du pipeline, notamment la moyenne, le minimum, le maximum et les percentiles P95/P99.

**Requête SQL** :
```sql
SELECT * FROM get_pipeline_latency_stats('10 minutes'::interval)
```

### 5. Nombre de messages traités

**Type de visualisation** : Jauge (Gauge)

**Description** : Indique le nombre total de messages traités dans les 5 dernières minutes.

**Requête SQL** :
```sql
SELECT
  COUNT(*) as messages_count
FROM
  sensor_data
WHERE
  time > NOW() - INTERVAL '5 minutes'
```

## Tableau de bord : Pipeline Performance (pipeline_performance.json)

### 1. Température et humidité en temps réel

**Type de visualisation** : Graphique temporel (Time series)

**Description** : Affiche les valeurs de température et d'humidité des capteurs au fil du temps.

**Requête SQL** :
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
ORDER BY
  time ASC
```

### 2. Métriques de traitement Spark

**Type de visualisation** : Graphique temporel (Time series)

**Description** : Montre les temps de traitement des lots Spark, permettant d'identifier les variations de performance du traitement.

**Requête SQL** :
```sql
SELECT
  time,
  processing_time,
  avg_processing_time
FROM
  processing_metrics
WHERE
  time > NOW() - INTERVAL '30 minutes'
ORDER BY
  time ASC
```

### 3. Distribution des températures

**Type de visualisation** : Histogramme (Histogram)

**Description** : Affiche la distribution des valeurs de température sur une période, permettant d'identifier les anomalies.

**Requête SQL** :
```sql
SELECT
  temperature,
  COUNT(*) as count
FROM
  sensor_data
WHERE
  time > NOW() - INTERVAL '1 hour'
GROUP BY
  temperature
ORDER BY
  temperature
```

### 4. Résumé des métriques de capteurs par heure

**Type de visualisation** : Tableau (Table)

**Description** : Présente un résumé horaire des données des capteurs avec des statistiques d'agrégation.

**Requête SQL** :
```sql
SELECT
  time_bucket('1 hour', time) as hour,
  sensor_id,
  AVG(temperature) as avg_temp,
  MIN(temperature) as min_temp,
  MAX(temperature) as max_temp,
  AVG(humidity) as avg_humidity,
  COUNT(*) as readings_count
FROM
  sensor_data
WHERE
  time > NOW() - INTERVAL '24 hours'
GROUP BY
  hour, sensor_id
ORDER BY
  hour DESC, sensor_id
```

### 5. Heatmap de performance du pipeline

**Type de visualisation** : Carte de chaleur (Heatmap)

**Description** : Visualise les variations de latence du pipeline au fil du temps sous forme de carte de chaleur, facilitant l'identification des tendances et des modèles.

**Requête SQL** :
```sql
SELECT
  time_bucket('10 seconds', time) as time_interval,
  metric_name,
  AVG(value_ms) as avg_latency
FROM
  pipeline_kpi
WHERE
  time > NOW() - INTERVAL '1 hour'
GROUP BY
  time_interval, metric_name
ORDER BY
  time_interval, metric_name
```

## Comment modifier ces requêtes

Pour modifier ces requêtes dans Grafana :

1. Accédez au tableau de bord concerné
2. Cliquez sur le titre d'un panneau
3. Sélectionnez "Edit"
4. Allez dans l'onglet "Query"
5. Modifiez la requête SQL selon vos besoins
6. Cliquez sur "Apply" pour appliquer les modifications

## Optimisations possibles

- Ajustez les intervalles de temps (`INTERVAL '10 minute'`, etc.) en fonction de votre fréquence d'acquisition de données
- Utilisez la fonction `time_bucket()` de TimescaleDB pour des agrégations temporelles efficaces
- Ajoutez des filtres supplémentaires par capteur ou par type de métrique si nécessaire
- Créez des vues matérialisées continues pour les requêtes fréquemment utilisées 