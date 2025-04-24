#!/usr/bin/env python3
########################################################
# Connecteur MQTT vers Kafka
# 
# Ce script agit comme un pont entre MQTT et Kafka.
# Il s'abonne à un topic MQTT, reçoit les messages des capteurs,
# puis les transfère vers un topic Kafka pour être traités
# par le pipeline de données.
#
# Fonctionnalités :
# - Abonnement à un topic MQTT configuré
# - Conversion des messages JSON du format MQTT
# - Transfert vers Kafka avec sérialisation appropriée
# - Mécanisme de reconnexion automatique
# - Gestion d'erreurs robuste
########################################################

import paho.mqtt.client as mqtt
import json
from kafka import KafkaProducer
import time

# Configuration des paramètres de connexion
MQTT_BROKER = "localhost"  # Adresse du broker MQTT (Mosquitto)
MQTT_PORT = 1883           # Port standard MQTT
MQTT_TOPIC = "sensors/data"  # Topic où les capteurs publient leurs données

KAFKA_BROKERS = ["localhost:9092"]  # Liste des brokers Kafka
KAFKA_TOPIC = "sensor_topic"        # Topic Kafka où les données seront envoyées

# Intervalle de traitement en secondes (réduit pour des résultats rapides)
PROCESSING_INTERVAL = 0.5  # 500 ms entre chaque message pour voir rapidement les résultats

# Création du producteur Kafka
def create_kafka_producer():
    """
    Crée et configure un producteur Kafka.
    
    Cette fonction initialise un producteur Kafka avec les paramètres appropriés,
    notamment pour la sérialisation des messages JSON.
    
    Returns:
        KafkaProducer: Instance du producteur Kafka configuré, ou None en cas d'erreur
    """
    try:
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')  # Convertit les objets Python en JSON encodé en UTF-8
        )
        print(f"Producteur Kafka connecté à {KAFKA_BROKERS}")
        return producer
    except Exception as e:
        print(f"Erreur lors de la création du producteur Kafka: {e}")
        return None

# Callback MQTT pour la connexion
def on_connect(client, userdata, flags, rc):
    """
    Callback exécuté lorsque le client MQTT se connecte au broker.
    
    Cette fonction vérifie si la connexion a réussi (rc=0) et, dans ce cas,
    s'abonne au topic MQTT configuré pour recevoir les données des capteurs.
    
    Args:
        client: Instance du client MQTT
        userdata: Données utilisateur définies lors de la création du client
        flags: Drapeaux de réponse envoyés par le broker
        rc: Code de résultat de la tentative de connexion
            (0: Succès, autres valeurs: Échec avec code d'erreur)
    """
    if rc == 0:
        print(f"Connecté au broker MQTT sur {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe(MQTT_TOPIC)
        print(f"Abonné au topic MQTT: {MQTT_TOPIC}")
    else:
        print(f"Échec de la connexion MQTT, code retour={rc}")
        print("Signification du code: " + {
            1: "Protocole incorrect",
            2: "Identifiant client rejeté",
            3: "Serveur indisponible",
            4: "Nom d'utilisateur/mot de passe incorrect",
            5: "Non autorisé"
        }.get(rc, "Erreur inconnue"))

# Callback MQTT pour les messages reçus
def on_message(client, userdata, msg):
    """
    Callback exécuté lorsqu'un message est reçu du broker MQTT.
    
    Cette fonction décode le message MQTT (supposé être au format JSON),
    puis le transmet au topic Kafka configuré.
    
    Args:
        client: Instance du client MQTT
        userdata: Données utilisateur contenant le producteur Kafka
        msg: Message MQTT reçu avec son payload et ses métadonnées
    """
    try:
        # Horodatage MQTT - capture le moment de réception du message
        mqtt_receive_time = time.time()
        
        # Décodage du message MQTT en JSON
        payload = msg.payload.decode('utf-8')
        data = json.loads(payload)
        
        # Enrichissement des données avec des horodatages pour le suivi de performance
        data['mqtt_receive_time'] = mqtt_receive_time
        data['kafka_send_time'] = time.time()
        
        # Envoi du message au topic Kafka
        userdata['producer'].send(KAFKA_TOPIC, value=data)
        userdata['producer'].flush()  # Force l'envoi immédiat du message
        
        # Calcul du temps de traitement MQTT
        mqtt_processing_time = (data['kafka_send_time'] - mqtt_receive_time) * 1000  # en millisecondes
        
        print(f"Message transféré de MQTT vers Kafka: {data}")
        print(f"Temps de traitement MQTT->Kafka: {mqtt_processing_time:.2f} ms")
    except json.JSONDecodeError as e:
        print(f"Erreur de décodage JSON: {e}, payload: {msg.payload}")
    except Exception as e:
        print(f"Erreur lors du traitement/transfert du message: {e}")

def main():
    """
    Fonction principale du connecteur MQTT-Kafka.
    
    Cette fonction gère:
    1. La connexion au broker Kafka avec mécanisme de reconnexion
    2. La configuration du client MQTT avec les callbacks appropriés
    3. La connexion au broker MQTT
    4. L'exécution de la boucle de traitement des messages
    """
    # Configuration des tentatives de connexion à Kafka
    max_retries = 10
    retry_count = 0
    
    # Tentatives répétées de connexion au broker Kafka
    while retry_count < max_retries:
        producer = create_kafka_producer()
        if producer:
            break
        print(f"Tentative de reconnexion Kafka dans 5 secondes... ({retry_count + 1}/{max_retries})")
        time.sleep(5)
        retry_count += 1
    
    if retry_count >= max_retries:
        print("Impossible de se connecter au broker Kafka après plusieurs tentatives")
        return
    
    # Création du client MQTT avec l'accès au producteur Kafka via userdata
    client = mqtt.Client(userdata={"producer": producer})
    
    # Configuration des callbacks MQTT
    client.on_connect = on_connect
    client.on_message = on_message
    
    # Configuration additionnelle (optionnelle)
    client.on_disconnect = lambda client, userdata, rc: print(f"Déconnecté du broker MQTT avec code: {rc}")
    
    # Connexion au broker MQTT
    try:
        print(f"Tentative de connexion au broker MQTT sur {MQTT_BROKER}:{MQTT_PORT}...")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)  # 60 secondes de keepalive
        
        print("Démarrage de la boucle de traitement des messages...")
        print("Appuyez sur Ctrl+C pour arrêter le programme")
        
        # Boucle infinie pour traiter les messages
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nArrêt du connecteur MQTT-Kafka")
        client.disconnect()
        print("Déconnecté du broker MQTT")
    except Exception as e:
        print(f"Erreur lors de la connexion au broker MQTT: {e}")

if __name__ == "__main__":
    main() 