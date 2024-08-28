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
Run a hook installed in /opt/ericsson/eric-cenm-hooks
"""
import sys
from os.path import dirname, exists, join
from subprocess import Popen, STDOUT
from typing import List

HOOK_DIR = '/opt/ericsson/eric-cenm-hooks'


def exec_hook(args: List[str]):
    """
    Execute a script with arguments

    Looks for hte script in the CWD and HOOK_DIR

    :param args: Script and option arguments

    """
    if len(args) == 0:
        raise SystemExit('Usage: hook_scripts [hook_args]')
    hook_script = args[0]
    print(f'Checking for hook {hook_script}')
    if not dirname(hook_script):
        hook_script = join(HOOK_DIR, hook_script)

    if not exists(hook_script):
        raise SystemExit(f'{hook_script} not found!')
    args[0] = hook_script

    print(f'Executing: {" ".join(args)}')
    with Popen(args, stderr=STDOUT) as process:
        return_code = process.wait()
        if return_code == 0:
            print(f'Hook {hook_script} with exit code 0.')
        else:
            raise SystemExit(return_code)


if __name__ == '__main__':  # pragma: no cover
    exec_hook(sys.argv[1:])
