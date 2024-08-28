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
Class to set the state of upgrade
"""
import sys

from argparse import ArgumentParser, RawTextHelpFormatter
from kubernetes import client
from kubernetes.client.exceptions import ApiException

from common import KubeApi, get_parsed_args



class UpgradeState(KubeApi):

    def set_upgrade_state(self, is_partial):
        """
        Creates a configmap with current scheduling values.
        """

        upgrade_state = {}
        cm_name = "upgrade-state"

        if is_partial:
            upgrade_state["Upgrade-State"] = "Partial"
        else:
            upgrade_state["Upgrade-State"] = ""

        cmap = client.V1ConfigMap()
        cmap.metadata = client.V1ObjectMeta(name=cm_name)
        cmap.data = upgrade_state
        try:
            self.replace_configmap(cm_name, cmap)
            self.info('Configmap Replaced')
            self.info(f'Upgrade State Set to {upgrade_state}')
        except ApiException as exc:
            self.info(f'Exception: {exc}')
            self.create_configmap(cmap)
            self.info('Configmap Created')
            self.info(f'Upgrade State Set to {upgrade_state}')


def main(sys_args):
    """
    Main method, parses args and calls classes.

    :param sys_args: sys.argv[1:]

    """
    arg_parser = ArgumentParser(
        formatter_class=RawTextHelpFormatter,
        description='Enables/Disables Backup Scheduling',
    )

    arg_parser.add_argument('--partial', dest='is_partial',
                            action='store_true', help='Disable Scheduling')

    arg_parser.add_argument('--full', dest='is_partial',
                            action='store_false', help='Enable Scheduling')

    args = get_parsed_args(sys_args, arg_parser)

    UpgradeState().set_upgrade_state(args.is_partial)


if __name__ == '__main__':  # pragma: no cover
    main(sys.argv[1:])
