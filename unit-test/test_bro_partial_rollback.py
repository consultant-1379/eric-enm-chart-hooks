from unittest.mock import MagicMock, patch

from kubernetes.client import ApiException
from kubernetes.client.models.v1_config_map import V1ConfigMap
from kubernetes.client.models.v1_object_meta import V1ObjectMeta

from test_common import BaseTestCase, BroAction, PATCH_load_incluster_config, \
    PATCH_load_kube_config, BroBackup, BroService
from bro_partial_rollback import BroPartialRollback
from lib.broapi import Schedule


class TestBroPartialRollback(BaseTestCase):

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('common.CoreV1Api')
    @patch('common.Bro')
    @patch('lib.broapi.Schedule')
    def test_enable_scheduling_partial_rollback(self, mock_schedule, p_bro_api, p_core):

        cfg_map = V1ConfigMap(
            metadata=V1ObjectMeta(name='upgrade-state'),
            data={'Upgrade-State': 'Partial'}
        )

        p_core.return_value.read_namespaced_config_map.side_effect = [
            cfg_map
        ]

        mock_schedule = MagicMock("mock_schedule")

        m_bro = MagicMock(name='m_bro')
        p_bro_api.return_value = m_bro

        m_scopes = MagicMock(name='m_scopes')
        m_scopes.__iter__.return_value = [MagicMock("m_scope", id="DEFAULT")]
        m_bro.scopes = m_scopes

        m_bro.get_schedule = mock_schedule

        klass = BroPartialRollback()
        klass.enable_scheduling()
        mock_schedule.return_value.update.assert_called_once()
        p_core.return_value.read_namespaced_config_map.assert_called_once_with("upgrade-state", self.namespace(), pretty=True)

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('common.CoreV1Api')
    @patch('common.Bro')
    @patch('lib.broapi.Schedule')
    def test_enable_scheduling_full_rollback(self, mock_schedule, p_bro_api, p_core):

        cfg_map = V1ConfigMap(
            metadata=V1ObjectMeta(name='upgrade-state'),
            data={'Upgrade-State': ''}
        )

        p_core.return_value.read_namespaced_config_map.side_effect = [
            cfg_map
        ]

        mock_schedule = MagicMock("mock_schedule")

        m_bro = MagicMock(name='m_bro')
        p_bro_api.return_value = m_bro

        m_scopes = MagicMock(name='m_scopes')
        m_scopes.__iter__.return_value = [MagicMock("m_scope", id="DEFAULT")]
        m_bro.scopes = m_scopes

        m_bro.get_schedule = mock_schedule

        klass = BroPartialRollback()
        klass.enable_scheduling()
        mock_schedule.return_value.update.assert_not_called()
        p_core.return_value.read_namespaced_config_map.assert_called_once_with("upgrade-state", self.namespace(), pretty=True)

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('common.CoreV1Api')
    @patch('common.Bro')
    @patch('lib.broapi.Schedule')
    def test_enable_scheduling_with_api_exception(self, mock_schedule, p_bro_api, p_core):
        #Mock the the ApiException thrown by read_namespaced_config_map
        mock_core_v1_api_instance = p_core.return_value
        mock_core_v1_api_instance.read_namespaced_config_map.side_effect = \
            ApiException("configmaps \"upgrade-state\" not found")

        mock_schedule = MagicMock("mock_schedule")
        m_bro = MagicMock(name='m_bro')
        p_bro_api.return_value = m_bro
        m_scopes = MagicMock(name='m_scopes')
        m_scopes.__iter__.return_value = [MagicMock("m_scope", id="DEFAULT")]
        m_bro.scopes = m_scopes
        m_bro.get_schedule = mock_schedule

        klass = BroPartialRollback()
        klass.enable_scheduling()

        mock_core_v1_api_instance.read_namespaced_config_map.assert_called_once_with("upgrade-state", self.namespace(), pretty=True)
        mock_core_v1_api_instance.create_namespaced_config_map.assert_called_once()
        mock_schedule.return_value.update.called_once_with(is_enabled=True)