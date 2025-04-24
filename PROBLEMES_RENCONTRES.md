# Problèmes rencontrés et solutions

## 1. Compatibilité des dépendances Spark-Kafka

**Problème** : Erreur `NoClassDefFoundError` pour `org/apache/spark/kafka010/KafkaConfigUpdater` lors de l'exécution de Spark.

**Solution** : Ajout des dépendances Kafka correctes dans le Dockerfile de Spark :
```dockerfile
RUN cd /opt/bitnami/spark/jars && \
    wget https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.4.0/spark-sql-kafka-0-10_2.12-3.4.0.jar && \
    wget https://repo1.maven.org/maven2/org/apache/spark/spark-token-provider-kafka-0-10_2.12/3.4.0/spark-token-provider-kafka-0-10_2.12-3.4.0.jar && \
    wget https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/3.3.2/kafka-clients-3.3.2.jar && \
    wget https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/2.11.1/commons-pool2-2.11.1.jar && \
    wget https://repo1.maven.org/maven2/org/apache/spark/spark-streaming-kafka-0-10_2.12/3.4.0/spark-streaming-kafka-0-10_2.12-3.4.0.jar
```

## 2. Communication entre conteneurs Docker

**Problème** : Impossible de résoudre le nom d'hôte `kafka` depuis Spark (`Couldn't resolve server kafka:29092`).

**Solution** : Assurer que tous les services sont sur le même réseau Docker et peuvent communiquer entre eux. Nous avons vérifié la configuration des ports et des réseaux dans docker-compose.yml.

## 3. Problème de topic Kafka inexistant

**Problème** : Erreur `UnknownTopicOrPartitionException` car le topic Kafka n'existait pas.

**Solution** : Création manuelle du topic Kafka avant de démarrer Spark :
```bash
docker-compose exec kafka kafka-topics --create --topic sensor_topic --partitions 1 --replication-factor 1 --bootstrap-server kafka:29092
```

## 4. Encodage base64 des messages MQTT dans Kafka

**Problème** : Les messages envoyés par MQTT étaient encodés en base64 dans Kafka, ce qui compliquait le traitement par Spark.

**Solution** : Modification du script Spark pour décoder correctement les messages base64 :
```python
parsed_df = df.selectExpr("CAST(value AS STRING) as encoded_json") \
    .select(
        # Décodage base64
        unbase64(col("encoded_json").substr(lit(2), length(col("encoded_json"))-2)).cast("string").alias("json_str")
    ) \
    .select(from_json(col("json_str"), schema).alias("data")) \
    .select("data.*")
```

## 5. Problèmes d'écriture dans MinIO

**Problème** : Les fichiers Parquet n'étaient pas créés régulièrement dans MinIO.

**Solution** : 
1. Ajout des dépendances S3A dans le Dockerfile Spark :
```dockerfile
RUN cd /opt/bitnami/spark/jars && \
    wget https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar && \
    wget https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar && \
    wget https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-common/3.3.4/hadoop-common-3.3.4.jar
```

2. Configuration optimisée pour l'écriture dans MinIO :
```python
minio_query = parsed_df \
    .writeStream \
    .format("parquet") \
    .option("path", "s3a://sensordata/data/") \
    .option("checkpointLocation", checkpoint_dir) \
    .outputMode("append") \
    .start()
```

## 6. Configuration TimescaleDB et type JSONB

**Problème** : Erreur lors de l'insertion dans TimescaleDB car le format des données JSON n'était pas compatible avec le type JSONB de PostgreSQL.

**Solution** : Utilisation de `create_map` pour générer un objet Spark qui sera correctement converti en JSONB :
```python
raw_data_expr = create_map(
    lit("temperature"), col("temperature"),
    lit("humidity"), col("humidity"),
    lit("timestamp"), col("timestamp")
)
batch_df = batch_df.withColumn("raw_data", raw_data_expr)
```

## 7. Gestion des checkpoints et redémarrages de Spark

**Problème** : Des erreurs survenaient lors du redémarrage de Spark à cause des checkpoints.

**Solution** : Utilisation de répertoires de checkpoint uniques générés dynamiquement :
```python
checkpoint_dir = "/tmp/checkpoints-" + str(uuid.uuid4())
```

## 8. Surveillance des streams Spark

**Problème** : Difficultés à diagnostiquer les problèmes de streaming.

**Solution** : Ajout d'une surveillance active des streams avec logs détaillés :
```python
while minio_query.isActive and timescaledb_query.isActive:
    minio_status = minio_query.status
    timescaledb_status = timescaledb_query.status
    print(f"Statut du stream MinIO: {minio_status}")
    print(f"Statut du stream TimescaleDB: {timescaledb_status}")
    time.sleep(10)
```

## 9. Problèmes de connexion au broker MQTT

**Problème** : Erreur de connexion au broker MQTT depuis le publisher (`Connection refused`).

**Solution** : Vérification que le conteneur Mosquitto était bien démarré et accessible, puis ajout d'un mécanisme de retry dans le script publisher :
```python
max_retries = 5
retry_count = 0
while retry_count < max_retries:
    if connect_mqtt():
        break
    print(f"Tentative de reconnexion dans 5 secondes... ({retry_count + 1}/{max_retries})")
    time.sleep(5)
    retry_count += 1
```

## 10. Configuration automatique des sources de données Grafana

**Problème** : Nécessité de configurer manuellement les sources de données dans Grafana.

**Solution** : Utilisation du système de provisionnement Grafana avec un fichier YAML :
```yaml
apiVersion: 1
datasources:
  - name: TimescaleDB
    type: postgres
    url: timescaledb:5432
    user: sensor_user
    secureJsonData:
      password: 'sensor_pass'
    jsonData:
      database: sensordb
      sslmode: 'disable'
      timescaledb: true
``` 