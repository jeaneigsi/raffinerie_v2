# Requêtes pour le Tableau de Bord IoT Grafana

Ce document contient toutes les requêtes SQL nécessaires pour créer un tableau de bord complet pour la surveillance des capteurs IoT.

## 1. Température et humidité en temps réel

**Titre**: Température et humidité en temps réel  
**Description**: Affiche les valeurs de température et d'humidité capturées par les capteurs au fil du temps.  
**Visualisation**: Time series (Séries temporelles)

```sql
SELECT
  time as time,
  temperature,
  humidity
FROM
  sensor_data
WHERE
  $__timeFilter(time)
ORDER BY time
```

## 2. Valeurs actuelles

**Titre**: Valeurs actuelles  
**Description**: Affiche les dernières valeurs mesurées pour la température et l'humidité.  
**Visualisation**: Stat panel (Panneau statistique)  

```sql
SELECT
  temperature,
  humidity,
  time
FROM
  sensor_data
ORDER BY time DESC
LIMIT 1
```

## 3. Moyenne, maximum et minimum

**Titre**: Statistiques sur la période  
**Description**: Fournit un résumé statistique des mesures sur la période sélectionnée.  
**Visualisation**: Gauge ou Table (Jauge ou Tableau)  

```sql
SELECT
  AVG(temperature) as avg_temp,
  MAX(temperature) as max_temp,
  MIN(temperature) as min_temp,
  AVG(humidity) as avg_hum,
  MAX(humidity) as max_hum,
  MIN(humidity) as min_hum
FROM
  sensor_data
WHERE
  $__timeFilter(time)
```

## 4. Moyennes horaires

**Titre**: Moyennes horaires  
**Description**: Calcule et affiche les moyennes de température et d'humidité par heure pour identifier les tendances.  
**Visualisation**: Time series (Séries temporelles)  

```sql
SELECT
  time_bucket('1 hour', time) AS hour,
  AVG(temperature) as avg_temperature,
  AVG(humidity) as avg_humidity
FROM
  sensor_data
WHERE
  $__timeFilter(time)
GROUP BY hour
ORDER BY hour
```

## 5. Histogramme en temps réel des températures

**Titre**: Distribution des températures en temps réel  
**Description**: Montre la distribution des valeurs de température regroupées par minute.  
**Visualisation**: Bar chart (Graphique à barres)  

```sql
SELECT 
  time_bucket('1 minute', time) as minute,
  FLOOR((temperature - 15) / ((35 - 15) / 10)) + 1 as temp_range,
  COUNT(*) as count
FROM 
  sensor_data
WHERE 
  $__timeFilter(time)
  AND temperature BETWEEN 15 AND 35
GROUP BY 
  minute, temp_range
ORDER BY 
  minute DESC, temp_range
LIMIT 100
```

## 6. Histogramme en temps réel de l'humidité

**Titre**: Distribution de l'humidité en temps réel  
**Description**: Montre la distribution des valeurs d'humidité regroupées par minute.  
**Visualisation**: Bar chart (Graphique à barres)  

```sql
SELECT 
  time_bucket('1 minute', time) as minute,
  FLOOR((humidity - 30) / ((90 - 30) / 10)) + 1 as hum_range,
  COUNT(*) as count
FROM 
  sensor_data
WHERE 
  $__timeFilter(time)
  AND humidity BETWEEN 30 AND 90
GROUP BY 
  minute, hum_range
ORDER BY 
  minute DESC, hum_range
LIMIT 100
```

## 7. Tendance sur les dernières heures

**Titre**: Tendance des dernières heures  
**Description**: Affiche l'évolution des tendances avec des moyennes par tranches de 15 minutes.  
**Visualisation**: Time series (Séries temporelles)  

```sql
SELECT
  time_bucket('15 minutes', time) AS interval,
  AVG(temperature) as avg_temperature,
  AVG(humidity) as avg_humidity
FROM
  sensor_data
WHERE
  time > NOW() - INTERVAL '6 hours'
GROUP BY interval
ORDER BY interval
```

## 8. Alertes et valeurs extrêmes

**Titre**: Valeurs extrêmes détectées  
**Description**: Identifie les moments où les capteurs ont détecté des valeurs extrêmes.  
**Visualisation**: Table (Tableau)  

```sql
SELECT
  time,
  temperature,
  humidity
FROM
  sensor_data
WHERE
  $__timeFilter(time)
  AND (temperature > 28 OR temperature < 20 OR humidity > 75 OR humidity < 40)
ORDER BY time DESC
LIMIT 20
```

## 9. Heatmap de corrélation température/humidité

**Titre**: Corrélation Température-Humidité  
**Description**: Analyse la relation entre température et humidité sous forme de heatmap.  
**Visualisation**: Heatmap  

```sql
SELECT
  FLOOR(temperature) as temp_bucket,
  FLOOR(humidity) as hum_bucket,
  COUNT(*) as count
FROM
  sensor_data
WHERE
  $__timeFilter(time)
GROUP BY
  temp_bucket, hum_bucket
ORDER BY
  temp_bucket, hum_bucket
```

## 10. Nombre total de mesures

**Titre**: Volume de données  
**Description**: Affiche le nombre total de mesures collectées dans la période sélectionnée.  
**Visualisation**: Stat panel (Panneau statistique)  

```sql
SELECT
  COUNT(*) as total_measurements
FROM
  sensor_data
WHERE
  $__timeFilter(time)
```

## 11. Variations récentes

**Titre**: Variations des 5 dernières minutes  
**Description**: Affiche les variations de température et d'humidité durant les 5 dernières minutes, mise à jour en temps réel.  
**Visualisation**: Stat panel (Panneau statistique)  

```sql
SELECT
  ROUND((MAX(temperature) - MIN(temperature))::numeric, 1) as temp_variation,
  ROUND((MAX(humidity) - MIN(humidity))::numeric, 1) as hum_variation
FROM
  sensor_data
WHERE
  time > NOW() - INTERVAL '5 minutes'
```

## 12. Taux de changement

**Titre**: Taux de changement en temps réel  
**Description**: Calcule le taux de changement (dérivée) de la température et de l'humidité pour détecter les variations rapides.  
**Visualisation**: Time series (Séries temporelles)  

```sql
WITH timestamped_data AS (
  SELECT 
    time,
    temperature,
    humidity,
    LAG(temperature) OVER (ORDER BY time) as prev_temp,
    LAG(humidity) OVER (ORDER BY time) as prev_hum,
    LAG(time) OVER (ORDER BY time) as prev_time
  FROM 
    sensor_data
  WHERE 
    $__timeFilter(time)
)
SELECT
  time,
  CASE 
    WHEN EXTRACT(EPOCH FROM (time - prev_time)) > 0 
    THEN (temperature - prev_temp) / EXTRACT(EPOCH FROM (time - prev_time)) 
    ELSE 0 
  END as temp_change_rate,
  CASE 
    WHEN EXTRACT(EPOCH FROM (time - prev_time)) > 0 
    THEN (humidity - prev_hum) / EXTRACT(EPOCH FROM (time - prev_time)) 
    ELSE 0 
  END as hum_change_rate
FROM
  timestamped_data
WHERE
  prev_time IS NOT NULL
ORDER BY
  time
```

## 13. Détection d'anomalies simples

**Titre**: Détection d'anomalies en temps réel  
**Description**: Identifie les mesures qui s'écartent significativement de la moyenne mobile.  
**Visualisation**: Table (Tableau) ou Time series (Séries temporelles)  

```sql
WITH stats AS (
  SELECT
    time,
    temperature,
    humidity,
    AVG(temperature) OVER (ORDER BY time ROWS BETWEEN 10 PRECEDING AND CURRENT ROW) as avg_temp_10,
    AVG(humidity) OVER (ORDER BY time ROWS BETWEEN 10 PRECEDING AND CURRENT ROW) as avg_hum_10,
    STDDEV(temperature) OVER (ORDER BY time ROWS BETWEEN 10 PRECEDING AND CURRENT ROW) as stddev_temp_10,
    STDDEV(humidity) OVER (ORDER BY time ROWS BETWEEN 10 PRECEDING AND CURRENT ROW) as stddev_hum_10
  FROM
    sensor_data
  WHERE
    $__timeFilter(time)
)
SELECT
  time,
  temperature,
  humidity,
  CASE
    WHEN ABS(temperature - avg_temp_10) > 2 * stddev_temp_10 THEN 'Anomalie de température'
    WHEN ABS(humidity - avg_hum_10) > 2 * stddev_hum_10 THEN 'Anomalie d''humidité'
    ELSE 'Normal'
  END as status
FROM
  stats
WHERE
  ABS(temperature - avg_temp_10) > 2 * stddev_temp_10 OR
  ABS(humidity - avg_hum_10) > 2 * stddev_hum_10
ORDER BY
  time DESC
LIMIT 10
```

## 14. Dernières mesures en temps réel

**Titre**: Flux de données en temps réel  
**Description**: Affiche un flux des 10 dernières mesures, idéal pour le monitoring en temps réel.  
**Visualisation**: Table (Tableau)  

```sql
SELECT
  time,
  temperature,
  humidity,
  sensor_id,
  EXTRACT(EPOCH FROM (NOW() - time)) as seconds_ago
FROM
  sensor_data
ORDER BY
  time DESC
LIMIT 10
```

## 15. Vitesse d'acquisition des données

**Titre**: Fréquence d'acquisition  
**Description**: Mesure la fréquence d'acquisition des données par minute, utile pour vérifier que les capteurs fonctionnent correctement.  
**Visualisation**: Gauge (Jauge) ou Time series (Séries temporelles)  

```sql
SELECT
  time_bucket('1 minute', time) AS minute,
  COUNT(*) as readings_per_minute
FROM
  sensor_data
WHERE
  time > NOW() - INTERVAL '30 minutes'
GROUP BY
  minute
ORDER BY
  minute DESC
``` 