# The environment agents work in. It runs with no network, so everything an
# agent might need has to be installed here. Changing this image can change
# results, so note it in the changelog when you do.
# Pinned by digest so every run uses the same base image; Dependabot proposes updates.
FROM debian:stable-slim@sha256:eb593cf2c358cacef45ca0a424bbc7d30cfa3466265fc2662b9466a0ca6ba1c5

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      bash coreutils findutils grep sed gawk procps file less \
      binutils xxd bsdextrautils gdb strace \
      unzip zip p7zip-full tar gzip bzip2 xz-utils \
      git sqlite3 jq libimage-exiftool-perl \
      python3 python3-pip python3-gmpy2 python3-pil python3-scapy \
      ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages --require-hashes -r /tmp/requirements.txt \
 && rm /tmp/requirements.txt

RUN useradd --create-home --uid 1000 --shell /bin/bash agent \
 && mkdir /work && chown agent:agent /work

USER agent
WORKDIR /work
CMD ["sleep", "infinity"]
