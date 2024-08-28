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
import sys
from argparse import ArgumentParser, RawTextHelpFormatter

from common import BroCliBaseClass, HookException, KubeApi, get_parsed_args


class BroRestoreReport(BroCliBaseClass):
    """
    Class to block till the current ongoing BRO action has completed.
    """

    def __init__(self):
        super().__init__()
        self.__kube = KubeApi()

    def show_restore_action(self, configmap: str, scope: str):
        """
        Block until the current ongoing BRO action (if any) has completed.

        :param configmap: Configmap with the restore action ID
        :param scope: The restore scope

        """
        self.info(f'Looking for a action ID in {configmap}')

        cfg_map = self.__kube.get_configmap(configmap)
        action_id = cfg_map.data.get('RESTORE_ACTION_ID', None)
        if not action_id:
            self.info('No action ID set, skipping.')
            return

        self.info(f'Looking for BRO action {action_id}')

        action = [act for act in self.bro_api().actions(scope) if
                  act.id == action_id]

        if not action:
            self.info(f'No action with ID {action_id} found in BRO, skipping.')
            return

        if len(action) != 1:
            raise HookException(
                f'More than one action with id {action_id} found?')

        action = action[0]
        if action.state == 'RUNNING':
            self.info(f'Action {action.id} is still RUNNING')
            self.wait_for_action(action)
        else:
            self.info(f'Name: {action.name}')
            self.info(f'Scope: {action.scope}')
            self.info(f'State: {action.state}')
            self.info(f'Result: {action.result}')
            self.info(f'StartTime: {action.start_time}')
            self.info(f'Completed: {action.completion_time}')
            self.info(f'AdditionalInfo: {action.additional_info or "N/A"}')
            if action.result != 'SUCCESS':
                raise HookException(
                    f'Action {action.id}/{action.name} failed with '
                    f'result {action.result}')


def main(sys_args):
    """
    Main method, parses args and calls classes.

    :param sys_args: sys.argv[1:]

    """
    arg_parser = ArgumentParser(
        formatter_class=RawTextHelpFormatter,
        description='Look up and action in BRO and report its status.'
    )
    arg_parser.add_argument('-c', dest='configmap', required=True,
                            metavar='configmap',
                            help='Configmap with the action id')
    arg_parser.add_argument('-s', dest='scope', required=True,
                            metavar='scope',
                            help='The scope of the backup')
    args = get_parsed_args(sys_args, arg_parser)
    BroRestoreReport().show_restore_action(args.configmap, args.scope)


if __name__ == '__main__':  # pragma: no cover
    main(sys.argv[1:])
