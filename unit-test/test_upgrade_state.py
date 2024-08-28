from unittest.mock import patch

from kubernetes.client.models.v1_config_map import V1ConfigMap
from kubernetes.client.models.v1_object_meta import V1ObjectMeta

from test_common import BaseTestCase, BroAction, PATCH_load_incluster_config, \
    PATCH_load_kube_config, BroBackup, BroService
from upgrade_state import UpgradeState


class TestUpgradeState(BaseTestCase):

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('common.CoreV1Api')
    def test_set_upgrade_state(self, p_core):

        cfg_map = V1ConfigMap(
            metadata=V1ObjectMeta(name='upgrade-state'),
            data={'Upgrade-State': 'Partial'}
        )

        p_core.return_value.read_namespaced_config_map.side_effect = [
            cfg_map
        ]

        klass = UpgradeState()
        klass.set_upgrade_state(True)
        p_core.return_value.replace_namespaced_config_map.assert_called_once_with('upgrade-state', 'enm404', cfg_map)
