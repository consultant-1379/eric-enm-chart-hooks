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
Class to delete service for .......
"""
from argparse import ArgumentParser, RawTextHelpFormatter


import sys

from common import KubeApi, get_parsed_args

class DeleteService(KubeApi):
    """
    Delete a SVC
    """
    def service_cleanup(self, service):
        """
        Delete a Service
        :param service: List of service names to delete

        """
        clusterip = service.spec.cluster_ip
        service_name = service.metadata.name
        if clusterip is not None:
            self.info(f'Deleting Service {service_name}')
            self.delete_service(service_name)
            self.info(f'Service ({service_name}) deleted.')


    def service(self, service):
        service_name = self.list_service_details(service)
        return service_name


def main(sys_args):
    """
    Main method, parses args and calls classes.

    :param sys_args: sys.argv[1:]

    """
    arg_parser = ArgumentParser(
        formatter_class=RawTextHelpFormatter,
        description='Delete a Service.'
    )
    arg_parser.add_argument('-s', dest='services', required=True,
                            metavar='service', nargs='?', action='append',
                            help='Service name.')
    args = get_parsed_args(sys_args, arg_parser)
    services = args.services
    del_svc = DeleteService()
    for svc in services:
        service_details = del_svc.service(svc)
        if service_details is not None:
            del_svc.service_cleanup(service_details)
        else:
            del_svc.debug(f"Skip the cleanup for service {svc}")


if __name__ == '__main__':  # pragma: no cover
    main(sys.argv[1:])
