# Pipeline de traitement de données IoT avec Apache Spark

Ce projet implémente un pipeline de traitement de données IoT en temps réel utilisant Apache Spark Structured Streaming. Le pipeline collecte des données de capteurs depuis Kafka, les traite, puis les stocke à la fois dans TimescaleDB pour l'analyse en temps réel et dans MinIO (compatible S3) pour l'archivage à long terme.

## Architecture du système

L'architecture complète du système comprend les composants suivants :

```
Capteurs IoT → MQTT → Kafka → Spark → TimescaleDB & MinIO → Grafana
```

1. Les données des capteurs (température et humidité) sont publiées via MQTT
2. Un broker MQTT transmet les données à Kafka
3. Spark consomme les données de Kafka en streaming
4. Les données sont traitées et stockées simultanément dans TimescaleDB et MinIO
5. Grafana visualise les données et les métriques de performance en temps réel

## Application Spark (`spark_app.py`)

### Fonctionnalités principales

- **Lecture en streaming** : Consomme des données JSON depuis un topic Kafka
- **Traitement** : Parse, transforme et enrichit les données
- **Stockage double** : Écrit dans TimescaleDB (SQL) et MinIO (Parquet)
- **Métriques de performance** : Collecte et stocke des KPIs pour chaque étape du pipeline

### Métriques de performance collectées

L'application collecte quatre types de métriques de performance essentielles :

1. **MQTT → Kafka** : Temps de transmission des données des capteurs à Kafka
2. **Kafka → Spark** : Temps de traitement pour que Spark reçoive les données de Kafka
3. **Spark → TimescaleDB** : Temps de traitement et d'écriture dans TimescaleDB
4. **Total (bout en bout)** : Latence totale depuis la capture jusqu'au stockage

Ces métriques sont stockées dans la table `pipeline_kpi` de TimescaleDB, permettant une analyse historique et en temps réel des performances du pipeline.

## Structure de la base de données TimescaleDB

### Tables principales

- **sensor_data** : Stocke les mesures de température et d'humidité
- **pipeline_kpi** : Stocke les métriques de performance du pipeline
- **processing_metrics** : Stocke les statistiques détaillées sur le traitement Spark

### Fonctions d'analyse

- **get_pipeline_latency_stats(interval)** : Calcule les statistiques de latence (moyenne, min, max, percentiles) pour chaque étape du pipeline sur un intervalle donné

## Dépannage et solutions implémentées

### Problème 1 : Indentation incorrecte dans `write_to_timescaledb`

Le code original contenait des erreurs d'indentation qui empêchaient l'exécution correcte. Ces erreurs ont été corrigées en assurant une indentation cohérente dans toutes les fonctions.

### Problème 2 : Module `psycopg2` manquant

Le module `psycopg2` nécessaire pour la connexion directe à TimescaleDB n'était pas disponible dans le conteneur Spark. Solution :

1. Installation du module dans le conteneur : `docker exec spark-processor pip install psycopg2-binary`
2. Implémentation d'une détection de la disponibilité du module avec gestion gracieuse des cas où il est absent

### Problème 3 : Table `pipeline_kpi` inexistante

La fonction `get_pipeline_latency_stats` faisait référence à une table inexistante nommée `pipeline_latency`. Solution :

1. Modification de la fonction pour utiliser la table `pipeline_kpi` existante
2. Implémentation d'une vérification d'existence et création automatique des tables si nécessaire

## Comment utiliser

### Vérification des données

Pour vérifier que les données sont correctement stockées dans TimescaleDB :

```bash
# Vérifier les données des capteurs
docker exec timescaledb psql -U sensor_user -d sensordb -c "SELECT * FROM sensor_data ORDER BY time DESC LIMIT 10;"

# Vérifier les métriques de performance
docker exec timescaledb psql -U sensor_user -d sensordb -c "SELECT * FROM pipeline_kpi ORDER BY time DESC LIMIT 10;"

# Obtenir des statistiques de latence sur la dernière heure
docker exec timescaledb psql -U sensor_user -d sensordb -c "SELECT * FROM get_pipeline_latency_stats('1 hour'::interval);"
```

### Dépannage courant

- **Données manquantes dans TimescaleDB** : Vérifier la disponibilité de `psycopg2` avec `docker exec spark-processor pip list | grep psycopg2`
- **Erreurs dans les logs Spark** : Consulter les logs avec `docker logs spark-processor`
- **Problèmes de connexion à Kafka** : Vérifier que le service est actif avec `docker ps` et que le topic existe

## Tableau de bord Grafana

Un tableau de bord Grafana est configuré pour visualiser :

1. Les données des capteurs en temps réel
2. Les métriques de performance du pipeline
3. Les statistiques historiques de latence

Le tableau de bord utilise la fonction `get_pipeline_latency_stats` pour afficher des graphiques de performance détaillés.

## Améliorations futures

- Implémenter la capture de timestamps réels à chaque étape du pipeline
- Ajouter la détection d'anomalies sur les données des capteurs
- Optimiser les paramètres Spark pour un traitement plus rapide
- Ajouter plus de métriques pour une meilleure observabilité du système 