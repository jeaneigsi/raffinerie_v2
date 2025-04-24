# Pipeline de Données IoT pour Capteurs

Ce projet implémente une pipeline de données complète pour la collecte, le transport, le traitement et la visualisation des données de capteurs IoT, utilisant des technologies modernes de Big Data.

## Vue d'ensemble

Le projet simule des capteurs IoT publiant des données de température et d'humidité via MQTT, puis les traite avec Apache Kafka et Apache Spark, avant de les stocker dans TimescaleDB et MinIO (compatible S3) et de les visualiser avec Grafana.

![Architecture](architecture.md)

## Prérequis

- Docker et Docker Compose
- Python 3.8+ 
- pip (gestionnaire de paquets Python)
- Au moins 8 Go de RAM disponible pour exécuter l'ensemble des conteneurs

## Installation

1. Clonez ce dépôt :
```bash
git clone <votre-repo>
cd <votre-repo>
```

2. Créez et activez un environnement virtuel Python :
```bash
python -m venv env
source env/bin/activate  # Linux/Mac
env\Scripts\activate     # Windows
```

3. Installez les dépendances Python :
```bash
pip install -r requirements.txt
```

## Structure du projet

```
├── docker-compose.yml         # Configuration des services
├── requirements.txt           # Dépendances Python
├── architecture.md            # Description de l'architecture
├── mqtt_to_kafka.py           # Bridge MQTT vers Kafka
├── mqtt-source.json           # Configuration Kafka Connect
├── spark/
│   ├── spark_app.py           # Application Spark Streaming
│   └── Dockerfile             # Image Docker pour Spark
├── sensor_simulator/
│   ├── publisher.py           # Simulateur de capteurs
│   └── subscriber.py          # Client test pour vérifier les données
├── timescaledb/
│   └── init/                  # Scripts d'initialisation de la base
├── mosquitto/
│   └── config/                # Configuration du broker MQTT
├── grafana/
│   └── provisioning/          # Configuration des dashboards
└── kafka-connect/             # Connecteurs pour Kafka
```

## Démarrage

1. Lancez l'ensemble des services avec Docker Compose :
```bash
docker-compose up -d
```

2. Vérifiez que tous les services sont démarrés :
```bash
docker-compose ps
```

3. Démarrez le simulateur de capteurs :
```bash
python sensor_simulator/publisher.py
```

4. Pour tester la réception des données :
```bash
python sensor_simulator/subscriber.py
```

## Architecture des composants

### Simulateur de capteurs
- Génère des données simulées de température et d'humidité
- Publie sur le topic MQTT `sensors/data`

### Pipeline de données
1. **MQTT (Mosquitto)** : Broker de messages pour les données IoT
2. **Kafka & Zookeeper** : Système de messagerie distribué
3. **Kafka Connect** : Connecteur pour transférer les données MQTT vers Kafka
4. **Spark Streaming** : Traitement en temps réel des données
5. **Stockage** :
   - **TimescaleDB** : Base de données pour séries temporelles
   - **MinIO** : Stockage compatible S3 pour les données brutes

### Visualisation
- **Grafana** : Interface de visualisation accessible sur http://localhost:3000
  - Identifiant : admin
  - Mot de passe : admin

## Format des données

Le simulateur publie des données au format JSON :
```json
{
  "temperature": 25.3,
  "humidity": 65.4,
  "timestamp": 1712921712.123
}
```

## Interfaces Web

- **Grafana** : http://localhost:3000
  - Identifiant : admin
  - Mot de passe : admin
- **MinIO Console** : http://localhost:9001
  - Identifiant : minioadmin
  - Mot de passe : minioadmin
- **Kafka Connect REST** : http://localhost:8083
- **Kafka UI** : http://localhost:8080
- **pgAdmin** : http://localhost:5050
  - Email : admin@admin.com
  - Mot de passe : admin

Pour configurer pgAdmin avec TimescaleDB :
1. Connectez-vous à pgAdmin
2. Cliquez sur "Add New Server"
3. Entrez un nom (ex: "TimescaleDB")
4. Dans l'onglet "Connection", entrez :
   - Host: timescaledb
   - Port: 5432
   - Database: sensordb
   - Username: sensor_user
   - Password: sensor_pass

## Arrêt

1. Pour arrêter le simulateur : Ctrl+C
2. Pour arrêter tous les services :
```bash
docker-compose down
```

## Documentation

Pour plus de détails sur l'architecture et le fonctionnement du système, consultez le fichier [architecture.md](architecture.md).

## Problèmes connus

Consultez le fichier [PROBLEMES_RENCONTRES.md](PROBLEMES_RENCONTRES.md) pour connaître les problèmes courants et leurs solutions. 