FROM ubuntu:latest

# This is a custom flux base to use for the experiments since the spack view builds are failing
# docker build -t ghcr.io/converged-computing/flux-view-ubuntu:tag-noble-flux-0.66.0 .

RUN apt-get update && \
    apt-get -qq install -y --no-install-recommends \
        apt-utils && \
    rm -rf /var/lib/apt/lists/*

# Utilities
RUN apt-get update && \
    apt-get -qq install -y --no-install-recommends \
        locales \
        ca-certificates \
        wget \
        man \
        git \
        flex \
        ssh \
        sudo \
        vim \
        luarocks \
        munge \
        lcov \
        ccache \
        lua5.4 \
        mpich \
        valgrind \
        jq && \
    rm -rf /var/lib/apt/lists/*

# Compilers, autotools
RUN apt-get update && \
    apt-get -qq install -y --no-install-recommends \
        build-essential \
        pkg-config \
        autotools-dev \
        libtool \
	libffi-dev \
        autoconf \
        automake \
        make \
        cmake \
        clang \
        clang-tidy \
        gcc \
        python3-dev \
        python3-pip \
        g++ && \
    rm -rf /var/lib/apt/lists/*

# Python - instead of a system python we install anaconda
# https://docs.conda.io/en/latest/miniconda.html#linux-installers
RUN python3 -m pip install --upgrade --ignore-installed --break-system-packages \
        "markupsafe==2.0.0" \
        coverage cffi ply six pyyaml "jsonschema>=2.6,<4.0" \
        sphinx sphinx-rtd-theme sphinxcontrib-spelling

# Other deps
RUN apt-get update && \
    apt-get -qq install -y --no-install-recommends \
        libsodium-dev \
        libzmq3-dev \
        libczmq-dev \
        libjansson-dev \
        libmunge-dev \
        libncursesw5-dev \
        liblua5.2-dev \
        liblz4-dev \
        libsqlite3-dev \
        uuid-dev \
        libhwloc-dev \
        libmpich-dev \
        libs3-dev \
        libevent-dev \
        libarchive-dev \
        libpam-dev && \
    rm -rf /var/lib/apt/lists/*

# Testing utils and libs
RUN apt-get update && \
    apt-get -qq install -y --no-install-recommends \
        faketime \
        libfaketime \
        pylint \
        cppcheck \
        aspell \
        aspell-en && \
    rm -rf /var/lib/apt/lists/*

RUN locale-gen en_US.UTF-8

# NOTE: luaposix installed by rocks due to Ubuntu bug: #1752082 https://bugs.launchpad.net/ubuntu/+source/lua-posix/+bug/1752082
RUN luarocks install luaposix

# Install openpmix, prrte
WORKDIR /opt/prrte
RUN git clone https://github.com/openpmix/openpmix.git && \
    git clone https://github.com/openpmix/prrte.git && \
    ls -l && \
    set -x && \
    cd openpmix && \
    git checkout fefaed568f33bf86f28afb6e45237f1ec5e4de93 && \
    ./autogen.pl && \
    ./configure --prefix=/usr --disable-static && make -j 4 install && \
    ldconfig && \
    cd .. && \
    cd prrte && \
    git checkout 477894f4720d822b15cab56eee7665107832921c && \
    ./autogen.pl && \
    ./configure --prefix=/usr && make -j 4 install && \
    cd ../.. && \
    rm -rf prrte

ENV LANG=C.UTF-8
RUN apt-get update && apt-get install -y python3-dev && apt-get clean

# This is from the docker check script (run interactively during a test)
# https://github.com/flux-framework/flux-core/blob/master/src/test/docker/checks/Dockerfile
ARG FLUX_SECURITY_VERSION=0.13.0

# Install flux-security by hand for now:
#
WORKDIR /opt
RUN CCACHE_DISABLE=1 && \
    V=$FLUX_SECURITY_VERSION && \
    PKG=flux-security-$V && \
    URL=https://github.com/flux-framework/flux-security/releases/download && \
    wget ${URL}/v${V}/${PKG}.tar.gz && \
    tar xvfz ${PKG}.tar.gz && \
    cd ${PKG} && \
    ./configure --prefix=/usr --sysconfdir=/etc && \
    make -j 4 && \
    make install && \
    cd .. && \
    rm -rf flux-security-*

# Setup MUNGE directories & key
RUN mkdir -p /var/run/munge && \
    dd if=/dev/urandom bs=1 count=1024 > /etc/munge/munge.key && \
    chown -R munge /etc/munge/munge.key /var/run/munge && \
    chmod 600 /etc/munge/munge.key

# Build flux core
# This I added and copied how to build with caliper / flux security enabled
# https://github.com/flux-framework/flux-core/blob/master/src/test/docker/docker-run-checks.sh#L185-L191
RUN git clone https://github.com/flux-framework/flux-core && \
    cd flux-core && \
    git fetch && \
    export FLUX_VERSION=0.66.0 && \
    ./autogen.sh && \
    ./configure --prefix=/usr --sysconfdir=/etc --localstatedir=/var \
        --with-flux-security && \
    make clean && \
    make && \
    sudo make install

# This is from the same src/test/docker/bionic/Dockerfile but in flux-sched
# Flux-sched deps
RUN sudo apt-get update
RUN sudo apt-get -qq install -y --no-install-recommends \
	libboost-graph-dev \
	libboost-system-dev \
	libboost-filesystem-dev \
	libboost-regex-dev \
	libyaml-cpp-dev \
	libedit-dev

# Build Flux Sched	
# https://github.com/flux-framework/flux-sched/blob/master/src/test/docker/docker-run-checks.sh#L152-L158
RUN git clone --depth 1 https://github.com/flux-framework/flux-sched && \
    cd flux-sched && \
    mkdir ./build && \
    cd ./build && \
    cmake ../ && \
    make && \
    sudo make install && \
    ldconfig
