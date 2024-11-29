# Topology Experiments

I am experimenting with topology to figure out how we might map this into a snapshotter or distribution mechanism on a cluster. What I'm trying:

1. Create a MiniCluster with a more nested tree topology
2. Try to interact with it
3. Can we make Go bindings to do the same (or do we need to exec call to the host)?

## Docker

Note that we needed to fix a segfault in flux, and then build from the master. To do this, we have a custom
build in [docker](docker).

```bash
cd ./docker
docker build -t ghcr.io/converged-computing/flux-view-ubuntu:tag-noble-flux-0.66.0 .
docker push ghcr.io/converged-computing/flux-view-ubuntu:tag-noble-flux-0.66.0
```

## Experiments

After [testing](#testing) we moved into experiments in Kubernetes.

 - [kind-experiment](kind-experiment): local experiment with kind, was challenging due to running the faux nodes (with a large base) on one machine.
 - [cloud-experiment](cloud-experiment): Run on GKE, much easier to do (but keep aware of costs)


## Testing

Install the Flux Operator

```bash
kubectl apply -f https://raw.githubusercontent.com/flux-framework/flux-operator/refs/heads/main/examples/dist/flux-operator.yaml
```

Create the minicluster (here is kary:2 topology size 8):

```bash
kubectl apply -f ./minicluster-test.yaml
```

Shell in

```bash
kubectl exec -it flux-0-xxx bash
. /mnt/flux/flux-view.sh
[root@flux-0 /]# flux proxy $fluxsocket bash
```

View the overlay structure:

```bash
[root@flux-0 /]# flux overlay status
0 flux-0: online
├─ 1 flux-1: online
│  ├─ 3 flux-3: online
│  │  └─ 7 flux-7: online
│  └─ 4 flux-4: online
└─ 2 flux-2: online
   ├─ 5 flux-5: online
   └─ 6 flux-6: online
```

Here are some testing scripts for ideas to distribute content via flux. The first one is doing a faux "pull" (some work that takes time) on broker 0 (which could be a container pull) and then creating an archive with it, and telling the other nodes to extract it, on two levels:

```bash
#!/bin/bash
# flux-distribute.sh

# This emulates a pull - just waste time and do nothing.
# We need to run (or submit with watch) to block until our imaginary file (layer) exists
flux run --requires rank:0 sleep 2
level_0=$(flux job last)

# The above would pull assets, let's fake it and do the next step - flux archive and then exec
guts=$(mktemp -p $(pwd) -t fake-container-guts-XXXXX)
guts_name=$(basename $guts)
guts_dir=$(dirname $guts)
flux archive create --name ${guts_name} --dir ${guts_dir} ${guts_name}

level_1=$(flux submit -N2 --requires rank:1,3 --dependency=after:$level_0 flux archive extract --name ${guts_name} -C ${guts_dir})
level_2=$(flux submit -N2 --requires rank:2,4 --dependency=after:$level_1 flux archive extract --name ${guts_name} -C ${guts_dir})
flux exec -r all ls ${guts_dir}fake*

# Clean up our fake assets
flux exec -r all rm -rf ${guts}
```

This next example would be a flat distribution - one pull, and then an extraction by all nodes without any middle level(s).

```bash
#!/bin/bash
# flat-distribute.sh

# This emulates a pull - just waste time and do nothing.
# We need to run (or submit with watch) to block until our imaginary file (layer) exists
flux run --requires rank:0 sleep 2
level_0=$(flux job last)

# The above would pull assets, let's fake it and do the next step - flux archive and then exec
guts=$(mktemp -p $(pwd) -t fake-container-guts-XXXXX)
guts_name=$(basename $guts)
guts_dir=$(dirname $guts)
flux archive create --name ${guts_name} --dir ${guts_dir} ${guts_name}

# Instead of trying to control extraction, just extract to all nodes at once
flux submit --watch -N4 --requires rank:1-4 --dependency=after:$level_0 flux archive extract --name ${guts_name} -C ${guts_dir})
flux exec -r all ls ${guts_dir}fake*

# Clean up our fake assets
flux exec -r all rm -rf ${guts}
```

We will continue with more scaled experiments in the subdirectories.
