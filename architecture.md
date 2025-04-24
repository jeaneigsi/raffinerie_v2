# Architecture du Projet IoT Data Pipeline

Ce document décrit l'architecture complète du projet de pipeline de données IoT, qui comprend la collecte, le transport, le traitement, le stockage, la visualisation et le monitoring des données de capteurs.

## Vue d'ensemble

Le projet met en œuvre une pipeline de données complète pour les capteurs IoT :

1. **Génération de données** : Simulation de capteurs IoT produisant des données de température et d'humidité
2. **Transport de données** : Utilisation de MQTT et Kafka pour le transport des messages
3. **Traitement des données** : Traitement en temps réel avec Apache Spark
4. **Stockage des données** : Stockage dans TimescaleDB (base de données temporelle) et MinIO (stockage d'objets S3)
5. **Visualisation** : Tableaux de bord avec Grafana
6. **Monitoring** : Surveillance complète du pipeline avec Spark UI, Kafka UI, et outils de monitoring personnalisés

## Architecture des composants

```
+-------------------+     +-------------------+     +-------------------+     
| Sensor Simulator  |---->|  MQTT (Mosquitto) |---->|  Kafka Connect    |
| (Python)          |     | (Broker)          |     | (Connecteur)      |
| - publisher.py    |     | - config/         |     | - connect-mqtt/   |
| - subscriber.py   |     | - data/           |     | - connect-kafka/  |
+-------------------+     | - log/            |     +-------------------+
                         +-------------------+           |
                                                           |
                                                           v
                                                     +-------------------+
                                                     | Kafka (+ Zookeeper)|
                                                     | (Message Broker)   |
                                                     | - topics/         |
                                                     | - partitions/     |
                                                     +-------------------+
                                                           |
                                                           |
+-------------------+     +-------------------+           |
|      MinIO        |<----|    Spark App      |<----------
| (Stockage S3)     |     |  (Traitement)     |           
| - buckets/        |     | - spark_app.py    |           
| - objects/        |     | - Dockerfile      |           
+-------------------+     +-------------------+           
                                    |             +-------------------+
                                    +------------>|    TimescaleDB    |
                                                  | (Base de données) |
                                                  | - tables/         |
                                                  | - schemas/        |
                                                  +-------------------+
                                                        |
                                                        v
                                                +-------------------+
                                                |      Grafana      |
                                                | (Visualisation)   |
                                                | - dashboards/     |
                                                | - datasources/    |
                                                +-------------------+

+-------------------+     +-------------------+     +-------------------+
|    Spark UI       |     |    Kafka UI       |     |    MinIO Console  |
| (Monitoring)      |     |  (Monitoring)     |     |  (Monitoring)     |
| - jobs/           |     | - topics/         |     | - buckets/        |
| - stages/         |     | - brokers/        |     | - objects/        |
+-------------------+     +-------------------+     +-------------------+

+-------------------+     +-------------------+
|     pgAdmin       |     |    Prometheus     |
| (Admin DB)        |     |  (Monitoring)     |
| - queries/        |     | - metrics/        |
| - schemas/        |     | - alerts/         |
+-------------------+     +-------------------+
```

## Structure des fichiers et répertoires

### 1. Simulateur de capteurs
```
sensor_simulator/
├── publisher.py          # Génération des données de capteurs
│   - Port MQTT: 1883
│   - Topic: sensors/data
│   - Format: JSON
│   - Fréquence: 1 message/seconde
├── subscriber.py         # Réception des données
└── requirements.txt      # Dépendances Python
    - paho-mqtt
    - python-dotenv
```

### 2. Configuration MQTT
```
mosquitto/
├── config/
│   └── mosquitto.conf    # Configuration du broker MQTT
│       - Port: 1883
│       - Persistence: true
│       - Log: debug
├── data/                 # Données persistantes
└── log/                 # Logs du broker
```

### 3. Kafka Connect
```
kafka-connect/
├── connect-mqtt/        # Configuration du connecteur MQTT
│   - Source: MQTT
│   - Target: Kafka
│   - Topics: sensors/data -> sensor-data-topic
├── connect-kafka/       # Configuration du connecteur Kafka
└── configuration/
    └── connect-standalone.properties
        - bootstrap.servers: kafka:29092
        - key.converter: org.apache.kafka.connect.json.JsonConverter
        - value.converter: org.apache.kafka.connect.json.JsonConverter
```

### 4. Application Spark
```
spark/
├── spark_app.py         # Application de traitement
│   - Mode: Streaming
│   - Batch Interval: 1 seconde
│   - Processing: 
│     * Filtrage des données
│     * Agrégation temporelle
│     * Enrichissement
├── Dockerfile           # Configuration du conteneur
│   - Base: python:3.9
│   - Spark: 3.3.0
│   - Ports: 4040 (UI)
└── requirements.txt     # Dépendances Python
    - pyspark
    - psycopg2
    - minio
```

### 5. Configuration TimescaleDB
```
timescaledb/
├── init/
│   └── init.sql        # Scripts d'initialisation
│       - Database: sensordb
│       - User: sensor_user
│       - Tables:
│         * sensor_data
│         * sensor_metadata
│       - Hypertables: sensor_data
├── data/               # Données persistantes
└── configuration/
    └── postgresql.conf
        - Port: 5432
        - Memory: 2GB
        - Connections: 100
```

### 6. Configuration Grafana
```
grafana/
├── provisioning/
│   ├── dashboards/     # Tableaux de bord
│   │   - IoT Overview
│   │   - Sensor Metrics
│   │   - System Health
│   └── datasources/    # Sources de données
│       - TimescaleDB
│       - Prometheus
├── data/              # Données persistantes
└── configuration/
    └── grafana.ini
        - Port: 3000
        - Auth: admin/admin
```

### 7. Configuration MinIO
```
minio/
├── data/              # Données persistantes S3
└── configuration/
    └── config.json
        - Port: 9000 (API)
        - Port: 9001 (Console)
        - Buckets:
          * sensordata
          * processed-data
```

### 8. Monitoring
```
monitoring/
├── prometheus/
│   ├── prometheus.yml  # Configuration Prometheus
│   │   - Port: 9090
│   │   - Scrape Interval: 15s
│   │   - Targets:
│   │     * Spark
│   │     * Kafka
│   │     * TimescaleDB
│   └── alerts/         # Règles d'alertes
│       - High Latency
│       - Error Rate
│       - Resource Usage
└── grafana/
    └── dashboards/     # Tableaux de bord de monitoring
        - System Metrics
        - Pipeline Health
        - Resource Usage
```

## Description des composants

### 1. Simulateur de capteurs
- **Fichiers** : `sensor_simulator/publisher.py`, `sensor_simulator/subscriber.py`
- **Fonction** : Génère des données simulées de température et d'humidité
- **Technologies** : Python, Paho-MQTT
- **Monitoring** : Logs de génération de données et métriques de performance

### 2. Transport de messages
- **MQTT (Mosquitto)** :
  - Broker de messages léger pour IoT
  - Reçoit les données des capteurs
  - Monitoring via logs et métriques de connexion

- **Kafka + Zookeeper** :
  - Système de messagerie distribué à haut débit
  - Utilisé comme couche intermédiaire pour scaling
  - Monitoring via Kafka UI (http://localhost:8080)
  
- **Kafka Connect** :
  - Connecteur MQTT pour Kafka
  - Transfère les données du topic MQTT vers Kafka
  - Monitoring des connecteurs et des erreurs

### 3. Traitement des données
- **Spark Application** :
  - **Fichier** : `spark/spark_app.py`
  - **Fonction** : Traite les données en streaming depuis Kafka
  - **Opérations** : 
    - Lecture des données Kafka
    - Transformation et enrichissement
    - Écriture vers TimescaleDB et MinIO
  - **Monitoring** : 
    - Spark UI (http://localhost:4040)
    - Métriques de performance
    - Logs de traitement

### 4. Stockage des données
- **TimescaleDB** :
  - Base de données PostgreSQL optimisée pour les séries temporelles
  - Stocke les données structurées avec horodatage
  - Monitoring via pgAdmin et requêtes de performance
  
- **MinIO** :
  - Compatible avec l'API Amazon S3
  - Stockage d'objets pour les données brutes et transformées au format Parquet
  - Monitoring via MinIO Console (http://localhost:9001)

### 5. Visualisation et Monitoring
- **Grafana** :
  - Tableaux de bord pour la visualisation des données
  - Connexion directe à TimescaleDB
  - Panels de monitoring personnalisés
  - URL : http://localhost:3000

- **pgAdmin** :
  - Interface d'administration pour TimescaleDB
  - Exécution de requêtes de monitoring
  - URL : http://localhost:5050

## Flux de données

1. Le simulateur génère des données et les publie sur le topic MQTT `sensors/data`
2. Kafka Connect capture ces messages et les transfère vers le topic Kafka `sensor-data-topic`
3. L'application Spark lit le flux de données depuis Kafka
4. Spark traite les données et les écrit simultanément vers :
   - TimescaleDB pour l'analyse et la visualisation en temps réel
   - MinIO (S3) pour le stockage à long terme
5. TimescaleDB stocke les données traitées
6. Grafana lit les données directement depuis TimescaleDB pour la visualisation
7. Les outils de monitoring (Spark UI, Kafka UI, MinIO Console) surveillent le pipeline en temps réel

## Monitoring du Pipeline

### 1. Métriques clés surveillées
- Taux d'ingestion de données
- Latences de traitement
- Performance de stockage
- Intégrité des données
- Utilisation des ressources

### 2. Outils de monitoring
- **Spark UI** (http://localhost:4040) :
  - Jobs et stages Spark
  - Métriques d'exécution
  - DAGs de traitement

- **Kafka UI** (http://localhost:8080) :
  - Topics et messages
  - Performance des brokers
  - État des connecteurs

- **MinIO Console** (http://localhost:9001) :
  - Stockage S3
  - Objets et buckets
  - Performance de stockage

- **pgAdmin** (http://localhost:5050) :
  - Requêtes de monitoring
  - Performance de la base de données
  - Intégrité des données

### 3. Tableaux de bord Grafana
- État du système
- Métriques de performance
- Visualisation des données
- Alertes et notifications

## Déploiement

L'ensemble du système est conteneurisé avec Docker et orchestré via Docker Compose, ce qui facilite le déploiement et garantit la cohérence des environnements. Chaque composant est configuré avec des paramètres de monitoring appropriés pour assurer la visibilité complète du pipeline.

## Détails techniques des composants

### 1. Simulateur de capteurs
```
sensor_simulator/
├── publisher.py          # Génération des données de capteurs
│   - Port MQTT: 1883
│   - Topic: sensors/data
│   - Format: JSON
│   - Fréquence: 1 message/seconde
├── subscriber.py         # Réception des données
└── requirements.txt      # Dépendances Python
    - paho-mqtt
    - python-dotenv
```

### 2. Configuration MQTT
```
mosquitto/
├── config/
│   └── mosquitto.conf    # Configuration du broker MQTT
│       - Port: 1883
│       - Persistence: true
│       - Log: debug
├── data/                 # Données persistantes
└── log/                 # Logs du broker
```

### 3. Kafka Connect
```
kafka-connect/
├── connect-mqtt/        # Configuration du connecteur MQTT
│   - Source: MQTT
│   - Target: Kafka
│   - Topics: sensors/data -> sensor-data-topic
├── connect-kafka/       # Configuration du connecteur Kafka
└── configuration/
    └── connect-standalone.properties
        - bootstrap.servers: kafka:29092
        - key.converter: org.apache.kafka.connect.json.JsonConverter
        - value.converter: org.apache.kafka.connect.json.JsonConverter
```

### 4. Application Spark
```
spark/
├── spark_app.py         # Application de traitement
│   - Mode: Streaming
│   - Batch Interval: 1 seconde
│   - Processing: 
│     * Filtrage des données
│     * Agrégation temporelle
│     * Enrichissement
├── Dockerfile           # Configuration du conteneur
│   - Base: python:3.9
│   - Spark: 3.3.0
│   - Ports: 4040 (UI)
└── requirements.txt     # Dépendances Python
    - pyspark
    - psycopg2
    - minio
```

### 5. Configuration TimescaleDB
```
timescaledb/
├── init/
│   └── init.sql        # Scripts d'initialisation
│       - Database: sensordb
│       - User: sensor_user
│       - Tables:
│         * sensor_data
│         * sensor_metadata
│       - Hypertables: sensor_data
├── data/               # Données persistantes
└── configuration/
    └── postgresql.conf
        - Port: 5432
        - Memory: 2GB
        - Connections: 100
```

### 6. Configuration Grafana
```
grafana/
├── provisioning/
│   ├── dashboards/     # Tableaux de bord
│   │   - IoT Overview
│   │   - Sensor Metrics
│   │   - System Health
│   └── datasources/    # Sources de données
│       - TimescaleDB
│       - Prometheus
├── data/              # Données persistantes
└── configuration/
    └── grafana.ini
        - Port: 3000
        - Auth: admin/admin
```

### 7. Configuration MinIO
```
minio/
├── data/              # Données persistantes S3
└── configuration/
    └── config.json
        - Port: 9000 (API)
        - Port: 9001 (Console)
        - Buckets:
          * sensordata
          * processed-data
```

### 8. Monitoring
```
monitoring/
├── prometheus/
│   ├── prometheus.yml  # Configuration Prometheus
│   │   - Port: 9090
│   │   - Scrape Interval: 15s
│   │   - Targets:
│   │     * Spark
│   │     * Kafka
│   │     * TimescaleDB
│   └── alerts/         # Règles d'alertes
│       - High Latency
│       - Error Rate
│       - Resource Usage
└── grafana/
    └── dashboards/     # Tableaux de bord de monitoring
        - System Metrics
        - Pipeline Health
        - Resource Usage
```

## Variables d'environnement clés

```bash
# MQTT
MQTT_BROKER=mosquitto
MQTT_PORT=1883
MQTT_TOPIC=sensors/data

# Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:29092
KAFKA_TOPIC=sensor-data-topic

# Spark
SPARK_MASTER=local[*]
SPARK_UI_PORT=4040

# TimescaleDB
POSTGRES_DB=sensordb
POSTGRES_USER=sensor_user
POSTGRES_PASSWORD=sensor_pass
POSTGRES_HOST=timescaledb
POSTGRES_PORT=5432

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=sensordata

# Grafana
GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=admin
```

## Ports exposés

| Service      | Port | Description                    |
|--------------|------|--------------------------------|
| MQTT         | 1883 | Broker MQTT                    |
| Kafka        | 9092 | API Kafka                      |
| Kafka UI     | 8080 | Interface de monitoring Kafka   |
| Spark UI     | 4040 | Interface de monitoring Spark   |
| TimescaleDB  | 5432 | Base de données                |
| pgAdmin      | 5050 | Interface d'administration DB   |
| Grafana      | 3000 | Interface de visualisation      |
| MinIO API    | 9000 | API S3                         |
| MinIO Console| 9001 | Interface d'administration S3   |
| Prometheus   | 9090 | Serveur de métriques           |