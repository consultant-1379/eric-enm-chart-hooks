#!/usr/bin/env python3
# *****************************************************************************
# Ericsson AB                                                            SCRIPT
# *****************************************************************************
#
# (c) 2022 Ericsson AB - All rights reserved.
#
# The copyright to the computer program(s) herein is the property
# of Ericsson AB, Sweden. The programs may be used and/or copied only
# with the written permission from Ericsson AB or in accordance with
# the terms and conditions stipulated in the agreement/contract under
# which the program(s) have been supplied.
# *****************************************************************************
"""
Class to execute a BRO backup manager configuration restore.
"""
import sys
import time
from argparse import ArgumentParser, RawTextHelpFormatter

from common import BroCliBaseClass, KubeApi, get_parsed_args

class BroPreUpgradeBackup(BroCliBaseClass):
    """
    Class to execute a pre-upgrade backup
    """
    def __init__(self):
        super().__init__()
        self.__kube = KubeApi()

    def execute_pre_upgrade(self, backup: str):
        """
        Creates Bro Pre-Upgrade Backup

        If the action completes, the response is checked. If the action is
        not in the SUCCESS state an Exception is raised

        :param backup: The backup name
        """
        self.wait_bro_ready()

        while True:
            rollback_agents = self.__kube.get_pods_br_rollback_pod_list()
            registered_agents = self.bro_api().status.agents

            if all(agents in registered_agents for agents in rollback_agents):
                self.info("All Agents of scope ROLLBACK are registered")
                break

            self.info("Not all Agents of scope ROLLBACK are registered")
            self.debug(f'rollback_agents: {rollback_agents}')
            self.debug(f'registered_agents: {registered_agents}')
            time.sleep(10)

        action = self.bro_api().create(backup, "ROLLBACK")

        self.wait_for_action(action)

def main(sys_args):
    """
    Main method, parses args and calls classes.

    :param sys_args: sys.argv[1:]

    """
    arg_parser = ArgumentParser(
        formatter_class=RawTextHelpFormatter,
        description='Execute pre-upgrade backup and disable backup scheduling',
    )

    arg_parser.add_argument('-b', dest='backup', required=True,
        metavar='backup_name',
        help='Name of the BRO pre-upgrade backup to be created')
    args = get_parsed_args(sys_args, arg_parser)

    BroPreUpgradeBackup().execute_pre_upgrade(args.backup)

if __name__ == '__main__':  # pragma: no cover
    main(sys.argv[1:])
