#!/usr/bin/env bash
set -o errexit
set -o pipefail
set -o nounset

set -x

INSTALL_FILE="/flux-install/install-flux.sh"
apt-get update && apt-get install -y wget curl jq || (yum update -y && yum install -y wget curl jq)

# Install x86 or arm
if [[ "$(uname -m)" == "x86_64" ]]; then
  wget https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl
else
  wget https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/arm64/kubectl
fi

chmod +x ./kubectl
mv ./kubectl /usr/local/bin/

# Write the node names to file that we share with the host node
# Note that I'm breaking apart anticipating that sometimes we will see control plane (kind)
# and other times not. For now, assume control plane has "control-plane" in name
echo "Deriving broker names from pod"
kubectl get nodes -o json | jq -r '.items[].status.addresses[] | select(.type=="Hostname") | .address' > /mnt/install/brokers.txt
kubectl get nodes -o json | jq -r '.items[0].status.addresses[] | select(.type=="Hostname") | .address' > /mnt/install/lead-broker.txt
kubectl get nodes -o json | jq -r '.items[].status.addresses[] | select(.type=="Hostname") | .address' | tail -n +2 > /mnt/install/follower-brokers.txt

if [[ ! -f "$INSTALL_FILE" ]]; then
    echo "Expected to find install file '$INSTALL_FILE', but it does not exist"
    exit 1
fi

# We need to copy everything into mount from container 
echo "Copying install files onto the host node"
cp ${INSTALL_FILE} /mnt/install/install.sh
cp /flux-install/parse-links.py /mnt/install/parse-links.py
chmod +x /mnt/install/install.sh

# This gets executed with nsenter to pid 1, the init process
echo "Executing nsenter to connect from container to host"
nsenter -t 1 -m bash /mnt/install/install.sh
RESULT="${PIPESTATUS[0]}"

if [ $RESULT -eq 0 ]; then
    echo "Completed successfully - flux is setup"
    sleep infinity
else
    echo "Failed during nsenter install"
    exit 1
fi