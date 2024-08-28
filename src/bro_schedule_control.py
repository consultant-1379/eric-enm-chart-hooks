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
import base64
import json
import re
import sys

from argparse import ArgumentParser, RawTextHelpFormatter
from datetime import datetime

from common import BroCliBaseClass, KubeApi, get_parsed_args

SCHEDULE_INTERVAL_RE = re.compile(
                        r'^((?P<weeks>\d+)w)?((?P<days>\d+)d)?'
                        r'((?P<hours>\d+)h)?((?P<minutes>\d+)m)?$')


class ScheduleControl(BroCliBaseClass):
    """
    Class to Configure Backup Scheduling
    """

    def __init__(self):
        super().__init__()
        self.__kube = KubeApi()

    def configure_scheduling(self, values=None, secret_name=None):
        """
        Uses scheduling configurations from the Values file to create user
        defined schedules for the DEFAULT scope.
        """
        self.wait_bro_ready()
        schedule = self.bro_api().get_schedule()
        scheduling_values = {}
        has_scheduling = True

        try:
            scheduling_values = json.loads(values)
        except ValueError as exc:
            self.debug(f'Exception occurred: {exc}')
            has_scheduling = False
        if not (has_scheduling or scheduling_values):
            self.info('Disabling backup scheduling.')
            schedule.update(enabled=False)
            self.delete_schedules()
            return
        self.info("Enabling backup scheduling.")

        auto_export = True
        export_uri = None
        export_password = None
        secret = self.__kube.get_secret(secret_name)

        if secret and secret['externalStorageURI'] \
                    and secret['externalStorageCredentials']:
            export_uri = base64.b64decode(
                secret['externalStorageURI']).decode("utf-8")
            export_password = base64.b64decode(
                secret['externalStorageCredentials']).decode("utf-8")
            self.info(f"Starting delete for '{secret_name}' Secret")
            response = self.__kube.delete_secret(secret_name)
            self.debug(f"response: {response}")
            if response.status == 'Success':
                self.info(f"Secret '{secret_name}' deleted successfully")

        if not (export_password or export_uri):
            self.warning("Export information not changed.")
            auto_export = None
            export_password = None
            export_uri = None

        try:
            backup_prefix = scheduling_values['backupPrefix']
        except KeyError:
            backup_prefix = "SCHEDULED_BACKUP"
            self.warning(f'Setting Backup Prefix to {backup_prefix}. '
                       'No Backup Prefix provided')

        schedule.update(
            True,
            backup_prefix,
            auto_export,
            export_password,
            export_uri)
        self.delete_schedules()

        try:
            self._add_schedules(schedule, scheduling_values['schedules'])
        except KeyError as exc:
            self.debug(f'Exception occurred: {exc}')
            self.warning("No schedules to create")

    def _add_schedules(self, schedule=None, schedules=None):
        if schedules:
            for a_schedule in schedules:
                if 'every' in a_schedule:
                    every = self.validate_backup_interval(SCHEDULE_INTERVAL_RE,
                                                    a_schedule['every'])
                    start_datetime = None
                    if 'start' in a_schedule:
                        start_datetime = self.validate_datetime(
                            'start', a_schedule['start'])
                    stop_datetime = None
                    if 'stop' in a_schedule:
                        stop_datetime = self.validate_datetime(
                            'stop',a_schedule['stop'])
                    if every:
                        matches = SCHEDULE_INTERVAL_RE.search(every)
                        interval = schedule.interval_add(
                            matches.group('weeks'),
                            matches.group('days'),
                            matches.group('hours'),
                            matches.group('minutes'),
                            start_time=start_datetime,
                            stop_time=stop_datetime)
                        self.debug(f'Added backup interval {interval.id}\n')

    def delete_schedules(self):
        """
        Deletes all schedules for DEFAULT scope
        """
        self.wait_bro_ready()
        schedule_config = self.bro_api().get_schedule()
        for interval in schedule_config.intervals:
            schedule_config.interval_delete(interval.id)

    def validate_backup_interval(self, interval_regex, value):
        """Check that schedule interval is properly formatted.
            Returns 'None' if validation fails.
        """
        if not value or not interval_regex.match(value):
            self.warning(
                f"Invalid schedule interval value: {value}")
            return None
        return value

    def validate_datetime(self, action, value):
        """Check that schedule start|stop datetime is properly formatted.
            Returns 'None' if validation fails.
        """
        try:
            datetime.strptime(value, '%Y-%m-%dT%H:%M:%S')
            return value
        except (ValueError, TypeError):
            self.warning(
                f"Invalid schedule '{action}' value: '{value}', "
                "format should be YYYY-mm-ddThh:mm:ss")
            return None

    def enable_scheduling(self, is_enabled):
        """
        Enable/disable backup scheduling for DEFAULT scope
        """
        self.wait_bro_ready()

        schedule = self.bro_api().get_schedule()
        schedule.update(enabled=is_enabled)

def main(sys_args):
    """
    Main method, parses args and calls classes.

    :param sys_args: sys.argv[1:]

    """
    arg_parser = ArgumentParser(
        formatter_class=RawTextHelpFormatter,
        description='Enables/Disables Backup Scheduling',
    )

    arg_parser.add_argument('--disabled', dest='is_enabled',
        action='store_false', help='Disable Scheduling')

    arg_parser.add_argument('--enabled', dest='is_enabled',
        action='store_true', help='Enable Scheduling')

    args = get_parsed_args(sys_args, arg_parser)

    ScheduleControl().enable_scheduling(args.is_enabled)


if __name__ == '__main__':  # pragma: no cover
    main(sys.argv[1:])
