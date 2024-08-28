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
Class to Enable Backup Scheduling if Upgrade was partial
"""
from kubernetes import client
from kubernetes.client.exceptions import ApiException
from common import KubeApi
from bro_schedule_control import ScheduleControl


class BroPartialRollback(KubeApi):

    def enable_scheduling(self):
        """
        Enable Backup Scheduling if Upgrade was partial.
        Create the configMap if not exist.
        """
        cm_name = "upgrade-state"
        try:
            upgrade_state_cmap = self.get_configmap(cm_name)
            if upgrade_state_cmap.data['Upgrade-State'] == "Partial":
                self.info("Partial Rollback - Enabling Scheduling")
                ScheduleControl().enable_scheduling(is_enabled=True)
            else:
                self.info("Full Rollback - Skipping Enabling Scheduling")
        except ApiException as exc:
            cmap = client.V1ConfigMap()
            cmap.metadata = client.V1ObjectMeta(name=cm_name)
            cmap.data = {"Upgrade-State": "Partial"}
            self.info(f"Exception: {exc}")
            self.create_configmap(cmap)
            self.info(f"Configmap {cm_name} created with "
                      "'Partial' Upgrade-State.")
            ScheduleControl().enable_scheduling(is_enabled=True)




def main():
    """
    Main method, calls classes.
    """

    BroPartialRollback().enable_scheduling()


if __name__ == '__main__':  # pragma: no cover
    main()
