#!/usr/bin/env python3

import argparse
import json
import os
import time
import sys
import re
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
        "--min-size",
        help="Minimum size (GB) to transfer, up to 10",
        default=1,
        type=int,
    )
    parser.add_argument(
        "--max-size",
        help="Maximum size (GB) to transfer, up to 10",
        default=10,
        type=int,
    )
    parser.add_argument(
        "--exact-nodes",
        help="Exact node count to use",
        default=None,
        type=int,
    )
    parser.add_argument(
        "--template",
        help="minicluster.yaml template to use",
        default=os.path.join(here, "templates", "minicluster.yaml"),
    )
    parser.add_argument(
        "--max-nodes",
        help="Maximum nodes from design to use",
        default=None,
        type=int,
    )
    parser.add_argument(
        "--topo",
        help="Filter to run just one or more topologies",
        action="append",
        default=None,
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
        "min_size": args.min_size,
    }
    outfile = os.path.join(nodes_dir, "topology-experiment.out")
    if os.path.exists(outfile):
        print(f"{outfile} exists, skipping")
        return False
    print(f"\n🍔 Running topology experiment size {nodes}")

    # Skip levels for now - extra time and might be buggy to do?
    # levels = exp["levels"]
    # Get the last level - where the leaves are
    # all_levels = list(levels)
    # all_levels.sort()
    # deepest_level = all_levels[-1]
    # This will be lower half
    # middle_level = str(int(len(all_levels) / 2))

    # Load the minicluster template
    minicluster_template = read_file(args.template)
    template = Template(minicluster_template)

    # Render into it
    render = template.render(**render)
    minicluster_yaml = os.path.join(nodes_dir, "minicluster.yaml")
    write_file(render, minicluster_yaml)
    run_kubectl(f"apply -f {minicluster_yaml}")
    time.sleep(10)

    # This will wait for it to finish
    # The long waiting time is based on the 10GB size, 30 minutes
    run_kubectl(f"wait --for=condition=complete --timeout=3000s job/{args.name}")

    cli = client.CoreV1Api()
    for pod in cli.list_namespaced_pod(namespace="default").items:
        if f"{args.name}-0" in pod.metadata.name:
            log = cli.read_namespaced_pod_log(
                name=pod.metadata.name, namespace="default"
            )
            break

    # This should no longer be an issue
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


def filter_plans(args, plans):
    """
    Filter plans in advance to tell user how many experiments we will run
    """
    # Quick hack so we don't need to regenerate the topology file for larger size
    updated = []
    if args.exact_nodes == 256 and args.topo is not None:
        for topo in args.topo:
            updated.append({"nodes": 256, "topo": topo})
    print(updated)
    return updated

    for exp in plans:
        nodes = exp["nodes"]
        topo = exp["topo"].replace(":", "-")
        if args.topo is not None and exp["topo"] not in args.topo:
            continue
        if args.exact_nodes is not None and nodes != args.exact_nodes:
            continue
        elif args.max_nodes is not None and nodes > args.max_nodes:
            continue
        updated.append(exp)
    return updated


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
        nodes = exp["nodes"]
        for ii in range(args.iters):
            path = os.path.join(args.data_dir, str(nodes), topo, str(ii))
            if not os.path.exists(path):
                os.makedirs(path)

            # EXPERIMENTS: ---
            try:
                if run_topology_experiment(exp, args, path):
                    count += 1
            except:
                print(f"Issue with {exp} - investigate!")

    print(f"Experiments (N={count}) are done!")


def validate(args):
    """
    Validate args, primarily sizes
    """
    if args.min_size > args.max_size:
        raise ValueError("Min size cannot be > Max size.")
    if args.min_size < 1 or args.max_size < 1:
        raise ValueError("Min and Max sizes cannot be less than 1")
    if args.max_size > 10:
        raise ValueError("Currently only support for 10GB.")
    if args.max_nodes and args.exact_nodes:
        raise ValueError("You must choose one of --max-nodes OR --exact-nodes")


def main():
    """
    Run experiments for lammps, and collect hwloc info.
    """
    parser = get_parser()

    # If an error occurs while parsing the arguments, the interpreter will exit with value 2
    args, _ = parser.parse_known_args()
    if not os.path.exists(args.data_dir):
        os.makedirs(args.data_dir)

    # Validate sizes and relationships between them
    validate(args)

    # Read in kary designs
    if not os.path.exists(args.data):
        sys.exit(f"{args.data} does not exist.")
    plans = read_json(args.data)

    # Filter plans so we can show user exactly number to run
    plans = filter_plans(args, plans)

    # plan experiments!
    print("🧪️ Experiments:")
    print("🪴️ Planning to run:")
    print(f"   Output Data         : {args.data_dir}")
    print(f"   Experiments         : {len(plans)}")
    if args.exact_nodes:
        print(f"   Exact Nodes         : {args.exact_nodes}")
    if args.max_nodes:
        print(f"     Max Nodes         : {args.max_nodes}")
    print(f"      Min Size         : {args.min_size}")
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
