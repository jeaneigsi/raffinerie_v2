import paho.mqtt.client as mqtt
import json
from datetime import datetime

# Configuration MQTT
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "sensors/data"

def on_connect(client, userdata, flags, rc):
    """Callback appelé lors de la connexion au broker MQTT"""
    if rc == 0:
        print(f"Connecté au broker MQTT sur {MQTT_BROKER}:{MQTT_PORT}")
        # Souscription au topic
        client.subscribe(MQTT_TOPIC)
        print(f"Abonné au topic: {MQTT_TOPIC}")
    else:
        print(f"Échec de la connexion, code retour={rc}")

def on_message(client, userdata, msg):
    """Callback appelé lors de la réception d'un message"""
    try:
        # Décodage du message JSON
        data = json.loads(msg.payload.decode())
        
        # Conversion du timestamp en date lisible
        timestamp = datetime.fromtimestamp(data['timestamp'])
        
        # Affichage formaté des données
        print("\n=== Nouvelles données reçues ===")
        print(f"Timestamp : {timestamp}")
        print(f"Température : {data['temperature']}°C")
        print(f"Humidité : {data['humidity']}%")
        print("============================")
    except json.JSONDecodeError as e:
        print(f"Erreur de décodage JSON: {e}")
    except Exception as e:
        print(f"Erreur lors du traitement du message: {e}")

def main():
    # Création du client MQTT
    client = mqtt.Client()
    
    # Configuration des callbacks
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        # Connexion au broker
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        
        # Boucle de traitement des messages
        print("En attente des données... (Ctrl+C pour arrêter)")
        client.loop_forever()
        
    except KeyboardInterrupt:
        print("\nArrêt du programme")
        client.disconnect()
    except Exception as e:
        print(f"Erreur: {e}")

if __name__ == "__main__":
    main() 