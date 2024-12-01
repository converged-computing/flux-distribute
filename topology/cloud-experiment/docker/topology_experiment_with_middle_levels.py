#!/usr/bin/env python3

# usage
# python topology_experiment.py flux-sample
# will write the entrypoint script

import argparse
import sys
import subprocess
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

# Go up to 10 sizes for now (matches container size)
for size in $(seq {{ min_size }} {{ max_size }})
  do
    # Create the archive and time it
    echo "EVENT create-archive-${size}"
    time {% if valgrind_create %}valgrind --leak-check=full{% endif %} flux archive create --name create-archive-${size} --dir /chonks ${size}gb.txt

    # Distribute to all nodes, but to /tmp because file exists in /chonks
    echo "EVENT distribute-all-nodes-${size}"
    time flux exec -r all -x 0 {% if valgrind_extract %}valgrind --leak-check=full{% endif %} flux archive extract --name create-archive-${size} -C /tmp

    # Cleanup all archive on all nodes
    echo "EVENT clean-all-nodes-${size}"
    time flux exec -r all rm -rf /tmp/${size}gb.txt

    echo "EVENT delete-archive-all-nodes-${size}"
    time flux exec -r all {% if valgrind_remove %}valgrind --leak-check=full{% endif %} flux archive remove --name create-archive-${size} 2>/dev/null

    # Next, do the same for the root node (level 0) to the deepest level (leaves)
    echo "EVENT create-leaf-nodes-${size}"
    time flux archive create --name create-archive-leaves-${size} --dir /chonks ${size}gb.txt
    echo "EVENT distribute-leaf-nodes-${size}"
    time flux exec -r {{leaf_nodes}} -x 0 {% if valgrind_extract %}valgrind --leak-check=full{% endif %} flux archive extract --name create-archive-leaves-${size} -C /tmp
    # Cleanup again    
    echo "EVENT clean-leaf-nodes-${size}"
    time flux exec -r all rm -rf /tmp/${size}gb.txt
    echo "EVENT delete-archive-leaf-nodes-${size}"
    time flux exec -r all flux archive remove --name create-archive-leaves-${size} 2>/dev/null

    # Finally, get the middle node and distribute to middle level first, then middle to last
    echo "EVENT create-middle-nodes-${size}"
    time flux archive create --name create-archive-middle-${size} --dir /chonks ${size}gb.txt
    echo "EVENT distribute-middle-nodes-0-${size}"
    time flux exec -r {{middle_nodes}} -x 0 {% if valgrind_extract %}valgrind --leak-check=full{% endif %} flux archive extract --name create-archive-middle-${size} -C /tmp
    echo "EVENT distribute-middle-nodes-1-${size}"
    time flux exec -r {{leaf_nodes}} -x 0 {% if valgrind_extract %}valgrind --leak-check=full{% endif %} flux archive extract --name create-archive-middle-${size} -C /tmp
    echo "EVENT clean-middle-nodes-${size}"
    time flux exec -r all rm -rf /tmp/${size}gb.txt
    echo "EVENT delete-archive-middle-nodes-${size}"
    time flux exec -r all flux archive remove --name create-archive-middle-${size} 2>/dev/null
done

# Show self!
echo "SCRIPT entrypoint"
cat $0
"""

def get_parser():
    parser = argparse.ArgumentParser(
        description="Kary Generator",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--middle-nodes",
        help="List of middle nodes",
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
        "--leaf-nodes",
        help="List of leaf nodes",
    )
    parser.add_argument(
        "--valgrind-create",
        help="Wrap create with valgrind",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--valgrind-remove",
        help="Wrap remove with valgrind",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--valgrind-extract",
        help="Wrap extract with valgrind",
        default=False,
        action="store_true",
    )    
    parser.add_argument(
        "--min-size",
        help="Min size gb file to expect in container",
        default=1,
        type=int,
    )
    parser.add_argument(
        "--max-size",
        help="Max size gb file to expect in container",
        default=10,
        type=int,
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

    # Size sanity checks
    if args.min_size > args.max_size:
        raise ValueError("Min size cannot be > Max size.")

    if args.min_size < 1 or args.max_size < 1:
        raise ValueError("Min and Max sizes cannot be less than 1")
    
    # For each level, first derive testing commands to send data from rank0 to (leaves)
    render = {
        "leaf_nodes": args.leaf_nodes,
        "middle_nodes": args.middle_nodes,
        "min_size": args.min_size,
        "max_size": args.max_size,
        "nodes": str(args.nodes),
        "topo": args.topo,
        "valgrind_remove": args.valgrind_remove,
        "valgrind_extract": args.valgrind_extract,
        "valgrind_create": args.valgrind_create,
    }
    template = Template(entrypoint_template)
    entrypoint = template.render(**render)

    # Write entrypoint script
    write_file(entrypoint, args.entrypoint, executable=True)

if __name__ == "__main__":
    main()
