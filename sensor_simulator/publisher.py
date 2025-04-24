########################################################
# Simulateur de Capteurs IoT - Publisher
# 
# Ce script simule des capteurs IoT générant des données de température
# et d'humidité, puis les publie sur un broker MQTT pour être traitées
# par le pipeline de données.
#
# Fonctionnalités :
# - Génération de données aléatoires de température (20-30°C)
# - Génération de données aléatoires d'humidité (40-80%)
# - Publication au format JSON sur un topic MQTT
# - Horodatage des données pour analyse temporelle
# - Mécanisme de reconnexion automatique
########################################################

import paho.mqtt.client as mqtt
import json
import random
import time
from datetime import datetime

# Configuration MQTT
MQTT_BROKER = "localhost"  # Mosquitto est exposé sur localhost via Docker
MQTT_PORT = 1883          # Port exposé dans docker-compose.yml
MQTT_TOPIC = "sensors/data"

# Configuration de la simulation
PUBLISH_INTERVAL = 0.5     # Intervalle en secondes entre les publications (réduit pour des résultats rapides)
SIMULATE_JITTER = True     # Ajouter une légère variation aléatoire dans les intervalles

# Création du client MQTT
client = mqtt.Client()

def connect_mqtt():
    """
    Établit la connexion avec le broker MQTT.
    
    Cette fonction tente de se connecter au broker MQTT configuré
    et affiche un message de confirmation ou d'erreur.
    
    Returns:
        bool: True si la connexion a réussi, False sinon
    """
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)  # 60 secondes de timeout
        print(f"Connecté au broker MQTT sur {MQTT_BROKER}:{MQTT_PORT}")
        return True
    except Exception as e:
        print(f"Erreur de connexion au broker MQTT: {e}")
        return False

def generate_sensor_data():
    """
    Génère des données simulées de température et d'humidité.
    
    Cette fonction crée un dictionnaire contenant des valeurs aléatoires
    de température (entre 20°C et 30°C) et d'humidité (entre 40% et 80%),
    ainsi qu'un horodatage Unix (timestamp) pour le moment de la génération.
    
    Returns:
        dict: Dictionnaire contenant les valeurs simulées des capteurs
    """
    return {
        "temperature": round(random.uniform(20.0, 30.0), 1),  # Température en °C, précision 0.1
        "humidity": round(random.uniform(40.0, 80.0), 1),     # Humidité en %, précision 0.1
        "timestamp": time.time()                              # Horodatage Unix en secondes
    }

def main():
    """
    Fonction principale du simulateur.
    
    Cette fonction gère la connexion au broker MQTT avec un mécanisme
    de nouvelles tentatives, puis entre dans une boucle infinie pour
    générer et publier des données de capteurs à intervalles réguliers.
    """
    # Attendre que le broker MQTT soit disponible
    # Mécanisme de reconnexion avec un nombre limité de tentatives
    max_retries = 5
    retry_count = 0
    
    while retry_count < max_retries:
        if connect_mqtt():
            break
        print(f"Tentative de reconnexion dans 5 secondes... ({retry_count + 1}/{max_retries})")
        time.sleep(5)
        retry_count += 1
    
    if retry_count >= max_retries:
        print("Impossible de se connecter au broker MQTT après plusieurs tentatives")
        return

    # Démarrage de la boucle de traitement MQTT en arrière-plan
    client.loop_start()

    try:
        print(f"Début de la simulation. Publication sur le topic: {MQTT_TOPIC}")
        print(f"Intervalle de publication: {PUBLISH_INTERVAL} secondes")
        print("Appuyez sur Ctrl+C pour arrêter la simulation")
        
        # Boucle infinie de génération et publication de données
        while True:
            # Génération et publication des données
            data = generate_sensor_data()
            message = json.dumps(data)  # Conversion en JSON
            
            # Publication sur le topic MQTT configuré
            result = client.publish(MQTT_TOPIC, message)
            
            # Vérification du statut de publication
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"Données publiées: {message}")
            else:
                print(f"Erreur lors de la publication: code {result.rc}")
                
            # Intervalle entre les publications
            if SIMULATE_JITTER:
                # Ajouter une légère variation aléatoire (±10%)
                jitter = PUBLISH_INTERVAL * random.uniform(-0.1, 0.1)
                sleep_time = max(0.1, PUBLISH_INTERVAL + jitter)
            else:
                sleep_time = PUBLISH_INTERVAL
                
            time.sleep(sleep_time)  # Attente entre chaque publication

    except KeyboardInterrupt:
        # Gestion propre de l'interruption par l'utilisateur
        print("\nArrêt du simulateur de capteurs")
        client.loop_stop()     # Arrêt de la boucle de traitement MQTT
        client.disconnect()    # Déconnexion propre du broker MQTT
        print("Déconnecté du broker MQTT")

if __name__ == "__main__":
    main() 