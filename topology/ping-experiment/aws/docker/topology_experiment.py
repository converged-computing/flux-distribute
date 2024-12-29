#!/usr/bin/env python3

# usage
# python topology_experiment.py flux-sample
# will write the entrypoint script

import argparse
import stat
import os
from jinja2 import Template

# Template script for entrypoint
entrypoint_template = """
#!/bin/bash
# flux-topology.sh

flux exec -r all flux module reload content purge-target-size=104857600 # 100mb
echo "MODULE STATS CONTENT"
flux module stats content | jq

# Print the overlay to show the topology
echo "NODES"
echo "{{ nodes }}"
echo "TOPOLOGY diagram"
flux overlay status
echo "TOPOLOGY description"
echo "{{ topo }}"

# Get the total size (number of children)
ranks=$(flux getattr size)
echo "RANKS ${ranks}"

# But we are testing this many...
nodes={{ nodes }}

# We start counting at 0
max_rank="$((nodes-1))"

# --pad
# Include in the payload a string of length *N* bytes. *N* may be a floating point number with optional multiplicative suffix (K,M,G). The payload will be echoed back in the response. This option can be used to explore the effect of message size on latency. Default: no padding.

# Limit is 2G
# flux-ping: flux-ping: pad: value 8192M too large (must be < 2G)

# target may be the name of a Flux service, e.g. "kvs". :program:`flux ping` will send a request to "kvs.ping". As a shorthand, target can include a rank or host prefix delimited by an exclamation point. :program:`flux ping 4!kvs` is equivalent to :option:`flux ping --rank 4 kvs` (see :option:`--rank` option below). Don't forget to quote the exclamation point if it is interpreted by your shell.

# As a shorthand, target may also simply be a rank or host by itself indicating that the broker on that rank/host, rather than a Flux service, is to be pinged. :command:`flux ping 1` is equivalent to :option:`flux ping --rank 1 broker`.
# Sizes 0, 200, 400, 600, 800, 1000 M

# Run flux ping for each of the kvs and broker, across all ranks (testing the topology) and message sizes up to
# Go up to 1000MB (1GB) 
for size in $(echo 0 200 400 600 800 1000)
  do
  for rank in $(seq 0 ${max_rank})
    do
    echo "EVENT flux-ping-broker-size-${size}-rank-${rank}"
    flux ping -c1 --pad=${size}M --rank ${rank} broker
    echo "EVENT flux-ping-kvs-size-${size}-rank-${rank}"
    flux ping -c1 --pad=${size}M --rank ${rank} kvs
  done
done

# Show self!
echo "SCRIPT entrypoint"
cat $0
"""


def get_parser():
    parser = argparse.ArgumentParser(
        description="Topology Ping Experiment",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--topo",
        help="Topology description",
    )
    parser.add_argument(
        "--nodes",
        help="Total number of nodes",
    )
    parser.add_argument(
        "--entrypoint",
        help="Entrypoint script to write (defaults to /entrypoint.sh)",
        default="/entrypoint.sh",
    )
    return parser


def write_file(content, filename, executable=False):
    with open(filename, "w") as fd:
        fd.write(content)

    # Make the file executable
    if executable:
        st = os.stat(filename)
        os.chmod(filename, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def main():
    parser = get_parser()
    args, _ = parser.parse_known_args()

    # For each level, first derive testing commands to send data from rank0 to (leaves)
    render = {
        "nodes": str(args.nodes),
        "topo": args.topo,
    }
    template = Template(entrypoint_template)
    entrypoint = template.render(**render)

    # Write entrypoint script
    write_file(entrypoint, args.entrypoint, executable=True)


if __name__ == "__main__":
    main()
