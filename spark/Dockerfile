FROM bitnami/spark:3.4.0

# Installation de Python et pip
USER root
RUN apt-get update && apt-get install -y python3 python3-pip wget libpq-dev python3-dev && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    pip3 install --no-cache-dir pyspark kafka-python psycopg2

# Installation des dépendances Kafka pour Spark
RUN cd /opt/bitnami/spark/jars && \
    wget https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.4.0/spark-sql-kafka-0-10_2.12-3.4.0.jar && \
    wget https://repo1.maven.org/maven2/org/apache/spark/spark-token-provider-kafka-0-10_2.12/3.4.0/spark-token-provider-kafka-0-10_2.12-3.4.0.jar && \
    wget https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/3.3.2/kafka-clients-3.3.2.jar && \
    wget https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/2.11.1/commons-pool2-2.11.1.jar && \
    wget https://repo1.maven.org/maven2/org/apache/spark/spark-streaming-kafka-0-10_2.12/3.4.0/spark-streaming-kafka-0-10_2.12-3.4.0.jar

# Installation des dépendances S3A pour MinIO (avec des versions compatibles explicites)
RUN cd /opt/bitnami/spark/jars && \
    wget https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar && \
    wget https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar && \
    wget https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-common/3.3.4/hadoop-common-3.3.4.jar && \
    wget https://repo1.maven.org/maven2/org/wildfly/openssl/wildfly-openssl/2.2.5.Final/wildfly-openssl-2.2.5.Final.jar && \
    wget https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-client/3.3.4/hadoop-client-3.3.4.jar

# Installation du connecteur JDBC PostgreSQL pour TimescaleDB
RUN cd /opt/bitnami/spark/jars && \
    wget https://jdbc.postgresql.org/download/postgresql-42.6.0.jar

# Configuration Spark pour S3A
COPY spark_app.py /opt/spark/work-dir/

# Point d'entrée
ENTRYPOINT ["python", "/opt/spark/work-dir/spark_app.py"] 