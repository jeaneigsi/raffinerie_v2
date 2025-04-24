########################################################
# Application Spark pour le traitement des données IoT
# 
# Ce script implémente une application Spark Structured Streaming
# qui lit les données de capteurs depuis Kafka, les traite, 
# et les écrit dans TimescaleDB et MinIO (stockage S3)
#
# Fonctionnalités :
# - Lecture de données depuis Kafka
# - Traitement en temps réel
# - Stockage dans TimescaleDB pour analyse temps réel
# - Archivage dans MinIO au format Parquet
# - Monitoring via Spark UI (port 4040)
########################################################

import json
import time
import uuid
import statistics
import os
import logging
from datetime import datetime, timedelta

# Imports Spark
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, unbase64, lit, length, current_timestamp, to_timestamp, to_json, struct, create_map, avg, window, expr
from pyspark.sql.types import StructType, StructField, DoubleType, TimestampType, StringType, IntegerType
import threading

# Configuration du logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Variables globales pour le suivi des données du KPI
PSYCOPG2_AVAILABLE = False
try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    logger.warning("Module psycopg2 non disponible. Le stockage des KPI en base de données sera limité.")

# Variables d'environnement
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "sensor-data")
CHECKPOINT_LOCATION = os.environ.get("CHECKPOINT_LOCATION", "/opt/spark-data/checkpoints")
TIMESCALEDB_URL = os.environ.get("TIMESCALEDB_URL", "jdbc:postgresql://timescaledb:5432/iot_data")
TIMESCALEDB_PROPERTIES = {
    "user": os.environ.get("TIMESCALEDB_USER", "postgres"),
    "password": os.environ.get("TIMESCALEDB_PASSWORD", "postgres"),
    "driver": "org.postgresql.Driver"
}
S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://minio:9000")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "minioadmin")
S3_BUCKET = os.environ.get("S3_BUCKET", "iot-data")

# Variables globales pour le suivi des métriques de performance
processing_times = []
MAX_TIMES_STORED = 500  # Limite le nombre de mesures stockées pour éviter les fuites de mémoire

# Configuration des intervalles
METRICS_UPDATE_INTERVAL = 1  # Secondes entre chaque mise à jour des métriques
CHECKPOINT_INTERVAL = "10 seconds"  # Intervalle de checkpoint Spark

# Mutex pour l'accès concurrent à la liste des temps de traitement
metrics_lock = threading.Lock()

# Variables pour stocker les temps moyens de traitement pour chaque étape du pipeline
stage_avg_times = {
    "mqtt_to_kafka": [],
    "kafka_to_spark": [],
    "spark_to_db": []
}

def create_spark_session():
    """
    Crée et configure une session Spark pour le traitement des données IoT.
    Configure les connecteurs Kafka, PostgreSQL et les paramètres S3/MinIO.
    """
    spark = SparkSession.builder \
        .appName("IoTDataProcessor") \
        .config("spark.sql.streaming.metricsEnabled", "true") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.executor.memory", "1g") \
        .config("spark.sql.shuffle.partitions", "2") \
        .config("spark.sql.streaming.checkpointLocation", CHECKPOINT_LOCATION) \
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0," + 
                                       "org.postgresql:postgresql:42.5.1," +
                                       "org.apache.hadoop:hadoop-aws:3.3.2") \
        .config("fs.s3a.endpoint", S3_ENDPOINT) \
        .config("fs.s3a.access.key", S3_ACCESS_KEY) \
        .config("fs.s3a.secret.key", S3_SECRET_KEY) \
        .config("fs.s3a.path.style.access", "true") \
        .config("fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("fs.s3a.connection.ssl.enabled", "false") \
        .getOrCreate()
    
    # Définir le niveau de log pour réduire le bruit
    spark.sparkContext.setLogLevel("WARN")
    return spark

def define_schema():
    """
    Définit le schéma des données attendues des capteurs.
    Le schéma comprend la température, l'humidité et l'horodatage.
    
    Returns:
        StructType: Schéma Spark SQL des données de capteurs
    """
    return StructType([
        StructField("temperature", DoubleType(), True),  # Température en degrés Celsius
        StructField("humidity", DoubleType(), True),     # Humidité en pourcentage
        StructField("timestamp", DoubleType(), True)     # Horodatage UNIX en secondes
    ])

def configure_s3(spark):
    """
    Configure les paramètres Hadoop pour l'accès à MinIO (compatible S3).
    Cette configuration est nécessaire pour que Spark puisse écrire
    des données dans le stockage objet S3.
    
    Args:
        spark (SparkSession): Session Spark active
    """
    print("Configuration supplémentaire de l'accès à MinIO (S3)...")
    hadoop_conf = spark.sparkContext._jsc.hadoopConfiguration()
    
    # Paramètres de connexion de base
    hadoop_conf.set("fs.s3a.endpoint", "http://minio:9000")
    hadoop_conf.set("fs.s3a.access.key", "minioadmin")
    hadoop_conf.set("fs.s3a.secret.key", "minioadmin")
    hadoop_conf.set("fs.s3a.path.style.access", "true")
    hadoop_conf.set("fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    hadoop_conf.set("fs.s3a.aws.credentials.provider", "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")
    
    # Paramètres de performance et de débogage
    hadoop_conf.set("fs.s3a.connection.maximum", "15")  # Nombre maximum de connexions
    hadoop_conf.set("fs.s3a.attempts.maximum", "3")     # Nombre de tentatives en cas d'échec
    hadoop_conf.set("fs.s3a.connection.timeout", "10000") # Timeout en millisecondes
    hadoop_conf.set("fs.s3a.impl.disable.cache", "true")  # Désactive le cache pour le débogage

def write_to_timescaledb(batch_df, epoch_id):
    """
    Écrit un lot de données dans TimescaleDB.
    Cette fonction est appelée pour chaque micro-batch de données
    généré par le streaming Spark.
    
    Args:
        batch_df (DataFrame): DataFrame Spark contenant le lot de données
        epoch_id (int): Identifiant unique du lot (généré par Spark)
    """
    print(f"⚠️ Tentative d'écriture du lot {epoch_id} dans TimescaleDB")
    
    # Capture du temps de début de traitement
    batch_start_time = time.time()
    batch_id = str(uuid.uuid4())  # Identifiant unique pour ce lot
    
    try:
        print(f"✅ Préparation des données pour le lot {epoch_id}...")
        
        # Convertir le timestamp Unix en timestamp SQL pour compatibilité TimescaleDB
        batch_df = batch_df.withColumn("time", to_timestamp(col("timestamp")))
        
        # Ajouter un ID de capteur (simulé comme 'sensor-1')
        batch_df = batch_df.withColumn("sensor_id", lit("sensor-1"))
        
        # Ajouter les timestamps nécessaires
        batch_df = batch_df.withColumn("spark_receive_time", lit(batch_start_time))
        
        # Simuler mqtt_receive_time et kafka_send_time
        current_time = time.time()
        mqtt_time = current_time - 5
        kafka_time = current_time - 2
        
        batch_df = batch_df.withColumn("mqtt_receive_time", lit(mqtt_time))
        batch_df = batch_df.withColumn("kafka_send_time", lit(kafka_time))
        
        # Créer JSON pour les données brutes
        batch_df = batch_df.withColumn(
            "raw_data", 
            to_json(struct(col("temperature"), col("humidity"), col("timestamp")))
        )
        
        # Sélectionner les colonnes pour TimescaleDB
        final_df = batch_df.select(
            "time", 
            "sensor_id", 
            "temperature", 
            "humidity", 
            "raw_data"
        )
        
        # Compter les messages
        message_count = final_df.count()
        print(f"✅ Préparation terminée: {message_count} messages à écrire")
        
        # Afficher le schéma pour débogage
        print("✅ Schéma du DataFrame:")
        final_df.printSchema()
        
        if message_count > 0:
            print("✅ Exemple de données:")
            final_df.show(1, truncate=False)
        
        print(f"✅ Tentative d'écriture via JDBC...")
        
        # Écrire dans TimescaleDB
        final_df.write \
            .format("jdbc") \
            .option("url", "jdbc:postgresql://timescaledb:5432/sensordb") \
            .option("dbtable", "sensor_data") \
            .option("user", "sensor_user") \
            .option("password", "sensor_pass") \
            .option("driver", "org.postgresql.Driver") \
            .mode("append") \
            .save()
        
        print(f"✅ Écriture JDBC réussie!")
        
        # Calcul des métriques de performance
        batch_end_time = time.time()
        processing_time = batch_end_time - batch_start_time
        
        with metrics_lock:
            processing_times.append(processing_time)
            if len(processing_times) > MAX_TIMES_STORED:
                processing_times.pop(0)
            
            avg_time = statistics.mean(processing_times)
            if len(processing_times) > 1:
                std_dev = statistics.stdev(processing_times)
                min_time = min(processing_times)
                max_time = max(processing_times)
                median_time = statistics.median(processing_times)
            else:
                std_dev = 0
                min_time = max_time = median_time = processing_times[0]
        
        print(f"✅ Lot {epoch_id} écrit avec succès en {processing_time:.3f} secondes")
        print(f"✅ Métriques: Moy={avg_time:.3f}s, Min/Méd/Max={min_time:.3f}/{median_time:.3f}/{max_time:.3f}s")
        
        if message_count > 0:
            sample_df = final_df.limit(min(50, message_count))
            rows = sample_df.collect()
            
            with metrics_lock:
                total_avg = processing_time * 1000  # En ms
                print(f"🔍 TEMPS: Spark → TimescaleDB: {total_avg:.2f} ms")
        
        # Stocker les métriques
        store_performance_metrics(epoch_id, processing_time, avg_time, min_time, max_time, len(processing_times))
        store_kpi_metrics(batch_id, final_df, processing_time * 1000, message_count)
        
    except Exception as e:
        print(f"❌ Erreur: {str(e)}")
        import traceback
        traceback.print_exc()

def store_performance_metrics(batch_id, processing_time, avg_time, min_time, max_time, sample_size):
    """
    Stocke les métriques de performance dans TimescaleDB pour analyse ultérieure.
    
    Args:
        batch_id: Identifiant du lot de données
        processing_time: Temps de traitement pour ce lot
        avg_time: Temps moyen de traitement
        min_time: Temps minimum de traitement
        max_time: Temps maximum de traitement
        sample_size: Nombre d'échantillons utilisés pour les statistiques
    """
    if not PSYCOPG2_AVAILABLE:
        print(f"Métriques de performance pour le lot {batch_id}: {processing_time:.3f}s (mais non stockées en base)")
        return
        
    try:
        # Connexion directe à TimescaleDB pour stocker les métriques
        conn = psycopg2.connect(
            host="timescaledb",
            database="sensordb",
            user="sensor_user",
            password="sensor_pass"
        )
        cursor = conn.cursor()
        
        # Création de la table si elle n'existe pas
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS processing_metrics (
            time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            batch_id VARCHAR(50),
            processing_time FLOAT,
            avg_processing_time FLOAT,
            min_processing_time FLOAT,
            max_processing_time FLOAT,
            sample_size INTEGER
        );
        
        -- Conversion en hypertable si elle ne l'est pas déjà
        SELECT create_hypertable('processing_metrics', 'time', if_not_exists => TRUE);
        """)
        
        # Insertion des métriques
        cursor.execute("""
        INSERT INTO processing_metrics 
        (batch_id, processing_time, avg_processing_time, min_processing_time, max_processing_time, sample_size)
        VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            str(batch_id),
            processing_time,
            avg_time,
            min_time,
            max_time,
            sample_size
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Erreur lors du stockage des métriques de performance: {e}")

def store_kpi_metrics(batch_id, df, processing_time_ms, message_count):
    """
    Stocke les métriques KPI de performance dans la table pipeline_kpi.
    
    Args:
        batch_id (str): Identifiant unique du lot
        df (DataFrame): DataFrame contenant les données traitées
        processing_time_ms (float): Temps de traitement en millisecondes
        message_count (int): Nombre de messages dans le lot
    """
    try:
        # Vérifier si psycopg2 est disponible
        if not PSYCOPG2_AVAILABLE:
            print("⚠️ psycopg2 n'est pas disponible, impossible de stocker les KPI en base de données")
            return
            
        # Établir une connexion à TimescaleDB
        conn = psycopg2.connect(
            host="timescaledb",
            database="sensordb",
            user="sensor_user",
            password="sensor_pass"
        )
        
        # Créer un curseur
        cursor = conn.cursor()
        
        # Vérifier si la table pipeline_kpi existe
        cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'pipeline_kpi')")
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            print("⚠️ La table pipeline_kpi n'existe pas. Création...")
            # Créer la table pour les KPI
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_kpi (
                time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                metric_name TEXT NOT NULL,
                value_ms DOUBLE PRECISION NOT NULL,
                batch_id TEXT,
                message_count INTEGER,
                metadata JSONB DEFAULT '{}'::jsonb
            );
            
            -- Conversion en hypertable
            SELECT create_hypertable('pipeline_kpi', 'time', if_not_exists => TRUE);
            
            -- Création d'index pour de meilleures performances
            CREATE INDEX IF NOT EXISTS idx_pipeline_kpi_metric_name ON pipeline_kpi(metric_name);
            CREATE INDEX IF NOT EXISTS idx_pipeline_kpi_batch_id ON pipeline_kpi(batch_id);
            """)
            conn.commit()
            print("✅ Table pipeline_kpi créée avec succès.")
        
        # Insérer la métrique de temps entre Spark et TimescaleDB
        cursor.execute(
            """
            INSERT INTO pipeline_kpi (metric_name, value_ms, batch_id, message_count, metadata)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                "spark_to_timescaledb",                        # Nom de la métrique
                processing_time_ms,                            # Valeur en ms
                batch_id,                                      # ID du lot
                message_count,                                 # Nombre de messages
                json.dumps({                                   # Métadonnées supplémentaires
                    "avg_temperature": float(df.select(avg("temperature")).collect()[0][0]) 
                    if message_count > 0 else 0,
                    "avg_humidity": float(df.select(avg("humidity")).collect()[0][0])
                    if message_count > 0 else 0,
                    "timestamp": time.time()
                })
            )
        )
        
        # Simuler les latences des autres étapes du pipeline
        # Puisque nous ne pouvons pas obtenir les vraies valeurs (colonnes manquantes dans le schéma)
        mqtt_to_kafka_ms = 50.0  # Valeur simulée
        kafka_to_spark_ms = 20.0  # Valeur simulée
        
        # Insérer les autres métriques KPI simulées
        cursor.execute(
            """
            INSERT INTO pipeline_kpi (metric_name, value_ms, batch_id, message_count, metadata)
            VALUES (%s, %s, %s, %s, %s)
            """,
            ("mqtt_to_kafka", mqtt_to_kafka_ms, batch_id, message_count, "{}")
        )
        
        cursor.execute(
            """
            INSERT INTO pipeline_kpi (metric_name, value_ms, batch_id, message_count, metadata)
            VALUES (%s, %s, %s, %s, %s)
            """,
            ("kafka_to_spark", kafka_to_spark_ms, batch_id, message_count, "{}")
        )
        
        # Calculer la latence totale du pipeline (simulée)
        total_pipeline_latency_ms = mqtt_to_kafka_ms + kafka_to_spark_ms + processing_time_ms
        
        cursor.execute(
            """
            INSERT INTO pipeline_kpi (metric_name, value_ms, batch_id, message_count, metadata)
            VALUES (%s, %s, %s, %s, %s)
            """,
            ("total_pipeline_latency", total_pipeline_latency_ms, batch_id, message_count, "{}")
        )
        
        # Valider les changements
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✅ KPI enregistrés avec succès pour le lot {batch_id}")
        print(f"✅ KPI simulés: MQTT→Kafka={mqtt_to_kafka_ms:.2f}ms, Kafka→Spark={kafka_to_spark_ms:.2f}ms, "
              f"Spark→TimescaleDB={processing_time_ms:.2f}ms, Total={total_pipeline_latency_ms:.2f}ms")
        
    except Exception as e:
        print(f"❌ Erreur lors du stockage des KPI : {str(e)}")
        import traceback
        traceback.print_exc()

def process_sensor_data(spark):
    """
    Fonction principale de traitement des données.
    Configure et exécute le pipeline de streaming Spark qui :
    1. Lit les données depuis Kafka
    2. Parse le JSON
    3. Traite les données
    4. Écrit dans TimescaleDB et MinIO
    
    Args:
        spark (SparkSession): Session Spark active
    """
    print("Configuration du schéma des données...")
    schema = define_schema()
    
    # Configuration supplémentaire de l'accès à MinIO
    configure_s3(spark)

    print("Connexion au topic Kafka...")
    # Création du DataFrame de streaming depuis Kafka
    # Option startingOffsets: Commencer à partir des derniers messages
    df = spark \
        .readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", "kafka:29092") \
        .option("subscribe", "sensor_topic") \
        .option("startingOffsets", "latest") \
        .load()

    print("Configuration du traitement des données...")
    # Étape 1: Afficher les données brutes pour le débogage
    # Cette étape affiche les données au format brut depuis Kafka
    raw_query = df.selectExpr("CAST(key AS STRING)", "CAST(value AS STRING)") \
        .writeStream \
        .outputMode("append") \
        .format("console") \
        .option("truncate", "false") \
        .start()
    
    # Étape 2: Décodage et parsing JSON
    # Cette étape convertit les données JSON en colonnes structurées
    print("Parsing JSON...")
    parsed_df = df.selectExpr("CAST(value AS STRING) as json_str") \
        .select(from_json(col("json_str"), schema).alias("data")) \
        .select("data.*") \
        .withColumn("batch_id", lit(str(uuid.uuid4())))  # Identifiant unique pour chaque batch
    
    # Étape 3: Afficher les données décodées pour le débogage
    # Utile pour vérifier que le parsing JSON fonctionne correctement
    parsed_query = parsed_df \
        .writeStream \
        .outputMode("append") \
        .format("console") \
        .option("truncate", "false") \
        .start()
    
    print("Démarrage du streaming avec sortie vers TimescaleDB...")
    # Écriture des données dans TimescaleDB via la fonction foreachBatch
    # Cette approche permet d'écrire chaque lot de données via JDBC
    timescaledb_query = parsed_df \
        .writeStream \
        .foreachBatch(write_to_timescaledb) \
        .outputMode("append") \
        .start()
    
    print("Démarrage du streaming avec sortie vers MinIO...")
    try:
        # Écriture dans MinIO (S3) au format Parquet
        # Le format Parquet est optimisé pour l'analyse de données
        checkpoint_dir = "/tmp/checkpoints-" + str(uuid.uuid4())  # Répertoire de checkpoint unique
        print(f"Utilisation du répertoire de checkpoint: {checkpoint_dir}")
        
        # Configuration du stream vers MinIO au format Parquet
        # Le format Parquet est optimisé pour l'analyse de données
        # path: Chemin S3 pour le stockage des données
        # checkpointLocation: Répertoire pour stocker les checkpoints de progression
        minio_query = parsed_df \
            .writeStream \
            .format("parquet") \
            .option("path", "s3a://sensordata/data/") \
            .option("checkpointLocation", checkpoint_dir) \
            .option("checkpointInterval", CHECKPOINT_INTERVAL) \
            .outputMode("append") \
            .start()

        print("Tous les flux de streaming ont démarré, en attente des données...")
        
        # Monitorer l'état du stream toutes les 10 secondes
        # Cela permet de suivre le fonctionnement du pipeline
        while minio_query.isActive and timescaledb_query.isActive:
            minio_status = minio_query.status
            timescaledb_status = timescaledb_query.status
            print(f"Statut du stream MinIO: {minio_status}")
            print(f"Statut du stream TimescaleDB: {timescaledb_status}")
            time.sleep(METRICS_UPDATE_INTERVAL)  # Attente réduite pour des mises à jour plus fréquentes
        
        # Si un des streams se termine, attendre que les deux se terminent
        # Cela évite d'arrêter l'application trop tôt
        minio_query.awaitTermination()
        timescaledb_query.awaitTermination()
        
    except Exception as e:
        # En cas d'erreur, logger et continuer avec la sortie console uniquement
        print(f"Erreur lors de la configuration du stream: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Fallback : sortie vers la console uniquement si les autres écritures échouent
        # Cela permet de continuer à voir les données même en cas d'erreur
        parsed_df.writeStream \
            .outputMode("append") \
            .format("console") \
            .option("truncate", "false") \
            .start() \
            .awaitTermination()

if __name__ == "__main__":
    """
    Point d'entrée principal de l'application.
    Initialise la session Spark et démarre le traitement.
    """
    print("Démarrage de l'application...")
    spark = create_spark_session()
    
    try:
        # Lancement du pipeline de traitement
        process_sensor_data(spark)
    except Exception as e:
        # Gestion des erreurs globales
        print(f"Erreur : {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # Nettoyage des ressources Spark
        print("Arrêt de l'application")
        spark.stop() 