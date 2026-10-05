# The environment agents work in. It runs with no network, so everything an
# agent might need has to be installed here.
FROM debian:stable-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      bash coreutils findutils grep sed gawk procps file \
      binutils xxd bsdextrautils unzip tar gzip bzip2 xz-utils \
      python3 python3-pip ca-certificates \
 && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 --shell /bin/bash agent \
 && mkdir /work && chown agent:agent /work

USER agent
WORKDIR /work
CMD ["sleep", "infinity"]
