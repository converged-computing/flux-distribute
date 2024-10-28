FROM ubuntu:22.04
# docker build -t ghcr.io/converged-computing/flux-distribute:latest .
# docker push ghcr.io/converged-computing/flux-distribute:latest
WORKDIR /flux-install
COPY docker/* .
RUN chmod +x /flux-install/entrypoint.sh
ENTRYPOINT ["/flux-install/entrypoint.sh"]
