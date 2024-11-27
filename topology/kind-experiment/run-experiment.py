#!/usr/bin/env python3

import argparse
import json
import os
import time
import sys
from jinja2 import Template

from kubernetes import client, config

config.load_kube_config()

# import the script we have two levels up
here = os.path.abspath(os.path.dirname(__file__))


def read_file(filename):
    with open(filename, "r") as fd:
        content = fd.read()
    return content


def write_file(content, filename):
    with open(filename, "w") as fd:
        fd.write(content)


minicluster_template = read_file(os.path.join(here, "minicluster.yaml"))
template = Template(minicluster_template)

# Max number of nodes for m-ary tree with k levels
# n = (mk − 1) / (m − 1)


def get_parser():
    parser = argparse.ArgumentParser(
        description="Topology Experiment Running",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--name",
        help="name for minicluster (defaults to flux-sample)",
        default="flux-sample",
    )
    parser.add_argument(
        "--data-dir",
        help="path to save data",
        default=os.path.join(here, "data", "raw"),
    )
    parser.add_argument(
        "--max-size",
        help="Maximum size to transfer",
        default=10,
        type=int,
    )
    parser.add_argument(
        "--iters",
        help="Iterations per experiment",
        default=5,
        type=int,
    )
    parser.add_argument(
        "--data",
        help="path to kary designs json",
        default=os.path.join(here, "kary-designs.json"),
    )
    return parser


def read_json(filename):
    """
    Read json from file.
    """
    with open(filename, "r") as fd:
        content = json.loads(fd.read())
    return content


def confirm_action(question):
    """
    Ask for confirmation of an action
    """
    response = input(question + " (yes/no)? ")
    while len(response) < 1 or response[0].lower().strip() not in "ynyesno":
        response = input("Please answer yes or no: ")
    if response[0].lower().strip() in "no":
        return False
    return True


def generate_uid(params):
    """
    Generate a unique id based on params.
    """
    uid = ""
    for k, v in params.items():
        if not isinstance(v, dict):
            uid += k.lower() + "-" + str(v).lower()
        else:
            uid += k.lower()
    return uid


def write_json(obj, filename):
    """
    write json to output file
    """
    with open(filename, "w") as fd:
        fd.write(json.dumps(obj, indent=4))


def run_topology_experiment(exp, args, nodes_dir):
    """
    Run the topology experiment.
    """
    nodes = exp["nodes"]
    render = {
        "nodes": nodes,
        "topo": exp["topo"],
        "name": args.name,
        "max_size": args.max_size,
    }
    outfile = os.path.join(nodes_dir, "topology-experiment.out")
    if os.path.exists(outfile):
        print(f"{outfile} exists, skipping")
        return False
    print(f"\n🍔 Running topology experiment size {nodes}")
    levels = exp["levels"]

    # Get the last level - where the leaves are
    all_levels = list(levels)
    all_levels.sort()
    deepest_level = all_levels[-1]

    # This will be lower half
    middle_level = str(int(len(all_levels) / 2))

    # For each level, first derive testing commands to send data from rank0 to (leaves)
    render.update(
        {
            "leaf_nodes": ",".join(levels[deepest_level]),
            "middle_nodes": ",".join(levels[middle_level]),
        }
    )
    render = template.render(**render)
    minicluster_yaml = os.path.join(nodes_dir, "minicluster.yaml")
    write_file(render, minicluster_yaml)
    run_kubectl(f"apply -f {minicluster_yaml}")
    time.sleep(10)

    # This will wait for it to finish
    run_kubectl(f"wait --for=condition=complete --timeout=600s job/{args.name}")

    cli = client.CoreV1Api()
    for pod in cli.list_namespaced_pod(namespace="default").items:
        if f"{args.name}-0" in pod.metadata.name:
            log = cli.read_namespaced_pod_log(
                name=pod.metadata.name, namespace="default"
            )
            break

    if "Segmentation fault" in log or "Segment" in log:
        print(f"Possible segmentation fault for {exp}!")

    # Save to file
    print(f"Writing topology log and recordings to {outfile}")
    write_file(log, outfile)

    # Wait for all pods to terminate
    run_kubectl(f"delete -f {minicluster_yaml} --wait=true", allow_fail=True)
    return True


def run_kubectl(command, allow_fail=False):
    """
    Wrapper to client to run command with kubeconfig file
    """
    command = f"kubectl {command}"
    res = os.system(command)
    if res != 0 and not allow_fail:
        print(
            f"ERROR: running {command} - debug and ensure it works before exiting from session."
        )
        import IPython

        IPython.embed()
    return res


def run_experiments(args, plans):
    """
    Generate runs for topology sizes
    """
    # Note that the experiment already has a table of values filtered down
    # Each experiment has some number of batches (we will typically just run one experiment)
    total = len(plans)
    count = 0
    for i, exp in enumerate(plans):
        print(f"== Running experiment {exp}: {i} of {total}")

        # Save the entire table just once
        topo = exp["topo"].replace(":", "-")

        for ii in range(args.iters):
            nodes = exp["nodes"]
            if nodes > 6:
                continue
            path = os.path.join(args.data_dir, str(nodes), topo, str(ii))
            if not os.path.exists(path):
                os.makedirs(path)

            # EXPERIMENTS: ---
            # Run LAMMPS a number of iterations in the cluster
            # This writes all iteration runs to one output file
            try:
                if run_topology_experiment(exp, args, path):
                    count += 1
            except:
                print(f"Issue with {exp} - investigate!")

    print("Experiments are done!")


def main():
    """
    Run experiments for lammps, and collect hwloc info.
    """
    parser = get_parser()

    # If an error occurs while parsing the arguments, the interpreter will exit with value 2
    args, _ = parser.parse_known_args()
    if not os.path.exists(args.data_dir):
        os.makedirs(args.data_dir)

    # Read in kary designs
    if not os.path.exists(args.data):
        sys.exit(f"{args.data} does not exist.")
    plans = read_json(args.data)

    # plan experiments!
    print("🧪️ Experiments:")
    print("🪴️ Planning to run:")
    print(f"   Output Data         : {args.data_dir}")
    print(f"   Experiments         : {len(plans)}")
    print(f"      Max Size         : {args.max_size}")
    print(f"         Iters         : {args.iters}")
    if not confirm_action("Would you like to continue?"):
        sys.exit("📺️ Cancelled!")

    # Main experiment running, show total time just for user FYI
    start_experiments = time.time()
    run_experiments(args, plans)
    stop_experiments = time.time()
    total = stop_experiments - start_experiments
    print(f"total time to run is {total} seconds")


if __name__ == "__main__":
    main()
