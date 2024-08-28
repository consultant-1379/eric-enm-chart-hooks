ARG BACKUP_RESTORE_CLI_VERSION
FROM armdocker.rnd.ericsson.se/proj-enm/backup-restore-cli:${BACKUP_RESTORE_CLI_VERSION}

ARG HOOK_DIR=/opt/ericsson/eric-cenm-hooks

USER root
COPY src/* ${HOOK_DIR}/

RUN zypper install -y python3-pip && \
    zypper clean -a && \
    pip3 install --no-cache-dir kubernetes==24.2.0 urllib3==1.24.2 && \
    ln -sfv ${HOOK_DIR}/hook_runner.py /usr/local/bin/exec_hook && \
    chmod -R 740 /opt/ericsson/ && \
    chown -R 293955:293955 /opt/ericsson/

ENV PYTHONPATH=/opt/ericsson/backup-restore-cli:${HOOK_DIR}:${PYTHONPATH}

USER 293955
