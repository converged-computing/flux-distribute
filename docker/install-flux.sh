#!/usr/bin/env bash

set -o errexit
set -o pipefail
set -o nounset

# Note: I don't have a check to see if we have already installed
# flux - the idea being that if we delete and reinstall the daemonset,
# we would want this to re-generate. That said, we do need a means
# to allow for autoscaling (adding new nodes) that works out of
# the box. Let's better test this alter.

# Dependencies!
which micromamba || (
  apt-get update && apt-get install -y bzip2 curl || (yum update -y && yum install -y bzip2 curl)

  # Install to root bin
  cd /
  curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xvj bin/micromamba
)

# We require munge
apt-get update && apt-get install -y munge || (yum update -y && yum install -y munge)

# Install mamba
export MAMBA_ROOT_PREFIX=/opt/conda
mkdir -p /opt/conda
eval "$(micromamba shell hook -s posix)"

# Activate the base environment
micromamba activate

# Flux still using old python...
micromamba install python=3.11 jupyter -c conda-forge --yes
micromamba activate base

# This assumes installing latest pair - we could always change this to
# be a specific version, but I don't see need for that yet.
micromamba install --yes flux-core flux-sched

# Prepare resource system directory
mkdir -p /opt/conda/etc/flux/system/conf.d
mkdir -p /opt/conda/etc/flux/system/cron.d
mkdir -p /opt/conda/etc/flux/system
mkdir -p /var/lib/flux /var/run/flux

# Flux curve.cert
# Ensure we have a shared curve certificate
# This is just for development - we need a means to generate and distribute this.

cat <<EOF | tee /tmp/curve.cert
#  ZeroMQ CURVE **Secret** Certificate
#  DO NOT DISTRIBUTE

metadata
    name = "flux-service"
    keygen.flux-core-version = "0.64.0"
    keygen.hostname = "flux-service"
    keygen.time = "2024-10-28T13:30:32"
    keygen.userid = "0"
    keygen.zmq-version = "4.3.5"
curve
    public-key = "uMQkII5d)VB?![bXY1.(PBV([Qew1x2l.ar3}5cg"
    secret-key = "ifW737B*JG:U\$s8lvlt6JeMsVfWZ#*eL5JWX2y(b"
EOF

mv /tmp/curve.cert /opt/conda/etc/flux/system/curve.cert
chmod o-r /opt/conda/etc/flux/system/curve.cert
chmod g-r /opt/conda/etc/flux/system/curve.cert
# /var/lib/flux needs to be owned by the instance owner (root)
# this should already by the case

# Get the linkname of the device
linkname=$(python3 /mnt/install/parse-links.py)
echo "Found ip link name ${linkname} to provide to flux"

# Assume we add all brokers, unless "control-plane" in name (kind)
brokers=""
for broker in $(cat /mnt/install/brokers.txt)
  do 
    # Don't include the control plane, we don't use it
    if [[ $broker = *'control-plane'* ]]; then
       continue
    fi
    echo "Adding broker ${broker}"
    if [[ "${brokers}" == "" ]]; then
      brokers="${broker}"
    else
      brokers="${brokers},${broker}"
    fi
  done

# One node cluster vs. not...
if [[ "$brokers" == "" ]]; then
    echo "No brokers found - this should not happen"
    exit 1
fi

# Generate resources!
flux R encode --hosts="${brokers}" --local > /opt/conda/etc/flux/system/R

# Show ip addresses for debugging
ip addr

# Write broker.toml
cat <<EOF | tee /tmp/broker.toml
# Allow users other than the instance owner (guests) to connect to Flux
# Optionally, root may be given "owner privileges" for convenience
[access]
allow-guest-user = true
allow-root-owner = true

# Point to resource definition generated with flux-R(1).
# Uncomment to exclude nodes (e.g. mgmt, login), from eligibility to run jobs.
[resource]
path = "/opt/conda/etc/flux/system/R"

# Point to shared network certificate generated flux-keygen(1).
# Define the network endpoints for Flux's tree based overlay network
# and inform Flux of the hostnames that will start flux-broker(1).
[bootstrap]
curve_cert = "/opt/conda/etc/flux/system/curve.cert"

# ubuntu does not have eth0
default_port = 8050
default_bind = "tcp://eth0:%p"
# default_bind = "tcp://${linkname}:%p"
default_connect = "tcp://%h:%p"

# Rank 0 is the TBON parent of all brokers unless explicitly set with
# parent directives.
# The actual ip addresses (for both) need to be added to /etc/hosts
# of each VM for now.
hosts = [
   { host = "${brokers}" },
]
# Speed up detection of crashed network peers (system default is around 20m)
[tbon]
tcp_user_timeout = "2m"
EOF

# Move to conf.d
mv /tmp/broker.toml /opt/conda/etc/flux/system/conf.d/broker.toml

# If we don't do this, fails on too many open files
sysctl fs.inotify.max_user_instances=8192
sysctl fs.inotify.max_user_watches=524288

# Write a small script that makes it easy to connect
cat <<EOF | tee /flux-connect.sh
#!/bin/bash

/opt/conda/bin/flux proxy local:///var/run/flux/local bash
EOF
chmod +x /flux-connect.sh

# Options for the broker. Flux installed from conda does not have
# systemd support.
brokerOptions="-Scron.directory=/opt/conda/etc/flux/system/cron.d \
-Stbon.fanout=256 \
-Srundir=/var/run/flux \
-Sbroker.rc2_none \
-Sstatedir=/opt/conda/etc/flux/system \
-Slocal-uri=local:///var/run/flux/local \
-Slog-stderr-level=6 \
-Slog-stderr-mode=local"

cfg="/opt/conda/etc/flux/system/conf.d/broker.toml"
echo "🌀 flux broker --config-path ${cfg} ${brokerOptions}"

# Retry for failure
while true
do
  /opt/conda/bin/flux broker --config-path ${cfg} ${brokerOptions}
  echo "Return value for follower worker is ${retval}"
  echo "😪 Sleeping 15s to try again..."
  sleep 15
done