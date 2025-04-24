-- Requête corrigée pour l'histogramme des distributions
-- Cette requête utilise une approche alternative sans width_bucket
SELECT 
  FLOOR((temperature - 15) / ((35 - 15) / 20)) + 1 as temp_bucket,
  FLOOR((humidity - 30) / ((90 - 30) / 20)) + 1 as hum_bucket,
  COUNT(*) as count
FROM 
  sensor_data
WHERE 
  $__timeFilter(time)
  AND temperature BETWEEN 15 AND 35
  AND humidity BETWEEN 30 AND 90
GROUP BY 
  temp_bucket, hum_bucket
ORDER BY 
  temp_bucket, hum_bucket; 