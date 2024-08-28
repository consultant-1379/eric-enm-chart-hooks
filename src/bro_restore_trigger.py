#!/usr/bin/env python3
# *****************************************************************************
# Ericsson AB                                                            SCRIPT
# *****************************************************************************
#
# (c) 2021 Ericsson AB - All rights reserved.
#
# The copyright to the computer program(s) herein is the property
# of Ericsson AB, Sweden. The programs may be used and/or copied only
# with the written permission from Ericsson AB or in accordance with
# the terms and conditions stipulated in the agreement/contract under
# which the program(s) have been supplied.
# *****************************************************************************
"""
Class to import a backup and trigger a restore in the background.
This will return once the restore job has started and not wait for it.
"""

import os
import sys
from argparse import ArgumentParser, RawTextHelpFormatter
from os.path import join
from socket import gethostname

from kubernetes.client import V1Container, V1Job, V1JobSpec, V1ObjectMeta, \
    V1PodSpec, V1PodTemplateSpec, V1LocalObjectReference

from common import BroCliBaseClass, HookException, KubeApi, \
    KubeBatchBaseClass, get_parsed_args


class BroImportAndRestoreTrigger(KubeBatchBaseClass):
    """
    Class to import a backup into BRO and create a batch.job that will
    run the actual restore action
    """

    def __init__(self):
        super().__init__()
        self.brocli = BroCliBaseClass()
        self.__kube = KubeApi()

    def import_backup(self, secrets: str, backup_name: str, scope: str):
        """
        Import a backup from an SFTP server.

        :param secrets: Directory containing the SFTP server URI and password
        :param backup_name: The backup to import
        :param scope: The backup scope

        """

        backups = self.brocli.bro_api().backups(scope)
        is_filename = backup_name.endswith('.tar.gz')

        if is_filename and backups:
            self.info(f'The backups in PVC are '
                      f'{[backup.name for backup in backups]}')
            raise HookException(
                ' BRO PVC is not empty.'
                ' Please remove all the backups'
                ' and repeat the procedure.')

        if  is_filename or not self.brocli.exists(backup_name, scope) :
            uri = self.read_secret(join(secrets, 'externalStorageURI'))
            password = self.read_secret(join(secrets,
                                             'externalStorageCredentials'))


            if not uri and not password:
                raise HookException(
                    f'Backup {backup_name} does not exist in BRO'
                    f' and have no SFTP secrets so can\'t try to'
                    f' import it either!')
            self.info(f'Importing {backup_name} from {uri}')
            self.brocli.import_backup(backup_name, uri, password)

        else:
            self.info(f'BRO has a backup called {backup_name}')

        # Check current product version and
        # imported backup product version match
        backup = None
        if is_filename:
            backup = self.brocli.bro_api().backups(scope)[0]
        else:
            backup = self.brocli.get_backup(backup_name, scope)

        product_version_cm = self.__kube.get_configmap(
            'product-version-configmap')
        enm_product_version = product_version_cm.metadata.annotations[
            'ericsson.com/product-revision']

        for service in backup.services:
            if service.agent_id == 'APPLICATION_INFO':
                backup_product_version = service.version

        if backup_product_version == enm_product_version:
            self.info('Product versions match')
        else:
            raise HookException(
                f'ENM product version {enm_product_version} and '
                f'backup product version {backup_product_version} '
                'do not match')

    def create_job_definition(self,  # pylint: disable=too-many-arguments
                              job_name: str, backup_name: str,
                              configmap: str, account: str,
                              scope: str) -> V1Job:
        """
        Get the definition of the restore execution job
        :param job_name: The job name
        :param backup_name: Name of the backup being restored
        :param configmap: The configmap to store the restore action ID in
        :param account: The serviceaccount to run the Job as
        :param scope: The backup scope

        :return: A V1Job object to create the job with.
        """

        bro_host = os.environ.get('BRO_HOST')
        if not bro_host:
            raise HookException(f'$BRO_HOST is not set in {gethostname()}')

        bro_port = os.environ.get('BRO_PORT')
        if not bro_port:
            raise HookException(f'$BRO_PORT is not set in {gethostname()}')

        pull_secret_name = os.environ.get('PULL_SECRET')

        this_pod = self.api_core().read_namespaced_pod(
            gethostname(),
            self.namespace()
        )

        exec_container = V1Container(
            name='executor',
            image=this_pod.spec.containers[0].image,
            image_pull_policy=this_pod.spec.containers[0].image_pull_policy,
            command=['/bin/sh', '-c',
                     f'exec_hook bro_restore_runner.py '
                     f'-b {backup_name} -c {configmap} -s {scope}'],
            env=[
                {'name': 'BRO_HOST', 'value': bro_host},
                {'name': 'BRO_PORT', 'value': bro_port}
            ]
        )
        pod_template = V1PodTemplateSpec(
            metadata=V1ObjectMeta(
                annotations={'backup_name': backup_name}
            ),
            spec=V1PodSpec(
                service_account=account,
                restart_policy='Never',
                containers=[exec_container],
                image_pull_secrets=[V1LocalObjectReference(
                    name=pull_secret_name)] if pull_secret_name else None))
        job_spec = V1JobSpec(template=pod_template, backoff_limit=0)
        job = V1Job(api_version="batch/v1", kind="Job",
                    metadata=V1ObjectMeta(name=job_name),
                    spec=job_spec)
        self.info('job_def:')
        self.info(f'\tname: {job.metadata.name}')
        self.info(f'\timage: {exec_container.image}')
        self.info(f'\tcommand: {exec_container.command}')
        return job

    def trigger_restore(self,  # pylint: disable=too-many-arguments
                        job_name: str, backup_name: str, configmap: str,
                        account: str, scope: str):
        """
        Execute a BRO restore in a background batch.job

        :param job_name: Name of the background restore job
        :param backup_name: The backup name
        :param configmap: The configmap to store the restore action ID in
        :param account: The serviceaccount to run the Job as
        :param scope: The backup scope

        """

        if backup_name.endswith('.tar.gz'):
            backup_name =  self.brocli.bro_api().backups(scope)[0].name

        job = self.create_job_definition(
            job_name, backup_name, configmap, account, scope)

        self.info(
            f'Triggering restore job {job_name} for {scope}/{backup_name}.')
        if job_name in self.list_jobs():
            self.delete_job(job_name)
            self.info('Replacing previous job.')

        api_response = self.api_batch().create_namespaced_job(
            self.namespace(),
            job,
        )
        self.info(f'Triggered restore job, status={api_response.status}')

    def import_and_trigger(self,  # pylint: disable=too-many-arguments
                           account: str, secrets: str, job_name: str,
                           backup_name: str, configmap: str, scope: str):
        """
        (Optionally) import a backup a trigger a restore in a
        background batch.job

        :param account: serviceacount to that allows configmap patch & get
        :param secrets: Directory containing the SFTP uri and password
        secrets files
        :param job_name: Name of the background restore job
        :param backup_name: The backup to restore
        :param configmap: The backup-restore-configmap holding the state
        :param scope: The backup scope
        of the current restore

        """
        self.import_backup(secrets, backup_name, scope)
        self.trigger_restore(job_name, backup_name, configmap, account, scope)


def main(sys_args):
    """
    Main method, parses args and calls classes.

    :param sys_args: sys.argv[1:]

    """
    arg_parser = ArgumentParser(
        formatter_class=RawTextHelpFormatter,
        description='Import and trigger a BRO restore of a named backup.'
    )

    arg_parser.add_argument('-S', dest='secrets', required=True,
                            metavar='secrets',
                            help='Location of the uri and password '
                                 'SFTP secrets files.')

    arg_parser.add_argument('-A', dest='account', required=True,
                            metavar='serviceaccount',
                            help='The serviceaccount with Role permissions '
                                 'for configmap patch & get')

    arg_parser.add_argument('-b', dest='backup', required=True,
                            metavar='backup_name',
                            help='Name of the BRO backup to restore')

    arg_parser.add_argument('-j', dest='job', required=True,
                            metavar='job_name',
                            help='Name of the background restore job')

    arg_parser.add_argument('-s', dest='scope', required=True,
                            metavar='scope', help='Name scope of the backup')

    arg_parser.add_argument('-c', dest='configmap', required=True,
                            metavar='configmap',
                            help='Name of the back-restore configmap')

    args = get_parsed_args(sys_args, arg_parser)
    trigger = BroImportAndRestoreTrigger()
    try:
        trigger.import_and_trigger(
        args.account, args.secrets, args.job, args.backup, args.configmap,
        args.scope)
    except Exception as import_exception: # pylint: disable=broad-except
        trigger.debug(f'Caught exception: {str(import_exception)}')
        sys.exit(1)


if __name__ == '__main__':  # pragma: no cover
    main(sys.argv[1:])
