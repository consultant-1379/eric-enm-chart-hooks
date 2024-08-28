from unittest.mock import MagicMock, PropertyMock, patch

from kubernetes.client.models.v1_config_map import V1ConfigMap

from bro_restore_report import BroRestoreReport, main
from common import HookException
from test_common import BaseTestCase, BroAction, PATCH_load_incluster_config, \
    PATCH_load_kube_config


class TestBroRestoreWait(BaseTestCase):

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('time.sleep')
    @patch('common.Bro')
    @patch('common.CoreV1Api')
    def test_show_restore_action(self, p_core, p_bro_api, p_sleep):
        m_bro = MagicMock(name='m_bro')
        p_bro_api.return_value = m_bro
        m_actions = MagicMock(name='m_actions')
        m_bro.actions = m_actions

        cfg_map = V1ConfigMap(
            data={'RESTORE_ACTION_ID': None}
        )
        p_core.return_value.read_namespaced_config_map.return_value = cfg_map

        klass = BroRestoreReport()

        klass.show_restore_action('cdf_map', 'ROLLBACK')
        self.assertEqual(0, m_bro.actions.call_count)

        action_ok = BroAction(name='RESTORE', id='12', progress_info = None, result='SUCCESS',
                              state='COMPLETE', scope='DEFAULT',
                              start_time='', completion_time='',
                              progress=0,
                              additional_info=None)

        action_fail = BroAction(name='RESTORE', id='12', progress_info = None, result='FAILURE',
                                state='COMPLETE', scope='DEFAULT',
                                start_time='', completion_time='',
                                progress=0,
                                additional_info=None)

        m_actions.return_value = [action_ok]
        cfg_map.data['RESTORE_ACTION_ID'] = '122'
        klass.show_restore_action('cdf_map', 'ROLLBACK')

        cfg_map.data['RESTORE_ACTION_ID'] = '12'
        m_actions.return_value = [action_ok, action_fail]
        self.assertRaises(HookException, klass.show_restore_action, 'cdf_map',
                          'ROLLBACK')

        m_actions.return_value = [action_ok]
        klass.show_restore_action('cdf_map', 'ROLLBACK')

        m_actions.return_value = [action_fail]
        self.assertRaises(HookException, klass.show_restore_action, 'cdf_map',
                          'ROLLBACK')

        m_state = PropertyMock(
            name='m_state', side_effect=[
                'RUNNING', 'RUNNING', 'COMPLETE', 'COMPLETE', 'COMPLETE'
            ])
        action_run_complete = BroAction(name='RESTORE', id='12', progress_info = None,
                                        result='SUCCESS',
                                        state=m_state, scope='DEFAULT',
                                        start_time='', completion_time='',
                                        progress=0,
                                        additional_info=None)
        type(action_run_complete).state = m_state
        m_actions.return_value = [action_run_complete]
        try:
            klass.show_restore_action('cdf_map', 'ROLLBACK')
            p_sleep.assert_called_once_with(5)
        finally:
            type(action_run_complete).state = list

    @patch('bro_restore_report.BroRestoreReport')
    def test_main(self, p_report_hook):
        p_report_hook.return_value = MagicMock(
            name='m_BroRestoreReport')
        m_show_restore_action = p_report_hook.return_value. \
            show_restore_action = MagicMock(name='m_show_restore_action')

        self.assertRaises(SystemExit, main, [])
        main(['-c', 'cfm_map', '-s', 'DEFAULT'])
        m_show_restore_action.assert_called_once_with('cfm_map', 'DEFAULT')
