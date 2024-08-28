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
Reset the backup-restore-configmap
"""

from argparse import ArgumentParser, RawTextHelpFormatter

import sys

from common import KubeApi, get_parsed_args


class ResetBroConfigMap(KubeApi):
    """
    Reset the backup-restore-configmap
    """

    def reset_restore_state(self, configmap_name: str):
        """
        Set the backup-restore-configmap used to hold the name/state of
        the current BRO restore to empty values.

        :param configmap_name: The configmap to reset

        """
        self.logger.info('Resetting values in configmap "%s"', configmap_name)
        cfg_map = self.get_configmap(configmap_name)
        self.info(f'Current {configmap_name}: {cfg_map.data}')

        for _key in cfg_map.data.keys():
            cfg_map.data[_key] = ""

        self.info(f'Patching {configmap_name} with {cfg_map.data}')

        # The body is a V1ConfigMap object, not json/string data...
        self.patch_configmap(cfg_map)
        cfg_map = self.get_configmap(configmap_name)
        self.info(f'Post patch {configmap_name}: {cfg_map.data}')


def main(sys_args):
    """
    Main method, parses args and calls classes.

    :param sys_args: sys.argv[1:]

    """
    arg_parser = ArgumentParser(
        formatter_class=RawTextHelpFormatter,
        description='Reset the values for the restore in the back-restore '
                    'configmap.',
    )

    arg_parser.add_argument('-c', dest='configmap', required=True,
                            metavar='configmap',
                            help='Name of the back-restore configmap')
    args = get_parsed_args(sys_args, arg_parser)
    ResetBroConfigMap().reset_restore_state(args.configmap)


if __name__ == '__main__':  # pragma: no cover
    main(sys.argv[1:])
