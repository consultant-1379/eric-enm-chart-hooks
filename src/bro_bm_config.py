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
Class to execute a BRO backup manager configuration.
"""
import sys
import json
from argparse import ArgumentParser, RawTextHelpFormatter

from common import BroCliBaseClass, get_parsed_args
from reset_bro_config_map import ResetBroConfigMap
from bro_schedule_control import ScheduleControl

class BroBMConfig(BroCliBaseClass):
    """
    Class to configure BRO backup manager.
    """

    def execute_restore_backup_manager_config(self, backup: str, scope: str):
        """
        Execute a BRO restore backup manager config and wait for it to
        complete.

        If the action completes, the response is checked. If the action is
        not in the SUCCESS state an Exception is raised

        :param backup: The backup name
        :param scope: The backup scope prefix
        """

        action = self.bro_api().restore(backup, f"{scope}-bro")

        self.wait_for_action(action)

    def do_restore(self, backup_name: str, scope: str):
        """
        Execute a backup manager config restore.

        :param backup_name: A backup name
        :param scope: A backup scope prefix

        """
        if scope == "ROLLBACK":
            self.info('Backup Manager configuration restore skipped for'
                      ' ROLLBACK scope.')
            return

        if backup_name.endswith('.tar.gz'):
            backup_name = self.bro_api().backups(scope)[0].name

        self.info('Restoring backup manager config')
        self.execute_restore_backup_manager_config(backup_name, scope)

        self.info('Backup Manager config restore complete.')


    def configure_retention(self, values=None):
        """
        Configure backup retention.

        :param values: BRO retention configurations from the Values file
        """
        retention_values = {}
        limit = 2
        auto_delete = True

        try:
            retention_values = json.loads(values)
        except ValueError:
            self.warning('No Retention Values Provided')

        try:
            limit = retention_values['limit']
        except KeyError:
            self.warning(f'Setting Retention limit to {limit}. '
                         'No limit value provided')

        try:
            auto_delete = retention_values['autoDelete']
        except KeyError:
            self.warning(f'Setting Retention auto delete to {auto_delete}. '
                       'No auto delete value provided')

        self.info('Configuring backup retention for DEFAULT '
                  'BRO backup manager.')

        retention = self.bro_api().get_retention()
        self.debug(f'Current Retention configuration: {retention}')
        retention.purge = auto_delete
        retention.limit = limit
        self.wait_for_action(retention.apply())
        retention = self.bro_api().get_retention()
        self.info(f'Updated Retention configuration: {retention}')

def main(sys_args):
    """
    Main method, parses args and calls classes.

    :param sys_args: sys.argv[1:]

    """
    arg_parser = ArgumentParser(
        formatter_class=RawTextHelpFormatter,
        description='Execute a BRO backup manager configurations.\n'
                    '\tA prerequisite for this is the BRO backup manager '
                    'configurations have been supplied by the user in '
                    'the Values file.',
    )
    arg_parser.add_argument('-b', dest='backup', required=False,
                            metavar='backup_name', default=None,
                            help='Name of the BRO backup to restore the'
                                 ' backup manager config from')
    arg_parser.add_argument('-s', dest='scope', required=False,
                            metavar='scope', default='DEFAULT',
                            help='The backup scope prefix')
    arg_parser.add_argument('-c', dest='configmap', required=False,
                            metavar='configmap', default=None,
                            help='Name of the configmap for storing the'
                                 ' backup manager configurations')
    arg_parser.add_argument('-S', dest='secret', required=False,
                            metavar='secrets', default=None,
                            help='Location of the uri and password '
                                 'SFTP secret file.')
    arg_parser.add_argument('-V', '--values', dest='values', required=False,
                            metavar='values', default=None,
                            help='BRO configurations from the Values file')
    arg_parser.add_argument('-R', '--retention', dest='retention',
                            required=False, metavar='retention',
                            default=None, help='BRO retention'
                                   ' configurations from the Values file')
    args = get_parsed_args(sys_args, arg_parser)

    if not args.backup == '-' and args.scope == "DEFAULT":
        BroBMConfig().do_restore(args.backup, args.scope)
    else:
        BroBMConfig().configure_retention(args.retention)
        ScheduleControl().configure_scheduling(args.values, args.secret)

    ResetBroConfigMap().reset_restore_state(args.configmap)

if __name__ == '__main__':  # pragma: no cover
    main(sys.argv[1:])
