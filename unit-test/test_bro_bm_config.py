from unittest.mock import MagicMock, PropertyMock, patch

from kubernetes.client.models.v1_config_map import V1ConfigMap
from kubernetes.client.models.v1_config_map_list import V1ConfigMapList
from kubernetes.client.models.v1_object_meta import V1ObjectMeta

from test_common import BaseTestCase, BroAction, BroBackup
from bro_bm_config import BroBMConfig, main
from common import HookException

class TestBroBMConfig(BaseTestCase):

    @patch('time.sleep')
    @patch('common.Bro')
    @patch('lib.broapi.Retention')
    def test_configure_retention_default(self, p_retention, p_bro_api, _sleep):
        m_bro = MagicMock(name='m_bro')
        p_bro_api.return_value = m_bro

        m_state = PropertyMock(name='m_state', side_effect=[
                'RUNNING', 'RUNNING',
                'FINISHED', 'FINISHED'
        ])
        a1 = BroAction(name='test', id='12345', progress_info = None, result='SUCCESS',
                       state=m_state, scope='DEFAULT',
                       start_time='', completion_time='',
                       progress=0,
                       additional_info=None)
        type(a1).state = m_state
        m_retention = MagicMock(name='m_retention', side_effect=[a1],
            purge=True,
            limit=3
        )

        m_values = '{"limit":"2", "autoDelete":true}'
        m_apply = MagicMock(
            name='m_apply', side_effect=[a1])
        m_retention.apply = m_apply
        p_retention.return_value = m_retention

        m_bro.get_retention.return_value = m_retention

        klass = BroBMConfig()
        klass.configure_retention(m_values)
        m_retention.apply.assert_called_once()

    @patch('time.sleep')
    @patch('common.Bro')
    def test_do_restore_default_config(self, p_bro_api, _sleep):
        m_bro = MagicMock(name='m_bro')
        p_bro_api.return_value = m_bro

        m_state = PropertyMock(
            name='m_state', side_effect=[
                'RUNNING', 'RUNNING',
                'FINISHED', 'FINISHED'
            ])
        a1 = BroAction(name='test', id='12345', progress_info = None, result='SUCCESS',
                       state=m_state, scope='DEFAULT',
                       start_time='', completion_time='',
                       progress=0,
                       additional_info=None)
        type(a1).state = m_state

        m_restore = MagicMock(
            name='m_restore', side_effect=[a1])
        m_bro.restore = m_restore

        try:
            klass = BroBMConfig()
            klass.do_restore('backup', 'DEFAULT')
            m_restore.assert_called_once_with('backup', 'DEFAULT-bro')
        finally:
            type(a1).state = str

    @patch('time.sleep')
    @patch('common.Bro')
    def test_do_restore_default_config_file_name(self, p_bro_api, _sleep):
        m_bro = MagicMock(name='m_bro')
        p_bro_api.return_value = m_bro

        m_scopes = MagicMock(name='m_scopes')
        m_scopes.__iter__.return_value = [MagicMock("m_scope", id="DEFAULT")]
        m_bro.scopes = m_scopes

        m_backups = MagicMock(name='m_backups')
        m_backups.return_value = [BroBackup("backup", [])]
        m_bro.backups = m_backups

        m_state = PropertyMock(
            name='m_state', side_effect=[
                'RUNNING', 'RUNNING',
                'FINISHED', 'FINISHED'
            ])
        a1 = BroAction(name='test', id='12345', progress_info = None, result='SUCCESS',
                       state=m_state, scope='DEFAULT',
                       start_time='', completion_time='',
                       progress=0,
                       additional_info=None)
        type(a1).state = m_state

        m_restore = MagicMock(
            name='m_restore', side_effect=[a1])
        m_bro.restore = m_restore
        m_backup_name = 'backup'
        m_bro.get_backup('backup', 'DEFAULT').name =m_backup_name

        try:
            klass = BroBMConfig()
            klass.do_restore('backup.tar.gz', 'DEFAULT')
            m_restore.assert_called_once_with('backup', 'DEFAULT-bro')
        finally:
            type(a1).state = str

    @patch('time.sleep')
    @patch('common.Bro')
    def test_execute_restore_backup_manager_config_error(self, p_bro_api, _sleep):
        m_bro = MagicMock(name='m_bro')
        p_bro_api.return_value = m_bro

        a1 = BroAction(name='test', id='12345', progress_info ='Agent :bravo failed at Stage: EXECUTION, \nmessage: some message\n',
                       result='FAILURE', state='FINISHED', scope='DEFAULT',
                       start_time='', completion_time='', progress=0,
                       additional_info='')

        m_bro.restore = MagicMock(name='m_restore', return_value=a1)
        klass = BroBMConfig()
        self.assertRaises(HookException, klass.execute_restore_backup_manager_config,
                          'backup', 'DEFAULT')

    @patch('common.Bro')
    def test_do_restore_rollback_config(self, p_bro_api):
        m_bro = MagicMock(name='m_bro')
        p_bro_api.return_value = m_bro

        m_restore = MagicMock(
            name='m_restore')
        m_bro.restore = m_restore

        klass = BroBMConfig()
        klass.do_restore('backup', 'ROLLBACK')
        m_restore.assert_not_called()

    @patch('bro_bm_config.ResetBroConfigMap')
    @patch('bro_bm_config.BroBMConfig')
    def test_main_restore(self, p_bro_bm_config, p_reset_bro_config_map):
        p_bro_bm_config.return_value = MagicMock(name='m_BroBMConfig')
        m_do_restore = MagicMock(name='m_do_restore')
        p_bro_bm_config.return_value.do_restore = m_do_restore

        p_reset_bro_config_map.return_value = MagicMock(name='m_ResetBroConfigMap')
        m_reset_restore_state = MagicMock(name='m_reset_restore_state')
        p_reset_bro_config_map.return_value.reset_restore_state = m_reset_restore_state

        main(['-b', 'some_backup', '-s', 'DEFAULT', '-c', 'br_config_map'])
        m_do_restore.assert_called_once_with(
            'some_backup', 'DEFAULT')
        m_reset_restore_state.assert_called_once_with('br_config_map')

    @patch('bro_bm_config.ScheduleControl')
    def test_main_rollback(self, p_scheduling_control):
        p_scheduling_control.return_value = MagicMock(name='m_ScheduleControl')
        m_scheduling_control = MagicMock(name='m_scheduling_control')
        p_scheduling_control.return_value.scheduling_control = m_scheduling_control

        main(['-b', 'some_backup', '-s', 'ROLLBACK', '-c', 'br_config_map'])
        m_scheduling_control.assert_called_once_with(True, None)

    @patch('bro_bm_config.ResetBroConfigMap')
    @patch('bro_bm_config.ScheduleControl')
    @patch('bro_bm_config.BroBMConfig')
    def test_main_rollback(self, p_bro_bm_config, p_configure_scheduling, p_reset_bro_config_map):
        p_configure_scheduling.return_value = MagicMock(name='m_ScheduleControl')
        m_configure_scheduling = MagicMock(name='m_configure_scheduling')
        p_configure_scheduling.return_value.configure_scheduling = m_configure_scheduling
        args_values = '{"backupPrefix":"S_B","enabled":false,"export":false,"schedules":[]}'

        p_reset_bro_config_map.return_value = MagicMock(name='m_ResetBroConfigMap')
        m_reset_restore_state = MagicMock(name='m_reset_restore_state')
        p_reset_bro_config_map.return_value.reset_restore_state = m_reset_restore_state

        main(['-b', '-', '-s', '-', '-c', 'br_config_map', '--values', args_values])
        m_configure_scheduling.assert_called_once_with(args_values, None)
        m_reset_restore_state.assert_called_once_with('br_config_map')

    @patch('bro_bm_config.ResetBroConfigMap')
    @patch('bro_bm_config.ScheduleControl')
    @patch('bro_bm_config.BroBMConfig')
    def test_main_install(self, p_bro_bm_config, p_configure_scheduling, p_reset_bro_config_map):
        p_bro_bm_config.return_value = MagicMock(name='m_BroBMConfig')
        m_configure_retention = MagicMock(name='m_configure_retention')
        p_bro_bm_config.return_value.configure_retention = m_configure_retention

        p_configure_scheduling.return_value = MagicMock(name='m_ScheduleControl')
        m_configure_scheduling = MagicMock(name='m_configure_scheduling')
        p_configure_scheduling.return_value.configure_scheduling = m_configure_scheduling
        args_values = '{"backupPrefix":"S_B","enabled":false,"export":false,"schedules":[]}'

        p_reset_bro_config_map.return_value = MagicMock(name='m_ResetBroConfigMap')
        m_reset_restore_state = MagicMock(name='m_reset_restore_state')
        p_reset_bro_config_map.return_value.reset_restore_state = m_reset_restore_state

        main(['-b', '-', '-s', '-', '-c', 'br_config_map', '--values', args_values])
        m_configure_retention.assert_called_once()
        m_configure_scheduling.assert_called_once_with(args_values, None)
        m_reset_restore_state.assert_called_once_with('br_config_map')
