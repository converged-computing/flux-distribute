#!/usr/bin/env python3

# This can be run in a container with flux! Shell in, and:
# python3 kary_generator.py --job-name $(hostname)
# mkdir -p /tmp/kary
# cd /tmp/kary
# docker run -v /tmp/kary:/data -it fluxrm/flux-sched:jammy
import argparse
import subprocess
import json
import os
import sys
import copy
import re


def get_parser():
    parser = argparse.ArgumentParser(
        description="Kary Generator",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--min-kary",
        help="minimum value of k (defaults to 1)",
        default=1,
        type=int,
    )
    parser.add_argument(
        "--job-name",
        help="name of the job (or cluster prefix)",
        default="flux-sample",
    )
    parser.add_argument(
        "--max-kary",
        help="maximum value of k (defaults to 32)",
        default=32,
        type=int,
    )
    parser.add_argument(
        "--min-nodes",
        help="minimum number of nodes (defaults to 4)",
        default=30,
        type=int,
    )
    parser.add_argument(
        "--max-nodes",
        help="maximum number of nodes (defaults to 32)",
        default=32,
        type=int,
    )
    parser.add_argument(
        "--outfile",
        help="Output file prefix (json and text) for experiment designs",
        default="kary-designs",
    )
    return parser


class TopologyParser:
    def __init__(self, job_name):
        self.job_name = job_name
        self.seen = set()
        self.results = []
        self.topos = {}

    def parse(self, nodes, topo):
        """
        Parse into a result.

        Return None if we deem it not interesting, meaning most of
        the nodes are children of the root (and the topology is not
        super interesting).
        """
        result = {"nodes": nodes, "topo": topo}
        p = subprocess.Popen(
            [
                "flux",
                "start",
                "-o",
                f"-Stbon.topo={topo}",
                f"--test-size={nodes}",
                "flux",
                "overlay",
                "status",
            ],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        out, err = p.communicate()
        out = out.decode("utf-8")
        levels = self.parse_levels(out, nodes)

        # If we have more than one level, ensure the direct children of root
        # >= half the nodes, which indicate a mostly flat graph (our stopping point)
        if len(levels) > 1 and len(levels[1]) > int(nodes / 2):
            return
        result["levels"] = levels
        result["out"] = out
        return self.add_result(result)

    def add_result(self, result):
        """
        Determine to add a result (or not)
        """
        if result and result["out"] not in self.seen:
            print(f"Nodes {result['nodes']} and {result['topo']}")
            topology = result["out"]
            print(topology)
            # Remove result -> out (topology) print
            uid = f"nodes-{result['nodes']}-topo-{result['topo']}"
            self.topos[uid] = copy.deepcopy(result)
            del result["out"]
            self.results.append(result)
            self.seen.add(topology)
            # We haven't seen it yet
            return False
        # We have seen it!
        return True

    def parse_levels(self, out, nodes):
        """
        Parse levels from output into structure.
        """
        import IPython

        IPython.embed()
        sys.exit()
        levels = {0: ["0"]}
        seen = set()
        for i, line in enumerate(out.split("\n")):
            if not line:
                continue
            # First line is always the lead
            if i == 0:
                continue
            # The identifier is right before the name
            line = line.split(self.job_name, 1)

            # The first part we can parse up to the number to get the level
            rank = int(re.search("[0-9]+", line[0]).group())
            for level, char in enumerate(line[0]):
                try:
                    int(char)
                except:
                    continue
                # Each level is 3 in
                level = int(level / 3)
                break

            worker = f"{self.job_name}-{rank}"
            if worker in seen:
                continue
            seen.add(worker)
            # Level 0 (broker) just has a number
            if level not in levels:
                levels[level] = []
            levels[level].append(str(rank))
        return levels


def main():
    parser = get_parser()
    args, _ = parser.parse_known_args()

    min_nodes = int(args.min_nodes)
    max_nodes = int(args.max_nodes)
    min_k = int(args.min_kary)
    max_k = int(args.max_kary)

    # Create a topology parser for the job prefix
    p = TopologyParser(args.job_name)

    for nodes in range(min_nodes, max_nodes):
        # Add binomial structure first
        p.parse(nodes, "binomial")

        for kary in range(min_k, max_k):
            # Break if we have seen it before
            if p.parse(nodes, f"kary:{kary}"):
                break

    with open(f"{args.outfile}.json", "w") as fd:
        fd.write(json.dumps(p.results, indent=4))

    with open(f"{args.outfile}-topology.json", "w") as fd:
        fd.write(json.dumps(p.topos, indent=4))

    with open(f"{args.outfile}.txt", "w") as fd:
        for topo, stdout in p.topos.items():
            fd.write(f"{topo}\n")
            fd.write(stdout["out"] + "\n")


if __name__ == "__main__":
    main()
