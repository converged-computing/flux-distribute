FROM fluxrm/flux-sched:jammy
USER root
# docker build -t ghcr.io/converged-computing/topology-experiment:test .
# docker push ghcr.io/converged-computing/topology-experiment:test
# kind load docker-image ghcr.io/converged-computing/topology-experiment:test
RUN apt-get update && apt-get install -y python3-pip && \
    python3 -m pip install Jinja2 && \
    apt-get clean
COPY ./topology_experiment.py /topology_experiment.py
