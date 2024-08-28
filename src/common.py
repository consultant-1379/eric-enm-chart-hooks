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
Common classes and functions for hook scripts.
"""
import logging
import os
import sys
import time
from argparse import ArgumentParser, Namespace
from os.path import exists
from typing import List

from kubernetes.client import ApiClient, BatchV1Api, CoreV1Api, V1ConfigMap, \
    V1DeleteOptions, V1Status, V1Service
from kubernetes.client.exceptions import ApiException
from kubernetes.config import ConfigException, load_incluster_config, \
    load_kube_config
from lib.broapi import Action, Backup, Bro
from requests.exceptions import ConnectionError as connection_err

class HookException(Exception):
    """ Generic exception for any hook errors """


class BaseClass:
    """
    Base class for all hooks.
    Provides the connections to kubernetes
    """

    def __init__(self):
        super().__init__()
        logging.basicConfig(
            stream=sys.stdout, level=logging.DEBUG,
            format='%(asctime)-20s [%(name)s]  %(levelname)-18s %(message)s')
        self.logger = logging.getLogger(__name__)
        logging.getLogger('kubernetes.client.rest').setLevel(logging.INFO)

    def info(self, message):
        """
        Log a message as INFO level

        :param message: Message to log.

        """
        self.logger.info(message)

    def warning(self, message):
        """
        Log the current message as ERROR level.

        :param message: Message to log

        """
        self.logger.warning(message)

    def debug(self, message):
        """
        Log the current message as DEBUG level.

        :param message: Message to log

        """
        self.logger.debug(message)


class KubeApi(BaseClass):
    """
    Common kubernetes API methods.
    """

    @staticmethod
    def namespace_file() -> str:
        """
        Get the secrets file with the current namespace name

        :returns: Namespace file
        """
        return '/var/run/secrets/kubernetes.io/serviceaccount/namespace'

    def __init__(self):
        super().__init__()
        self.__api_client = None
        self.__api_core = None
        self._load_config()
        self._read_namespace_file()

    def _read_namespace_file(self):
        """
        Get the current Pods namespace from the serviceaccount namespace file

        """
        ns_file = os.environ['SA_NAMESPACE'] \
            if 'SA_NAMESPACE' in os.environ \
            else KubeApi.namespace_file()

        with open(ns_file, encoding="utf-8") as _r:
            self.__namespace = _r.readline()
        self.logger.debug('Namespace set to "%s"', self.namespace())

    def _load_config(self):
        self.debug('Loading K8s client config')
        try:
            load_incluster_config()
            self.debug('Loaded in-cluster config')
        except ConfigException as error:
            incluster_error = str(error)
            self.warning(f'Could not load in-cluster config, '
                         f'trying kube-config: {incluster_error}')
            try:
                load_kube_config()
                self.debug('Loaded kube config')
            except ConfigException as error:
                kubecfg_error = str(error)
                self.warning(f'Failed to load kube-config as '
                             f'well: {kubecfg_error}')
                raise HookException(  # pylint: disable=raise-missing-from
                    'Could not connect to kubernetes:'
                    'load_incluster_config:{incluster_error}:'
                    'load_kube_config:{kubecfg_error}'
                )
        self.__api_client = ApiClient()
        self.__api_core = CoreV1Api(self.__api_client)

    def namespace(self) -> str:
        """
        Get the current namespace
        :return: namespace
        """
        return self.__namespace

    def api_core(self) -> CoreV1Api:
        """
        Get the current CoreV1Api instance.

        :return: A CoreV1Api interface
        """
        return self.__api_core

    def api_client(self) -> ApiClient:
        """
        Get the current ApiClient instance.

        :return: A ApiClient interface
        """
        return self.__api_client

    @staticmethod
    def read_secret(secret) -> str:
        """
        Read a secret file.
        If the file doesn't exists an empty string is returned.

        :param secret: Secrets file
        :return: First line in secrets file.

        """
        if exists(secret):
            with open(secret, encoding="utf-8") as _reader:
                return _reader.readline()
        return ""

    def get_secret(self, secret: str):
        """
        Read a secret

        :param secret: secret name
        :return: dictionary representing the secret
                or None if secret does not exist
        """
        try:
            return self.api_core().read_namespaced_secret(
                secret, self.namespace(), pretty=True).data
        except ApiException as exc:
            self.debug(f"Secret '{secret}' not found: {exc}")
        return None

    def delete_secret(self, secret: str) -> V1Status:
        """
        Delete a secret

        :param secret: secret name
        """

        while True:
            try:
                status = self.api_core().delete_namespaced_secret(
                    secret, self.namespace(), grace_period_seconds=0
                )

                return status
            except ApiException as exception:
                if exception.status != 404:
                    raise exception
                time.sleep(5)

    def get_configmap(self, configmap: str) -> V1ConfigMap:
        """
        Read a configmap

        :param configmap: configmap name
        :return: V1ConfigMap representing the configmap
        """
        return self.api_core().read_namespaced_config_map(
            configmap, self.namespace(), pretty=True
        )

    def list_configmaps(self) -> List[str]:
        """
        Get a list of configmaps

        :return: Names of available configmaps
        """
        cms = self.api_core().list_namespaced_config_map(
            self.namespace()).items
        return [cm.metadata.name for cm in cms]

    def patch_configmap(self, configmap: V1ConfigMap):
        """
        # The body is a V1ConfigMap object, not json/string data...

        :param configmap: The configmap to patch
        :return: None
        """
        self.api_core().patch_namespaced_config_map(
            configmap.metadata.name,
            self.namespace(),
            configmap
        )

    def replace_configmap(self, name, body):
        """
        Replaces a configmap

        :param name: Configmap Name
        :param body: V1Configmap information
        """
        self.api_core().replace_namespaced_config_map(
            name, self.namespace(), body)

    def create_configmap(self, body):
        """
        Creates a configmap

        :param body: V1Configmap information
        """
        self.api_core().create_namespaced_config_map(self.namespace(), body)

    def delete_configmap(self, name):
        """
        Deletes a configmap with a given name

        :param name: Name of the configmap
        """
        self.api_core().delete_namespaced_config_map(name, self.namespace())

    def get_pods_br_rollback_pod_list(self):
        rollback_agents = []
        pods = self.api_core().list_namespaced_pod(self.namespace()).items

        for pod in pods:
            try:
                if pod.metadata.annotations["backupType"] == "ROLLBACK":
                    rollback_agents\
                    .append(pod.metadata.labels["adpbrlabelkey"])
            except (TypeError, KeyError):
                continue

        return rollback_agents

    def list_service_details(self, svc_name) -> V1Service:
        #name = service # str | name of the Service
        try:
            service_details = self.api_core().read_namespaced_service(svc_name,
              self.namespace(), pretty=True)
            return service_details
        except ApiException as exception:
            self.debug(f"An exception occurred: {exception}")
            self.debug(f"service {svc_name} is not "
                       f"running in namespace {self.namespace()}")
            return None

    def list_services(self) -> List[str]:
        """
        Get a list of services

        :return: List of existsing services
        """
        services = self.api_core().list_namespaced_service(
          self.namespace(), pretty=True).items
        return [service.metadata.name for service in services]


    def delete_service(self, svc_name: str):
        """
        Delete a service.

        :param svc_name: The service name

        """
        if svc_name in self.list_services():
            options = V1DeleteOptions(
                propagation_policy='Foreground',
                grace_period_seconds=5)
            self.api_core().delete_namespaced_service(
                svc_name, self.namespace(), body=options)
            self.info(f'Waiting for service {svc_name} to delete.')
            while svc_name in self.list_services():
                time.sleep(1)
            self.info(f'Existing service {svc_name} deleted.')
        else:
            self.info(f'Service {svc_name} does not exist to delete.')

class BroCliBaseClass(BaseClass):
    """
    Base class for BROCLI interaction

    """

    def __init__(self):
        super().__init__()
        self.__bro_api = Bro(
            host=os.environ['BRO_HOST'],
            port=int(os.environ['BRO_PORT']))

    def bro_api(self) -> Bro:

        """
        brocli interface.

        :return: A brocli instance
        """
        return self.__bro_api

    def wait_bro_ready(self):
        """
        Wait until BRO is ready
        """
        while True:
            try:
                status = self.bro_api().status
                self.debug(f"BRO Status: {status}")
                break
            except connection_err:
                self.info("Waiting for BRO to be ready")
                time.sleep(10)

    def exists(self, backup_name: str, scope: str) -> bool:
        """
        Check if the named backup exists in BRO.

        :param backup_name: The backup name
        :param scope: The backup scope
        :return: True if the backup exits, False otherwise
        """
        current = self.bro_api().backups(scope)
        existing = [backup.name for backup in current]
        return backup_name in existing

    def import_backup(self, backup_name: str, sftp_uri: str, password: str):
        """
        Import it from the SFTP source and wait for the import to complete.
        :param backup_name: The backup name
        :param sftp_uri: URI of the SFTP server,
            format: <user>@<hostname>/<data_path>
        :param password: SFTP password

        """
        action = self.bro_api().import_backup(
            backup_name, sftp_uri, password)
        self.wait_for_action(action)

    def get_backup(self, backup_name: str, scope: str) -> Backup:
        """
        Get the details of a backup in BRO

        :param backup_name: The backup name
        :param scope: The backup scope
        :return: Info on backup
        """
        return self.bro_api().get_backup(backup_name, scope)

    def wait_for_action(self, action: Action):
        """
        Wait for an action to complete.

        :param action: The action to monitor and wait for completion.

        """
        self.info(f'Waiting for action {action.id} to complete.')
        while action.state == 'RUNNING':
            self.info(f'{action.name} {action.id} is {action.state}. '
                      f'Progress: {action.progress:.0%}')
            time.sleep(5)

        self.log_action(action)

        if action.result != 'SUCCESS':
            raise HookException(
                f'Action {action.name} failed with result {action.result}')

    def log_action(self, action: Action):
        """
        Log the details of an action

        :param action: The BRO action.

        """
        add_info = action.additional_info or 'None'
        add_info = add_info.replace('\n', ' ')
        self.info(f'{action.name} {action.id} is {action.state}. '
                  f'Progress: {action.progress:.0%} '
                  f'Result: {action.result}')
        self.info(f'Additional info: {add_info}')


class KubeBatchBaseClass(KubeApi):
    """
    Base class for batch(job) interaction

    """

    def __init__(self):
        super().__init__()
        self.__api_batch = BatchV1Api(self.api_client())

    def api_batch(self) -> BatchV1Api:
        """
        Get the current BatchV1Api instance.

        :return: A BatchV1Api interface
        """
        return self.__api_batch

    def list_jobs(self) -> List[str]:
        """
        List all batch jobs.

        :return: List of existing batch jobs
        """
        jobs = self.api_batch().list_namespaced_job(self.namespace()).items
        return [job.metadata.name for job in jobs]

    def delete_job(self, job_name: str):
        """
        Delete a batch job.

        :param job_name: The job name

        """
        if job_name in self.list_jobs():
            options = V1DeleteOptions(
                propagation_policy='Foreground',
                grace_period_seconds=5)
            self.api_batch().delete_namespaced_job(
                job_name, self.namespace(), body=options)
            self.info('Waiting for job to delete.')
            while job_name in self.list_jobs():
                time.sleep(1)
            self.info(f'Existing job {job_name} deleted.')
        else:
            self.info(f'Job {job_name} does not exist to delete.')


def get_parsed_args(args: List[str], arg_parser: ArgumentParser) -> Namespace:
    """
    Get te parsed args from an ArgumentParser instance handling the case
    where there's no input arguments. If there are no input arguments the the
    ArgumentParser help is printed and a SystemExit error is raised.

    :param args: List of arguments and values to parse.
    :param arg_parser: The ArgumentParser to use
    :return: Namespace containing parsed options.
    """
    if len(args) == 0:
        print(arg_parser.format_help())
        raise SystemExit(2)
    return arg_parser.parse_args(args)
