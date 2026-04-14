#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Run this script ON the Lightsail nano instance (SSH in first).
# It installs Docker and starts Kafka + Qdrant.
#
# Usage:
#   ssh ubuntu@<instance-ip>
#   curl -O https://raw.githubusercontent.com/.../1-setup-lightsail-instance.sh
#   chmod +x 1-setup-lightsail-instance.sh && ./1-setup-lightsail-instance.sh
# ─────────────────────────────────────────────────────────────────────────────
set -e

echo "==> Installing Docker..."
sudo apt-get update -y
sudo apt-get install -y docker.io docker-compose-plugin
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker ubuntu

echo "==> Creating docker-compose for Kafka + Qdrant..."
mkdir -p ~/idp-infra && cat > ~/idp-infra/docker-compose.yml <<'EOF'
services:

  kafka:
    image: apache/kafka:latest
    container_name: idp-kafka
    restart: unless-stopped
    ports:
      - "9092:9092"
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      KAFKA_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://0.0.0.0:9092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"
      KAFKA_NUM_PARTITIONS: 3
      KAFKA_DEFAULT_REPLICATION_FACTOR: 1
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    volumes:
      - kafka_data:/var/lib/kafka/data

  qdrant:
    image: qdrant/qdrant:latest
    container_name: idp-qdrant
    restart: unless-stopped
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

volumes:
  kafka_data:
  qdrant_data:
EOF

echo "==> Starting Kafka + Qdrant..."
cd ~/idp-infra
docker compose up -d

echo "==> Waiting for Kafka to be ready..."
sleep 30

echo ""
echo "✓ Done! Kafka and Qdrant are running."
echo ""
echo "IMPORTANT — open these ports in Lightsail firewall:"
echo "  Port 9092  (Kafka)"
echo "  Port 6333  (Qdrant)"
echo ""
echo "Use the PRIVATE IP of this instance in your .env.prod:"
echo "  KAFKA_BOOTSTRAP_SERVERS=$(hostname -I | awk '{print $1}'):9092"
echo "  QDRANT_HOST=$(hostname -I | awk '{print $1}')"
