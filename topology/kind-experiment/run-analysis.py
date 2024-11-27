#!/usr/bin/env python3

import matplotlib.pylab as plt
import seaborn as sns
import collections
import pandas
import argparse
import json
import os
import re

here = os.path.dirname(os.path.abspath(__file__))


def get_parser():
    parser = argparse.ArgumentParser(
        description="Parse analysis results",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--data",
        help="data directory with experiment events metadata to parse",
        default=os.path.join(here, "data", "raw"),
    )
    parser.add_argument(
        "--out",
        help="directory to save parsed results (with experiment prefix)",
        default=os.path.join(here, "data", "parsed"),
    )
    return parser


def recursive_find(base, pattern="*.*"):
    """
    Recursively find and yield files matching a glob pattern.
    """
    for root, _, filenames in os.walk(base):
        for filename in filenames:
            if not re.search(pattern, filename):
                continue
            yield os.path.join(root, filename)


def parse_event_time(timestamp):
    minutes = 0
    # First check for milliseconds, if reported in ms there aren't seconds or minutes
    if "ms" in timestamp:
        return float(timestamp.replace("ms", "", 1)) / 1000
    if "m" in timestamp:
        minutes, rest = timestamp.split("m", 1)
        minutes = int(minutes)
        timestamp = rest
    seconds = float(timestamp.rstrip("s"))
    return (minutes * 60) + seconds


def find_inputs(input_dir):
    """
    Find inputs (times results files)
    """
    files = []
    # This should find topology-experiment.out
    for filename in recursive_find(input_dir, pattern="[.]out"):
        # We only have data for small
        files.append(filename)
    return files


def main():
    """
    Find times/events* files to parse.
    """
    parser = get_parser()
    args, _ = parser.parse_known_args()

    # Output images and data
    outdir = os.path.abspath(args.out)
    indir = os.path.abspath(args.data)
    if not os.path.exists(outdir):
        os.makedirs(outdir)

    # Find input files (skip anything with test)
    files = find_inputs(indir)
    if not files:
        raise ValueError(f"There are no input files in {indir}")

    # Saves raw data to file
    df = parse_data(indir, outdir, files)
    plot_times(df, outdir)


def read_file(filename):
    with open(filename, "r") as fd:
        content = fd.read()
    return content


def write_json(obj, filename):
    with open(filename, "w") as fd:
        fd.write(json.dumps(obj, indent=4))


def parse_data(indir, outdir, files):
    # Assemble results across filenames
    df = pandas.DataFrame(
        columns=[
            "uid",
            "topology",
            "iteration",
            "nodes",
            "event",
            "size_gb",
            "time_seconds",
        ]
    )
    results = {}
    idx = 0
    for filename in files:
        parts = filename.split(os.sep)
        topology = parts[-3]
        nodes = int(parts[-4])
        iteration = int(parts[-2])
        uid = f"{topology.replace(':', '-')}-{nodes}"
        events = read_file(filename)
        events, script = events.split("SCRIPT entrypoint", 1)
        lines = events.split("\n")

        # Topology diagram
        idx_start = [i for i, x in enumerate(lines) if "TOPOLOGY diagram" in x][0]
        idx_end = [i for i, x in enumerate(lines) if "TOPOLOGY description" in x][0]
        results[uid] = lines[idx_start + 1 : idx_end]

        # The rest is events
        title = None
        lines = lines[idx_end + 2 :]
        while lines:
            line = lines.pop(0)
            if not line.strip():
                continue
            if "EVENT" in line:
                title = line.split(" ")[-1]
                title = title.rsplit("-", 1)
                size_gb = int(title[-1])
                title = title[0]
                while "real" not in line:
                    line = lines.pop(0)
                timestamp = parse_event_time(line.split("\t")[-1])
                df.loc[idx, :] = [
                    uid,
                    topology,
                    iteration,
                    nodes,
                    title,
                    size_gb,
                    timestamp,
                ]
                idx += 1

    # This is the primary raw data we are interested in.
    topology_file = os.path.join(outdir, "topologies.json")
    write_json(results, topology_file)
    df_file = os.path.join(outdir, "topologies-events.csv")
    df.to_csv(df_file)
    return df


def plot_times(df, outdir):
    for event in df.event.unique():
        print(f"Plotting event {event}")
        event_subset = df[df.event == event]
        for nodes in df.nodes.unique():
            subset = event_subset[event_subset.nodes == nodes]
            topos = list(subset.topology.unique())
            colors = sns.color_palette("hls", len(topos))
            hexcolors = colors.as_hex()
            palette = collections.OrderedDict()
            for t in topos:
                palette[t] = hexcolors.pop(0)

            ax = make_plot(
                subset,
                title=f"Data Movement for {event} at Size {nodes} Nodes Across Topology",
                ydimension="time_seconds",
                xdimension="size_gb",
                outdir=outdir,
                ext="png",
                plotname=f"{event}-nodes-{nodes}",
                hue="topology",
                palette=palette,
                plot_type="bar",
                xlabel="Size of Data (GB)",
                ylabel="Time (Seconds)",
                # do_log=True,
                # With log, no ylimit
                # ylim=None,
            )


def make_plot(
    df,
    title,
    ydimension,
    xdimension,
    xlabel,
    ylabel,
    palette=None,
    ext="pdf",
    plotname="lammps",
    plot_type="violin",
    hue=None,
    outdir="img",
    do_log=False,
    ylim=None,
):
    """
    Helper function to make common plots.
    """
    plotfunc = sns.lineplot
    if plot_type == "violin":
        plotfunc = sns.violinplot

    ext = ext.strip(".")
    plt.figure(figsize=(7, 3))
    sns.set_style("dark")
    if plot_type == "violin":
        ax = plotfunc(
            x=xdimension,
            y=ydimension,
            hue=hue,
            data=df,
            linewidth=0.8,
            palette=palette,
            marker="o",
        )
    else:
        ax = plotfunc(
            x=xdimension,
            y=ydimension,
            hue=hue,
            data=df,
            linewidth=1.8,
            palette=palette,
            # whis=[5, 95],
            # dodge=True,
        )
        # This range is specifically for pulling times -
        # so the ranges are equivalent
        if ylim is not None:
            ax.set(ylim=ylim)

    if do_log:
        plt.yscale("log")
    plt.title(title)
    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_xticklabels(ax.get_xmajorticklabels(), fontsize=14)
    ax.set_yticklabels(ax.get_yticks(), fontsize=14)
    sns.move_legend(ax, "upper left", bbox_to_anchor=(1, 1))
    plt.xticks(rotation=90)
    plt.tight_layout()
    plt.savefig(os.path.join(outdir, f"{plotname}.png"))
    plt.clf()
    return ax


if __name__ == "__main__":
    main()
