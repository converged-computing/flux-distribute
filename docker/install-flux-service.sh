#!/usr/bin/env bash

# Note: we can't currently use this because flux installed from
# conda does not have systemd support:
# " broker: broker.sd_notify is set but Flux was not built with systemd support.: No such file or directory"

set -o errexit
set -o pipefail
set -o nounset

set -x

# Note: I don't have a check to see if we have already installed
# flux - the idea being that if we delete and reinstall the daemonset,
# we would want this to re-generate. That said, we do need a means
# to allow for autoscaling (adding new nodes) that works out of
# the box.

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
    name = "kind-worker2"
    keygen.flux-core-version = "0.64.0"
    keygen.hostname = "kind-worker2"
    keygen.time = "2024-10-28T13:30:32"
    keygen.userid = "0"
    keygen.zmq-version = "4.3.5"
curve
    public-key = "uMQkII5d)VB?![bXY1.(PBV([Qew1x2l.ar3}5cg"
    secret-key = "ifW737B*JG:U$s8lvlt6JeMsVfWZ#*eL5JWX2y(b"
EOF

mv /tmp/curve.cert /opt/conda/etc/flux/system/curve.cert
chmod o-r /opt/conda/etc/flux/system/curve.cert
chmod g-r /opt/conda/etc/flux/system/curve.cert
# /var/lib/flux needs to be owned by the instance owner (root)
# this should already by the case

# Get the linkname of the device
linkname=$(python3 /mnt/install/parse-links.py)
echo "Found ip link name ${linkname} to provide to flux"

# Get broker names.
lead_broker=$(cat /mnt/install/lead-broker.txt)
echo "The lead broker is ${lead_broker}"

followers=""
for broker in $(cat /mnt/install/follower-brokers.txt)
  do 
    echo "Adding broker ${broker}"
    if [[ "${followers}" == "" ]]; then
      followers="${broker}"
    else
      followers="${followers},${broker}"
    fi
  done

# One node cluster vs. not...
if [[ "$followers" == "" ]]; then
    brokers="${lead_broker}"
else
    echo "The follower brokers are ${followers}"
    brokers="${lead_broker},${followers}"
fi

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
default_bind = "tcp://${linkname}:%p"
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

# Write new service file
cat <<EOF | tee /tmp/flux.service
[Unit]
Description=Flux message broker
Wants=munge.service

[Service]
Type=notify
NotifyAccess=main
TimeoutStopSec=90
KillMode=mixed
ExecStart=/bin/bash -c '\
  XDG_RUNTIME_DIR=/run/user/$UID \
  DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$UID/bus \
  /opt/conda/bin/flux broker \
  --config-path=/opt/conda/etc/flux/system/conf.d \
  -Scron.directory=/opt/conda/etc/flux/system/cron.d \
  -Srundir=/var/run/flux \
  -Sstatedir=/var/lib/flux \
  -Slocal-uri=local:///var/run/flux/local \
  -Slog-stderr-level=6 \
  -Slog-stderr-mode=local \
  -Sbroker.rc2_none \
  -Sbroker.quorum=1 \
  -Sbroker.quorum-timeout=none \
  -Sbroker.exit-norestart=42 \
  -Sbroker.sd-notify=1 \
  -Scontent.restore=auto'
SyslogIdentifier=flux
ExecReload=/opt/conda/bin/flux config reload
LimitMEMLOCK=infinity
Restart=always
RestartSec=5s
RestartPreventExitStatus=42
SuccessExitStatus=42
User=root
RuntimeDirectory=flux
RuntimeDirectoryMode=0755
StateDirectory=flux
StateDirectoryMode=0700
PermissionsStartOnly=true
# ExecStartPre=/usr/bin/loginctl enable-linger flux
# ExecStartPre=bash -c 'systemctl start user@$(id -u flux).service'

#
# Delegate cgroup control to user flux, so that systemd doesn't reset
#  cgroups for flux initiated processes, and to allow (some) cgroup
#  manipulation as user flux.
#
Delegate=yes

[Install]
WantedBy=multi-user.target
EOF

mv /tmp/flux.service /lib/systemd/system/flux.service

# If we don't do this, fails on too many open files
sysctl fs.inotify.max_user_instances=8192
sysctl fs.inotify.max_user_watches=524288

systemctl daemon-reload
systemctl enable --now flux.service
systemctl status flux.service