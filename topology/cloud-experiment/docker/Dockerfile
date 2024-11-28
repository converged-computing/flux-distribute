FROM rockylinux:9

# docker build -t ghcr.io/converged-computing/container-chonks:topology-test .
# docker push ghcr.io/converged-computing/container-chonks:topology-test

# 1GB to 10GB!
WORKDIR /chonks
RUN head -c 1000000000 /dev/zero > ./1gb.txt
RUN head -c 2000000000 /dev/zero > ./2gb.txt
RUN head -c 3000000000 /dev/zero > ./3gb.txt
RUN head -c 4000000000 /dev/zero > ./4gb.txt
RUN head -c 5000000000 /dev/zero > ./5gb.txt
RUN head -c 6000000000 /dev/zero > ./6gb.txt
RUN head -c 7000000000 /dev/zero > ./7gb.txt
RUN head -c 8000000000 /dev/zero > ./8gb.txt
RUN head -c 9000000000 /dev/zero > ./9gb.txt
RUN head -c 10000000000 /dev/zero > ./10gb.txt
COPY ./topology_experiment.py /topology_experiment.py
