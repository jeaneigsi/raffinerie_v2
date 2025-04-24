-- Activer l'extension TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- La base de données est déjà créée par les variables d'environnement POSTGRES_DB

-- Créer la table pour stocker les données des capteurs
CREATE TABLE IF NOT EXISTS sensor_data (
    time TIMESTAMPTZ NOT NULL,
    sensor_id TEXT NOT NULL,
    temperature DOUBLE PRECISION NULL,
    humidity DOUBLE PRECISION NULL,
    raw_data TEXT NULL
);

-- Créer un index sur sensor_id pour accélérer les requêtes
CREATE INDEX IF NOT EXISTS idx_sensor_data_sensor_id ON sensor_data(sensor_id);

-- Convertir la table en hypertable avec partitionnement sur le temps
SELECT create_hypertable('sensor_data', 'time', if_not_exists => TRUE);

-- Créer des vues pour faciliter les requêtes communes
CREATE OR REPLACE VIEW hourly_avg_temperature AS
SELECT
    time_bucket('1 hour', time) AS hour,
    sensor_id,
    AVG(temperature) AS avg_temperature
FROM sensor_data
GROUP BY hour, sensor_id
ORDER BY hour DESC, sensor_id;

CREATE OR REPLACE VIEW hourly_avg_humidity AS
SELECT
    time_bucket('1 hour', time) AS hour,
    sensor_id,
    AVG(humidity) AS avg_humidity
FROM sensor_data
GROUP BY hour, sensor_id
ORDER BY hour DESC, sensor_id;

-- Ajouter des politiques de rétention (par exemple, conservation de 30 jours de données)
-- Décommentez si vous voulez limiter le stockage
-- SELECT add_retention_policy('sensor_data', INTERVAL '30 days', if_not_exists => TRUE);

-- Accorder les privilèges nécessaires
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO sensor_user; 