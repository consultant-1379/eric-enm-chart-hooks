from unittest.mock import MagicMock, PropertyMock, patch

from test_common import BaseTestCase, BroAction, BroBackup, PATCH_load_incluster_config, \
    PATCH_load_kube_config
from bro_pre_upgrade_backup_trigger import BroPreUpgradeBackup, main
from common import HookException

class TestBroPreUpgradeBackupTrigger(BaseTestCase):

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('common.CoreV1Api')
    @patch('time.sleep')
    @patch('common.Bro')
    def test_execute_pre_upgrade_backup(self, p_bro_api, _sleep, p_core):
        m_bro = MagicMock(name='m_bro')
        p_bro_api.return_value = m_bro

        m_state = PropertyMock(
            name='m_state', side_effect=[
                'RUNNING', 'RUNNING',
                'FINISHED', 'FINISHED'
            ])
        a1 = BroAction(name='test', id='12345', progress_info=None, result='SUCCESS',
                       state=m_state, scope='ROLLBACK',
                       start_time='', completion_time='',
                       progress=0,
                       additional_info=None)

        m_create = MagicMock(
            name='m_create', side_effect=[a1])
        m_bro.create = m_create

        klass = BroPreUpgradeBackup()
        klass.execute_pre_upgrade("test")
        m_create.assert_called_once_with("test", "ROLLBACK")

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('common.CoreV1Api')
    @patch('time.sleep')
    @patch('common.Bro')
    def test_execute_pre_upgrade_backup_error(self, p_bro_api, _sleep, p_core):
        m_bro = MagicMock(name='m_bro')
        p_bro_api.return_value = m_bro

        m_state = PropertyMock(
            name='m_state', side_effect=[
                'RUNNING', 'RUNNING',
                'FINISHED', 'FINISHED'
            ])
        a1 = BroAction(name='test', id='12345', progress_info=None, result='FAILURE',
                       state=m_state, scope='ROLLBACK',
                       start_time='', completion_time='',
                       progress=0,
                       additional_info=None)

        m_create = MagicMock(
            name='m_create', side_effect=[a1])
        m_bro.create = m_create

        klass = BroPreUpgradeBackup()
        self.assertRaises(HookException, klass.execute_pre_upgrade, 'test')

    def test_main_missing_args(self):
        self.assertRaises(SystemExit, main, [])
