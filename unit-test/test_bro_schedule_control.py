import base64
from unittest.mock import MagicMock, PropertyMock, patch

from collections import namedtuple
from os.path import join

from kubernetes.client.api.batch_v1_api import BatchV1Api
from kubernetes.client.api.core_v1_api import CoreV1Api
from kubernetes.client.api_client import ApiClient
from kubernetes.client.models.v1_config_map import V1ConfigMap
from kubernetes.client.models.v1_object_meta import V1ObjectMeta

from test_common import BaseTestCase, BroAction, PATCH_load_incluster_config, \
    PATCH_load_kube_config, BroBackup, BroService
from bro_schedule_control import ScheduleControl, main
from common import BroCliBaseClass, HookException, KubeApi, \
    KubeBatchBaseClass, get_parsed_args
from lib.broapi import Schedule

class TestBroScheduleControl(BaseTestCase):

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('time.sleep')
    @patch('common.Bro')
    @patch('lib.broapi.Schedule')
    def test_configure_scheduling_no_values(self, p_schedule, p_bro_api, _sleep):
        m_bro = MagicMock(name='m_bro')
        p_bro_api.return_value = m_bro
        m_schedule = MagicMock(name='m_schedule',
            enabled=True,
            recent_created = None,
            prefix = 'SCHEDULED_BACKUP',
            export = False,
            export_password = None,
            export_uri = None
        )
        p_schedule.return_value = m_schedule
        m_bro.get_schedule.return_value = m_schedule
        klass = ScheduleControl()
        klass.configure_scheduling(values='-')
        m_schedule.update.assert_called_once()

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('common.KubeApi.delete_secret')
    @patch('common.KubeApi.get_secret')
    @patch('time.sleep')
    @patch('common.Bro')
    @patch('lib.broapi.Schedule')
    def test_configure_scheduling_configs_provided(self, p_schedule, p_bro_api, _sleep, p_get_secret, p_delete_secret):
        m_bro = MagicMock(name='m_bro')
        p_bro_api.return_value = m_bro

        m_uri = base64.b64encode("sftp://user@something:/some_path/".encode("utf-8"))
        m_pass = base64.b64encode("somepassword".encode("utf-8"))
        m_secret = MagicMock(name='m_secret')
               
        s_data = {'externalStorageURI': m_uri, 'externalStorageCredentials': m_pass}
        m_secret.__getitem__.side_effect  = s_data.__getitem__
        p_get_secret.return_value = m_secret
        m_secret_delete = MagicMock(name='m_secret_delete',
                                    status='Success') 
        p_delete_secret.return_value = m_secret_delete
        m_schedule = MagicMock(name='m_schedule',
            enabled=True,
            recent_created = None,
            prefix = 'SCHEDULED_BACKUP',
            export = False,
            export_password = None,
            export_uri = None
        )
        p_schedule.return_value = m_schedule

        m_bro.get_schedule.return_value = m_schedule
        klass = ScheduleControl()

        m_values = '{"backupPrefix":"SCHEDULED_BACKUP_WITH_EXPORT",' \
                    '"enabled":true,"export":true,' \
                    '"schedules":[{"every":"1w","start":"2022-10-22T04:00:00"},'\
                                '{"every":"3d","stop":"2022-10-22T12:00:00"},'\
                                '{"every":"2d4m","stop":"2022-10-28T04:20:50","start":"2022-10-24T12:12:12"},'\
                                '{"every":null,"start":"2022-10-28T04:20:50"},'\
                                '{"every":"5h","stop":"null"},'\
                                '{"every":"6h30m","start":null},'\
                                '{"6h30m":"every","start":"2022-10-24T12:12:12"},'\
                                '{"every":"0w0d0h0m","start":"2022-10-24T12:12:12"},'\
                                '{"every ":"15m"},'\
                                '{"start":"2022-10-24T12:12:12"},'\
                                '{"every":"1week","start":"2022-10-24T12:12:12"},'\
                                '{"every":"50m","start":"2022/10/24 12:12:12"},'\
                                '{"every":"1d","start":"22-10-24T12:12:12"}]}'
        klass.configure_scheduling(m_values, "secret-name")
        m_schedule.update.assert_called_once_with(
            True,
            'SCHEDULED_BACKUP_WITH_EXPORT',
            True,
            'somepassword',
            'sftp://user@something:/some_path/')

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('common.KubeApi.get_secret')
    @patch('time.sleep')
    @patch('common.Bro')
    @patch('lib.broapi.Schedule')
    def test_configure_scheduling_no_secret_exist(self, p_schedule, p_bro_api, _sleep, p_secret):
        m_bro = MagicMock(name='m_bro')
        p_bro_api.return_value = m_bro

        m_apicore = MagicMock(name='m_apicore')
        p_secret.return_value = None
        m_schedule = MagicMock(name='m_schedule',
            enabled=None,
            recent_created = None,
            prefix = None,
            export = None,
            export_password = None,
            export_uri = None
        )
        p_schedule.return_value = m_schedule

        m_bro.get_schedule.return_value = m_schedule
        klass = ScheduleControl()

        m_values = '{"backupPrefix":"SCHEDULED_BACKUP_NO_EXPORT","enabled":true,"export":true,"schedules":[{"dayOfWeek":"Tue","startTime":"02:00"},{"dayOfWeek":"Thu","startTime":"04:00"},{"dayOfWeek":"Fri","startTime":"03:00"}]}'
        klass.configure_scheduling(m_values, "nonexisting_secret")
        m_schedule.update.assert_called_once_with(
            True,
            'SCHEDULED_BACKUP_NO_EXPORT',
            None,
            None,
            None)

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('time.sleep')
    @patch('common.Bro')
    @patch('lib.broapi.Schedule')
    def test_disable_scheduling(self, p_schedule, p_bro_api, _sleep):
        m_bro = MagicMock(name='m_bro')
        p_bro_api.return_value = m_bro

        m_schedule = MagicMock(name='m_schedule',
            enabled=True,
            recent_created = None,
            prefix = 'SCHEDULED_BACKUP',
            export = False,
            export_password = None,
            export_uri = None
        )
        p_schedule.return_value = m_schedule
        m_bro.get_schedule.return_value = m_schedule
        klass = ScheduleControl()
        klass.enable_scheduling(False)
        m_schedule.update.assert_called_once()

    def test_main_missing_args(self):
        self.assertRaises(SystemExit, main, [])

    @patch('bro_schedule_control.ScheduleControl')
    def test_main_with_args(self, p_schedule_control):
        p_schedule_control.return_value = MagicMock(name='m_ScheduleControl')
        m_scheduling_control = MagicMock(name='m_scheduling_control')
        p_schedule_control.return_value.enable_scheduling = m_scheduling_control
        main(['--disabled'])
        m_scheduling_control.assert_called_once_with(False)
