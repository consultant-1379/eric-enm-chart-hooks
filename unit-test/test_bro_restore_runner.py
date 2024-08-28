from unittest.mock import MagicMock, PropertyMock, call, patch

from kubernetes.client.models.v1_config_map import V1ConfigMap
from kubernetes.client.models.v1_config_map_list import V1ConfigMapList
from kubernetes.client.models.v1_object_meta import V1ObjectMeta

from test_common import BaseTestCase, BroAction, PATCH_load_incluster_config, \
    PATCH_load_kube_config, BroBackup, BroService
from bro_restore_runner import BroRestoreRunner, main
from common import HookException


class TestBroRestoreRunner(BaseTestCase):

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('time.sleep')
    @patch('common.CoreV1Api')
    @patch('common.Bro')
    def test_execute_restore(self, p_bro_api, p_core, _sleep):
        cfg_map = V1ConfigMap(
            metadata=V1ObjectMeta(name='cfg-map'),
            data={'key_1': 'value_1'}
        )
        m_list = MagicMock(name='m_list_namespaced_config_map')
        p_core.return_value.list_namespaced_config_map = m_list
        m_list.return_value = V1ConfigMapList(items=[cfg_map])
        p_core.return_value.read_namespaced_config_map.return_value = cfg_map

        m_patch = MagicMock(name='m_patch_namespaced_config_map')
        p_core.return_value.patch_namespaced_config_map = m_patch

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
        type(a1).state = m_state

        m_bro.restore = MagicMock(
            name='m_restore', side_effect=[a1])

        try:
            klass = BroRestoreRunner()
            waiting = klass.execute_restore('backup', 'ROLLBACK', 'cfg-map')
            self.assertFalse(waiting)
            m_patch.assert_called_once_with('cfg-map', self.namespace(),
                                            cfg_map)
        finally:
            type(a1).state = str

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('time.sleep')
    @patch('common.CoreV1Api')
    @patch('common.Bro')
    def test_execute_restore_waiting_for_agents(self,
                                                p_bro_api, p_core, _sleep):
        m_bro = MagicMock(name='m_bro')
        p_bro_api.return_value = m_bro

        add_info = 'Agents with the following IDs are required:\n[s1, s2, s3]'
        a1 = BroAction(name='test', id='12345', progress_info = None, result='FAILURE',
                       state='FINISHED', scope='ROLLBACK',
                       start_time='', completion_time='',
                       progress=0,
                       additional_info=add_info)

        m_bro.restore = MagicMock(name='m_restore', return_value=a1)
        klass = BroRestoreRunner()
        waiting = klass.execute_restore('backup', 'ROLLBACK', 'cfg-map')
        self.assertTrue(waiting)

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('time.sleep')
    @patch('common.CoreV1Api')
    @patch('common.Bro')
    def test_execute_restore_error(self, p_bro_api, p_core, _sleep):
        m_bro = MagicMock(name='m_bro')
        p_bro_api.return_value = m_bro

        a1 = BroAction(name='test', id='12345', progress_info='Agent :bravo failed at Stage: EXECUTION,\n message: some message\n', result='FAILURE',
                       state='FINISHED', scope='ROLLBACK',
                       start_time='', completion_time='',
                       progress=0,
                       additional_info='')

        m_bro.restore = MagicMock(name='m_restore', return_value=a1)
        klass = BroRestoreRunner()
        self.assertRaises(HookException, klass.execute_restore,
                          'backup', 'ROLLBACK', 'cfg-map')

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('time.sleep')
    @patch('common.CoreV1Api')
    @patch('common.Bro')
    def test_do_restore_waiting(self, p_bro_api, p_core, p_sleep):
        cfg_map = V1ConfigMap(
            metadata=V1ObjectMeta(name='cfg-map'),
            data={}
        )
        p_core.return_value.read_namespaced_config_map.side_effect = [cfg_map]

        m_patch_namespaced_config_map = MagicMock(name='m_patch')
        p_core.return_value.patch_namespaced_config_map = \
            m_patch_namespaced_config_map

        m_bro = MagicMock(name='m_bro')
        p_bro_api.return_value = m_bro

        m_agents = PropertyMock(name='m_agents', side_effect=[
            ['postgres'],
            ['postgres', 'eric-enm-mdt-bro-agent'],
            ['postgres', 'eric-enm-mdt-bro-agent'],
            ['postgres', 'eric-enm-mdt-bro-agent'],
            ['postgres', 'eric-enm-mdt-bro-agent']
        ])
        m_status = PropertyMock(name='m_status', return_value=m_agents)
        m_bro.status = m_status

        type(m_status).agents = m_agents

        m_bro.get_backup.return_value = BroBackup(
            'backup', [BroService('mdt', 'eric-enm-mdt-bro-agent'), BroService('pg', 'postgres')]
        )

        klass = BroRestoreRunner()
        klass.execute_restore = MagicMock(
            name='m_execute_restore', side_effect=[True, False])
        try:
            klass.do_restore('backup', 'cfg-map', 'ROLLBACK')
        finally:
            type(m_status).agents = list

        self.assertIn('RESTORE_STATE', cfg_map.data)
        self.assertEqual('finished', cfg_map.data['RESTORE_STATE'])
        m_patch_namespaced_config_map.assert_called_once_with(
            'cfg-map', self.namespace(), cfg_map)

        p_sleep.assert_called_once_with(30)

    @patch('bro_restore_runner.BroRestoreRunner')
    def test_main(self, p_bro_restore_runner):
        p_bro_restore_runner.return_value = MagicMock(
            name='m_BroRestoreRunner')
        m_do_restore = p_bro_restore_runner.return_value.do_restore = \
            MagicMock(name='m_do_restore')

        self.assertRaises(SystemExit, main, [])
        main(['-b', 'some_backup', '-c', 'br_config_map', '-s', 'ROLLBACK'])
        m_do_restore.assert_called_once_with(
            'some_backup', 'br_config_map', 'ROLLBACK')
