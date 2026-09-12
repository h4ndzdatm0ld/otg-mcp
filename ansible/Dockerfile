# Control node for the Ixia-C deployment playbooks.
#
# Ansible lives here and nowhere else: it is deliberately absent from
# pyproject.toml so the otg_mcp package's production and test dependency sets
# stay free of it.
FROM python:3.12-alpine

# openssh-client: every target is remote, reached over SSH.
# sshpass: only needed if a target requires password (rather than key) auth.
# rsync/git: used by the ixia_c role's repository handling.
RUN apk add --no-cache \
        openssh-client \
        sshpass \
        git \
        rsync \
        curl

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Collections and the geerlingguy.docker role are baked in so a deploy does not
# need Galaxy reachable at run time.
COPY requirements.yml /tmp/requirements.yml
RUN ansible-galaxy collection install -r /tmp/requirements.yml -p /usr/share/ansible/collections \
    && ansible-galaxy role install -r /tmp/requirements.yml -p /usr/share/ansible/roles \
    && rm /tmp/requirements.yml

COPY docker-entrypoint.sh /usr/local/bin/entrypoint
RUN chmod +x /usr/local/bin/entrypoint

WORKDIR /ansible
ENV ANSIBLE_CONFIG=/ansible/ansible.cfg \
    ANSIBLE_COLLECTIONS_PATH=/usr/share/ansible/collections \
    ANSIBLE_ROLES_PATH=/ansible/roles:/usr/share/ansible/roles

ENTRYPOINT ["/usr/local/bin/entrypoint"]
CMD ["help"]
