.PHONY: all build

all: build

# This logic was moved from upstream/hack/build-images.sh - too much changing logic
# and became hard to maintain
build:
	docker build -t ghcr.io/converged-computing/flux-distribute:latest .

push: build
	docker push ghcr.io/converged-computing/flux-distribute:latest
	sleep 2

# Assume testing with kind
test: push
	kubectl delete -f daemonset-installer.yaml || true
	kubectl apply -f daemonset-installer.yaml