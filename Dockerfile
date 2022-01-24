FROM waggle/plugin-base:1.1.1-base

RUN apt-get update \
  && apt-get install -y \
  openssh-client \
  git \
  nmap \
  arp-scan \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt camera_provisioner.py hanwhacamera.py networkswitch.py utils.py run.sh /app/
RUN pip3 install --no-cache-dir -r /app/requirements.txt

ENTRYPOINT ["/bin/bash", "/app/run.sh"]