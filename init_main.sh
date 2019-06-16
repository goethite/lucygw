#!/bin/bash -e

GOVER="1.12.4"

export DEBIAN_FRONTEND=noninteractive
apt update
apt install -y locales python3-pip python3-dev virtualenv

# Locales
locale-gen en_GB
locale-gen en_GB.UTF-8
update-locale en_GB

# Install Go
wget -qO- https://dl.google.com/go/go${GOVER}.linux-amd64.tar.gz | \
  tar zx -C /usr/local/
export PATH=$PATH:/usr/local/go/bin
echo 'export PATH=$PATH:/usr/local/go/bin:~/go/bin' >> ~vagrant/.bashrc
echo 'export GOPATH=$HOME/go' >> ~vagrant/.bashrc

echo "172.17.0.1 kafka-0.broker.kubeless.svc.cluster.local" >> /etc/hosts
