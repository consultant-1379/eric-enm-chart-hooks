from unittest.mock import MagicMock, mock_open, patch

from kubernetes.client import V1ConfigMap, V1ObjectMeta

from reset_bro_config_map import ResetBroConfigMap, main
from test_common import BaseTestCase, PATCH_load_incluster_config, \
    PATCH_load_kube_config


class TestCasePatchBroConfigMap(BaseTestCase):
    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('common.ApiClient')
    @patch('common.CoreV1Api')
    def test_reset_restore_state(self, api_core, _):
        klass = ResetBroConfigMap()

        configmap_name = 'test_config_map'
        metadata = V1ObjectMeta(name=configmap_name)
        pre_cfg_map = V1ConfigMap(
            metadata=metadata,
            data={'key_1': 'value_1'}
        )
        post_cfg_map = V1ConfigMap(
            metadata=metadata,
            data={'key_1': ''}
        )

        api_core.return_value.read_namespaced_config_map.side_effect = [
            pre_cfg_map, post_cfg_map
        ]

        klass.reset_restore_state(configmap_name)
        api_core.return_value.patch_namespaced_config_map.assert_called_with(
            configmap_name, self.namespace(), post_cfg_map
        )

    @patch('reset_bro_config_map.ResetBroConfigMap')
    def test_main(self, p_patch_bro_configmap):
        p_patch_bro_configmap.return_value = MagicMock(
            name='m_ResetBroConfigMap')
        m_do_reset = p_patch_bro_configmap.return_value.reset_restore_state = \
            MagicMock(name='m_reset_restore_state')

        self.assertRaises(SystemExit, main, [])
        self.assertRaises(SystemExit, main, ['ss'])

        main(['-c', 'cfg_map'])
        m_do_reset.assert_called_once_with('cfg_map')
