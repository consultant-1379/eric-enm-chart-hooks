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
Class to execute a BRO restore.
"""
import re
import sys
import time
from argparse import ArgumentParser, RawTextHelpFormatter
from typing import List
from kubernetes.client.exceptions import ApiException

from common import BroCliBaseClass, HookException, KubeApi, get_parsed_args

class BroRestoreRunner(BroCliBaseClass):
    """
    Class to execute a BRO restore.
    """

    def __init__(self):
        super().__init__()
        self.__kube = KubeApi()

    def _patch_bro_configmap(self, configmap: str, key: str, value: str):
        while True:
            try:
                cfg_map = self.__kube.get_configmap(configmap)

                cfg_map.data[key] = value

                self.__kube.patch_configmap(cfg_map)

                break
            except ApiException as exception:
                if exception.status != 404:
                    raise exception
                time.sleep(5)

    def execute_restore(self, backup: str, scope: str,
                        configmap: str) -> List[str]:
        """
        Execute a BRO restore and wait for it to complete.

        If the action completes, the response is checked. If the action is
        not in the SUCCESS state, the response is checked for missing agents.
        If there are missing agents True will be returned, anything else is
        raised as an Exception

        :param backup: The backup name
        :param scope: The backup scope
        :param configmap: The configmap to record the action ID in.

        :return: True if required agents haven't registered with BRO yet.
        """

        action = self.bro_api().restore(backup, scope)
        id_recorded = False
        while action.state == 'RUNNING':
            self.info(f'{action.name} is {action.state} at '
                      f'{action.progress:.0%}'
                      f'{action.progress_info}')
            maps = self.__kube.list_configmaps()
            if not id_recorded and configmap in maps:
                # The backup-restore-configmap may not be created yet so keep
                # trying to store the action ID, if not already done.
                self._patch_bro_configmap(
                    configmap, 'RESTORE_ACTION_ID', action.id)
                id_recorded = True
            time.sleep(10)

        self.log_action(action)

        add_info = action.additional_info or 'None'
        add_info = add_info.replace('\n', ' ')
        waiting = False
        if 'Agents with the following IDs are required' in add_info:
            _match = re.search(r'.*?\[(.*)]', action.additional_info)
            waiting = _match is not None
        elif 'Failing job for not having any registered agents' in add_info:
            self.info('No agents have registered yet.')
            waiting = True

        if action.result != 'SUCCESS' and not waiting:
            raise HookException(
                f'Action {action.name} failed with '
                f'result {action.result}: {add_info}')
        return waiting

    def do_restore(self, backup_name: str, configmap: str,
                   scope: str):
        """
        Execute a restore. This will wait for the required BEO services to
        register before triggering anything.

        :param backup_name: A backup name
        :param scope: A backup scope
        :param configmap: The config map to store the restore action ID in

        """

        # Wait for all required agents to register
        # try to prevent a load of restore failure errors for
        # unregistered agents.
        backup = self.get_backup(backup_name, scope)

        required_agents = [service.agent_id for service in backup.services]

        # Remove virtual service BRO adds for application info
        if 'APPLICATION_INFO' in required_agents:
            required_agents.remove('APPLICATION_INFO')

        waiting = True
        while waiting:
            while not all(agent in self.bro_api().status.agents
                          for agent in required_agents):
                self.info('Waiting for all agents '
                          'to register before proceeding')
                time.sleep(30)
            self.info('Executing BRO restore')
            waiting = self.execute_restore(backup_name, scope, configmap)
            if waiting:
                self.info('Restore failed because of missing agents')

        self.info('Setting RESTORE_STATE=finished')
        self._patch_bro_configmap(configmap, 'RESTORE_STATE', 'finished')
        self.info('Restore complete.')


def main(sys_args):
    """
    Main method, parses args and calls classes.

    :param sys_args: sys.argv[1:]

    """
    arg_parser = ArgumentParser(
        formatter_class=RawTextHelpFormatter,
        description='Execute a BRO restore of a named backup.\n'
                    '\tA prerequisite for this is the backup exists in BRO.\n'
                    'This will wait for all services (agents) listed in the '
                    'backup to register with BRO before triggering the '
                    'restore.',
    )
    arg_parser.add_argument('-b', dest='backup', required=True,
                            metavar='backup_name',
                            help='Name of the BRO backup to restore')
    arg_parser.add_argument('-s', dest='scope', required=True,
                            metavar='scope', help='The backup scope')
    arg_parser.add_argument('-c', dest='configmap', required=True,
                            metavar='configmap',
                            help='The backup-restore configmap')
    args = get_parsed_args(sys_args, arg_parser)
    BroRestoreRunner().do_restore(args.backup, args.configmap, args.scope)


if __name__ == '__main__':  # pragma: no cover
    main(sys.argv[1:])
