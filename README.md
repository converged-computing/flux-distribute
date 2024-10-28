# Flux Distribute

This is an experiment to install Flux to Kubernetes nodes, where we could try:

- using it as a mechanism to distribute content (e.g., containers with some cool tree algorithms)
- orchestrate some part of the kubelet logic
- interact with a custom scheduler

We will first start by having a daemonset that installs it, and if that is successful, we can next try to use flux archive and flux exec to share content. If that is successful, then we can try to implement something else. FOr example, a tool in Go could distributes containers across the nodes, likely by doing a pull first to one node, and then having the distribution done by flux.

## Usage

To install to your cluster, you should create it first! There is an [example](example) provided using kind:

```bash
kind create cluster --config ./example/kind-config.yaml
```

Then install the daemonset. 

```bash
kubectl apply -f ./daemonset-installer.yaml
```

You can then look at the first node in your set (the lead broker) to see all workers join:

```console
/opt/conda/bin/flux proxy local:///var/run/flux/local bash
🌀 flux broker --config-path /opt/conda/etc/flux/system/conf.d/broker.toml -Scron.directory=/opt/conda/etc/flux/system/cron.d -Stbon.fanout=256 -Srundir=/var/run/flux -Sbroker.rc2_none -Sstatedir=/opt/conda/etc/flux/system -Slocal-uri=local:///var/run/flux/local -Slog-stderr-level=6 -Slog-stderr-mode=local
broker.info[0]: start: none->join 0.359796ms
broker.info[0]: parent-none: join->init 0.009167ms
kvs.info[0]: restored KVS from checkpoint on 2024-10-28T15:01:55Z
cron.info[0]: synchronizing cron tasks to event heartbeat.pulse
job-manager.info[0]: restart: 0 jobs
job-manager.info[0]: restart: 0 running jobs
job-manager.info[0]: restart: checkpoint.job-manager not found
broker.info[0]: rc1.0: running /opt/conda/etc/flux/rc1.d/01-sched-fluxion
sched-fluxion-resource.info[0]: version 0.38.0
sched-fluxion-resource.warning[0]: create_reader: allowlist unsupported
sched-fluxion-resource.info[0]: populate_resource_db: loaded resources from core's resource.acquire
sched-fluxion-qmanager.info[0]: version 0.38.0
broker.info[0]: rc1.0: running /opt/conda/etc/flux/rc1.d/02-cron
broker.info[0]: rc1.0: /opt/conda/etc/flux/rc1 Exited (rc=0) 0.6s
broker.info[0]: rc1-success: init->quorum 0.554957s
broker.info[0]: online: kind-worker (ranks 0)
broker.info[0]: online: kind-worker,kind-worker[2-4] (ranks 0-3)
broker.info[0]: quorum-full: quorum->run 1.46333s
```

Or an individual worker will show similar:

```console
🌀 flux broker --config-path /opt/conda/etc/flux/system/conf.d/broker.toml -Scron.directory=/opt/conda/etc/flux/system/cron.d -Stbon.fanout=256 -Srundir=/var/run/flux -Sbroker.rc2_none -Sstatedir=/opt/conda/etc/flux/system -Slocal-uri=local:///var/run/flux/local -Slog-stderr-level=6 -Slog-stderr-mode=local
broker.info[3]: start: none->join 0.312617ms
broker.info[3]: parent-ready: join->init 1.68782s
broker.info[3]: configuration updated
broker.info[3]: rc1.0: running /opt/conda/etc/flux/rc1.d/01-sched-fluxion
broker.info[3]: rc1.0: running /opt/conda/etc/flux/rc1.d/02-cron
broker.info[3]: rc1.0: /opt/conda/etc/flux/rc1 Exited (rc=0) 0.3s
broker.info[3]: rc1-success: init->quorum 0.303304s
broker.info[3]: quorum-full: quorum->run 1.16005s
```

We can't use systemd because the conda packages don't support it, but that should be OK for now.

## How does this work?

1. We use a daemonset and nsenter to enter the init process of the node
2. We install flux core and sched from conda forge
3. The rbac / roles and service account given to the daemonset give it permission to list node
4. With the node addresses, we can prepare a broker configuration
5. The daemonset launches a script that installs and configures flux
6. The brokers start on each node!

The scripts are built into the container, so if you need to update or change something, just do it there.
Note that a systemd example install is included in [docker](docker) but we cannot use it yet because the conda installs don't support systemd.


## Debugging

I've added a script that makes it easy to shell in and debug. You can look at the logs to see the first in the host list - this is the lead broker. In the log above, it's `kind-worker`. Get the pod associated with it:

```bash
$ kubectl get pods -o wide
NAME                 READY   STATUS    RESTARTS   AGE     IP           NODE           NOMINATED NODE   READINESS GATES
install-flux-266zk   1/1     Running   0          4m43s   172.18.0.3   kind-worker4   <none>           <none>
install-flux-2sqq6   1/1     Running   0          4m43s   172.18.0.5   kind-worker    <none>           <none>
install-flux-7d5ps   1/1     Running   0          4m43s   172.18.0.4   kind-worker2   <none>           <none>
install-flux-ql9w9   1/1     Running   0          4m43s   172.18.0.6   kind-worker3   <none>           <none>
```

You can either shell into the associated daemonset pods and run nsenter:

```bash
kubectl exec -it install-flux-2sqq6 bash
nsenter -t 1 -m bash
```

Or use the kubectl node-shell plugin (which does the same)

```bash
kubectl node-shell kind-worker
```

Flux lives with conda, and it's not on the path. But I will tell you it's in `/opt/conda/bin` and you can just run the script that the daemonset prepares to connect to the broker:

```bash
 ./flux-connect.sh 
root@kind-worker:/# flux resource list
     STATE NNODES   NCORES    NGPUS NODELIST
      free      4       32        0 kind-worker,kind-worker[2-4]
 allocated      0        0        0 
      down      0        0        0 
```

Boum! Bing badda... boom! 💥

## Limitations

We currently just install flux core and sched from conda, meaning the latest versions. An improvement would be to allow customization, or for these builds, to enable systemd support (not currently there for the conda binaries). We also don't do any kind of restart if nodes are added, meaning that autoscaling won't work. You would need to delete the daemonset and then recreate it, and likely we would want to do some kind of cleanup step.

## Development

To build the base image (note that the Daemonset has image pull policy "Always" that requires a push, but you can load into kind or your cluster and then make the policy "Never."). To build, just do:

```bash
make build
```

But to build and then apply the daemonset:

```bash
make test
```

And then see flux running! This is from the node, actually:

```bash
kubectl logs install-flux-xxxx -f
```

## License

HPCIC DevTools is distributed under the terms of the MIT license.
All new contributions must be made under this license.

See [LICENSE](https://github.com/converged-computing/cloud-select/blob/main/LICENSE),
[COPYRIGHT](https://github.com/converged-computing/cloud-select/blob/main/COPYRIGHT), and
[NOTICE](https://github.com/converged-computing/cloud-select/blob/main/NOTICE) for details.

SPDX-License-Identifier: (MIT)

LLNL-CODE- 842614