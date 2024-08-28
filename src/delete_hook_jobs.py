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
Class to delete jobs created by chart hooks, helm doesn't do this.
"""
from argparse import ArgumentParser, RawTextHelpFormatter
from typing import List

import sys

from common import KubeBatchBaseClass, get_parsed_args


class DeleteHookJobs(KubeBatchBaseClass):
    """
    Delete a list of jobs
    """
    def hook_cleanup(self, jobs: List[str]):
        """
        Delete a list of batch.jobs
        :param jobs: List of job names to delete

        """
        for job_name in jobs:
            self.info(f'Deleting job {job_name}')
            self.delete_job(job_name)
            self.info(f'Job {job_name} deleted.')


def main(sys_args):
    """
    Main method, parses args and calls classes.

    :param sys_args: sys.argv[1:]

    """
    arg_parser = ArgumentParser(
        formatter_class=RawTextHelpFormatter,
        description='Delete a Job.'
    )
    arg_parser.add_argument('-j', dest='jobs', required=True,
                            metavar='job', nargs='?', action='append',
                            help='Job name.')
    args = get_parsed_args(sys_args, arg_parser)
    DeleteHookJobs().hook_cleanup(args.jobs)


if __name__ == '__main__':  # pragma: no cover
    main(sys.argv[1:])
