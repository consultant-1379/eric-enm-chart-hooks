#!/usr/bin/env python3
# *****************************************************************************
# Ericsson AB                                                            SCRIPT
# *****************************************************************************
#
# (c) 2024 Ericsson AB - All rights reserved.
#
# The copyright to the computer program(s) herein is the property
# of Ericsson AB, Sweden. The programs may be used and/or copied only
# with the written permission from Ericsson AB or in accordance with
# the terms and conditions stipulated in the agreement/contract under
# which the program(s) have been supplied.
# *****************************************************************************
"""
Class to delete secrets.
"""
from argparse import ArgumentParser, RawTextHelpFormatter

import sys
from typing import List

from common import KubeApi, get_parsed_args

class DeleteSecrets(KubeApi):
    """
    Delete the given list of secrets.
    """
    def cleanup_secrets(self, secrets: List[str]):
        """
        Delete the given list of secrets
        :param secrets: List of secret names to delete

        """
        for secret in secrets:
            self.info(f'Deleting secret {secret}')
            self.delete_secret(secret)
            self.info(f'Secret {secret} deleted.')


def main(sys_args):
    """
    Main method, parses args and calls classes.

    :param sys_args: sys.argv[1:]

    """
    arg_parser = ArgumentParser(
        formatter_class=RawTextHelpFormatter,
        description='Delete a list of secrets.'
    )
    arg_parser.add_argument('-s', dest='secrets', required=True,
                            metavar='secret', nargs='?', action='append',
                            help='Secret name.')
    args = get_parsed_args(sys_args, arg_parser)
    DeleteSecrets().cleanup_secrets(args.secrets)


if __name__ == '__main__':  # pragma: no cover
    main(sys.argv[1:])
