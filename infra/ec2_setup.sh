#!/usr/bin/env bash
# ==============================================================================
# ZeroTrace Production Host Provisioning Script (AWS EC2 ap-south-1 Mumbai)
# Target: Ubuntu 22.04 LTS on t3.xlarge / c6i.xlarge (16 GB RAM)
# ==============================================================================

set -euo pipefail

echo "=========================================================="
echo "Starting ZeroTrace Host Provisioning (ap-south-1 Mumbai)..."
echo "=========================================================="

# 1. System packages
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get upgrade -y
apt-get install -y --no-install-recommends \
    curl \
    git \
    make \
    ffmpeg \
    openjdk-17-jre-headless \
    ca-certificates \
    gnupg \
    lsb-release \
    jq

# 2. Install Docker
if ! command -v docker &> /dev/null; then
    echo "Installing Docker Engine..."
    mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    systemctl enable docker
    systemctl start docker
    usermod -aG docker ubuntu || true
fi

# 3. Kernel tuning for high-throughput PySpark & Postgres
echo "Configuring virtual memory and file descriptor limits..."
sysctl -w vm.max_map_count=262144
echo "vm.max_map_count=262144" >> /etc/sysctl.conf
sysctl -w fs.file-max=65536
echo "fs.file-max=65536" >> /etc/sysctl.conf

# 4. Clone or update ZeroTrace repo
APP_DIR="/opt/zerotrace"
if [ ! -d "$APP_DIR" ]; then
    echo "Creating ZeroTrace deployment directory at $APP_DIR..."
    mkdir -p "$APP_DIR"
fi

echo "=========================================================="
echo "Host Provisioning Complete! Next steps:"
echo "1. Copy production .env into $APP_DIR/.env"
echo "2. Run: cd $APP_DIR && docker compose -f infra/docker-compose.prod.yml up -d"
echo "=========================================================="
