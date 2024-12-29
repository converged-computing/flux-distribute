# Flux Topology (ping) Experiment

> You can use flux ping to measure latency - The wise Garlick

## Details

- A result from flux ping (broadly) would reflect a result that uses other flux messages
- Job events are entries in an eventlog, very high level.  Event messages are pub/sub broadcasts
- Sounds like the ping is a better (simpler) measure to reflect a topology design?
- flux ping lets you measure message latency bewteen two points in the topology. You can also pad the ping packet with data to see how that affects latency.

> OK this is a good direction. I can start with the thought nugget of (instead of using flux as a data distribution with archive) as a means to send messages, and then of different sizes. I can do an equivalent experiment (much cheaper to not wait for archive/extract) that tries to measure different sizes of clusters / topologies (and I can mess with padding) and then (key) will be figuring out a use case in kubernetes where this is interesting to have, e.g., communication between nodes.

```bash
An example of ping from rank 0 to rank 1 vs rank 15 in a kary:1 topology:
$ flux ping -c1 '1!kvs'
flux-ping 1!kvs
1!kvs.ping pad=0 seq=0 time=0.325 ms (832dc794!19db4c61!b28587bb!ff3181bc!3fc35227)
$ flux ping -c1 '15!kvs'
flux-ping 15!kvs
15!kvs.ping pad=0 seq=0 time=3.111 ms (09c76965!19db4c61!b28587bb!ff3181bc!7220370d!995323db!fb8c5e14!71749354!81d4044a!e5d3f886!5631e912!4ba32649!b6dde8d3!53456c63!7d804878!72d85179!fffc4573!e9f31837!9b84352c)
```

See the script in [docker](docker) for description of what the above means. Note that we can also test pings to/from [anywhere in the topolog](https://github.com/flux-framework/flux-core/blob/59cbf5e91f3c936aede77d2b6ec9d598e4ad6754/t/t0007-ping.t#L125) using flux exec.

## Usage

We are now going to use our topologies to drive an experiment. For testing, we will just run a subset in kind.
Create the cluster:

```bash
kind create cluster --config ./kind-config.yaml 
```

Install the Flux Operator

```bash
kubectl apply -f https://raw.githubusercontent.com/flux-framework/flux-operator/refs/heads/main/examples/dist/flux-operator.yaml
```

Run the experiment! Note that the sizes aren't being passed anywhere at the moment.

```bash
python run-experiment.py --data ./kary-designs.json --iters=3 --max-nodes=4
```
```console
Experiments are done!
total time to run is 3782.7171614170074 seconds
```

