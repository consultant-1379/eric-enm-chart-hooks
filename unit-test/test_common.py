import os
import shutil
from argparse import ArgumentParser
from collections import namedtuple
from os.path import isdir, join
from tempfile import gettempdir
from unittest import TestCase
from unittest.mock import ANY, MagicMock, PropertyMock, mock_open, patch

from kubernetes.client.api.batch_v1_api import BatchV1Api
from kubernetes.client.api.core_v1_api import CoreV1Api
from kubernetes.client.api_client import ApiClient
from kubernetes.client.exceptions import ApiException
from kubernetes.client.models.v1_config_map import V1ConfigMap
from kubernetes.client.models.v1_job import V1Job
from kubernetes.client.models.v1_job_list import V1JobList
from kubernetes.client.models.v1_object_meta import V1ObjectMeta
from kubernetes.client.models.v1_secret import V1Secret
from kubernetes.client.models.v1_status import V1Status
from kubernetes.config import ConfigException

from lib.broapi import Bro

os.environ['BRO_HOST'] = 'localhost'
os.environ['BRO_PORT'] = '0'

from common import BroCliBaseClass, HookException, KubeApi, \
    KubeBatchBaseClass, get_parsed_args

BroService = namedtuple('Service', ['name', 'agent_id'])
BroBackup = namedtuple('Backup', ['name', 'services'])
BroAction = namedtuple('Action', [
    'name', 'id', 'progress_info', 'result', 'state', 'scope', 'start_time', 'completion_time',
    'additional_info', 'progress'
])

PATCH_load_incluster_config = MagicMock(name='m_load_incluster_config')
PATCH_load_kube_config = MagicMock(name='m_load_kube_config')


class BaseTestCase(TestCase):
    def __init__(self, method_name):
        super().__init__(method_name)
        self.tmpdir = join(gettempdir(), self.__class__.__name__)

    @staticmethod
    def namespace():
        return 'enm404'

    @staticmethod
    def reset_mocks(*mocks):
        for _mock in mocks:
            _mock.reset_mock(return_value=True, side_effect=True)

    def setUp(self) -> None:
        if not isdir(self.tmpdir):
            os.makedirs(self.tmpdir)

        os.environ['SA_NAMESPACE'] = join(self.tmpdir, 'namespace')
        with open(os.environ['SA_NAMESPACE'], 'w') as _w:
            _w.write(BaseTestCase.namespace())

        PATCH_load_incluster_config.reset_mock(
            return_value=True, side_effect=True)
        PATCH_load_kube_config.reset_mock(
            return_value=True, side_effect=True)

    def tearDown(self) -> None:
        del os.environ['SA_NAMESPACE']
        if isdir(self.tmpdir):
            shutil.rmtree(self.tmpdir)


class TestKubeApi(BaseTestCase):

    def test_namespace_file(self):
        self.assertEqual(
            '/var/run/secrets/kubernetes.io/serviceaccount/namespace',
            KubeApi.namespace_file())

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    def test_init_load_incluster_config_ok(self):
        KubeApi()
        self.assertEqual(1, PATCH_load_incluster_config.call_count)
        self.assertEqual(0, PATCH_load_kube_config.call_count)

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    def test_init_load_incluster_config_fail(self):
        PATCH_load_incluster_config.side_effect = [
            ConfigException()
        ]
        KubeApi()
        self.assertEqual(1, PATCH_load_incluster_config.call_count)
        self.assertEqual(1, PATCH_load_kube_config.call_count)

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    def test_init_load_kube_fail(self):
        PATCH_load_incluster_config.side_effect = [
            ConfigException('oops-load_incluster_config')
        ]
        PATCH_load_kube_config.side_effect = [
            ConfigException('oops-load_kube_config')
        ]
        self.assertRaises(HookException, KubeApi)

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    def test_init_load_all_ok(self):
        klass = KubeApi()
        self.assertEqual(self.namespace(), klass.namespace())

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    def test_api_core(self):
        klass = KubeApi()
        api_core = klass.api_core()
        self.assertIsInstance(api_core, CoreV1Api)

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    def test_api_client(self):
        klass = KubeApi()
        api_client = klass.api_client()
        self.assertIsInstance(api_client, ApiClient)

    @patch('common.exists')
    def test_read_secret(self, p_exists):
        p_exists.side_effect = [False, True]

        actual = KubeApi.read_secret('/some/file')
        self.assertEqual('', actual)

        expect = 'something'
        with patch("builtins.open", mock_open(read_data=expect)):
            actual = KubeApi.read_secret('/some/file')
            self.assertEqual(expect, actual)

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('common.CoreV1Api')
    def test_get_configmap(self, p_core):
        klass = KubeApi()

        cfg_map = V1ConfigMap(
            data={'key': False}
        )

        p_core.return_value.read_namespaced_config_map.side_effect = [cfg_map]

        read = klass.get_configmap('configmap_name')
        self.assertEqual(cfg_map, read)

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('common.CoreV1Api')
    def test_get_secret(self, p_core):
        klass = KubeApi()
        m_secret = V1Secret(
            data={'key': False}
        )
        p_core.return_value.read_namespaced_secret.side_effect = [m_secret]
        read = klass.get_secret('secret_name')
        self.assertEqual(m_secret.data, read)

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('common.CoreV1Api')
    def test_get_secret_not_exist(self, p_core):
        klass = KubeApi()
        p_core.return_value.read_namespaced_secret.side_effect = [
            ApiException("Secret 'secret_name' not found")
        ]
        read = klass.get_secret('secret_name')
        self.assertEqual(None, read)

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('common.CoreV1Api')
    def test_delete_secret(self, p_core):
        klass = KubeApi()
        m_status = V1Status(
            status='Success'
        )
        p_core.return_value.delete_namespaced_secret.side_effect = [m_status]
        read = klass.delete_secret('secret_name')
        self.assertEqual(m_status.status, read.status)

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('common.CoreV1Api')
    def test_patch_configmap(self, p_core):
        klass = KubeApi()

        cfg_map = V1ConfigMap(
            metadata=V1ObjectMeta(name='cfg_map'),
            data={'key': False}
        )

        p_core.return_value.patch_namespaced_config_map.side_effect = [
            cfg_map
        ]
        klass.patch_configmap(cfg_map)

        p_core.return_value.patch_namespaced_config_map.assert_called_with(
            cfg_map.metadata.name, klass.namespace(), cfg_map
        )


class TestBroCliBaseClass(BaseTestCase):

    def test_brocli(self):
        klass = BroCliBaseClass()
        self.assertIsInstance(klass.bro_api(), Bro)

    @patch('common.Bro')
    def test_exists(self, p_bro_api):
        m_bro = MagicMock(name='m_bro')
        p_bro_api.return_value = m_bro

        Backup = namedtuple('Backup', ['name'])

        m_bro.backups = MagicMock('backups')
        m_bro.backups.return_value = [
            Backup(name='bk1'), Backup(name='bk2')
        ]

        klass = BroCliBaseClass()
        self.assertTrue(klass.exists('bk1', 'DEFAULT'))
        self.assertFalse(klass.exists('bk3', 'ROLLBACK'))

    @patch('common.Bro')
    def test_import_backup(self, p_bro_api):
        m_bro = MagicMock(name='m_bro')
        p_bro_api.return_value = m_bro

        action = BroAction('import', '12345', '<None>','SUCCESS', 'COMPLETE',
                           'DEFAULT', '0', '0', '', 100)
        m_import_backup = MagicMock(name='m_import_backup',
                                    return_value=action)
        m_bro.import_backup = m_import_backup

        klass = BroCliBaseClass()
        klass.import_backup('backup', 'sftp@sftp', 'sftp')

    @patch('common.Bro')
    def test_import_backup_failed(self, p_bro_api):
        m_bro = MagicMock(name='m_bro')
        p_bro_api.return_value = m_bro

        action = BroAction('import', '12345', '<None>', 'FAILURE', 'COMPLETE',
                           'DEFAULT', '0', '0', '', 100)
        m_import_backup = MagicMock(name='m_import_backup',
                                    return_value=action)
        m_bro.import_backup = m_import_backup

        klass = BroCliBaseClass()
        self.assertRaises(HookException, klass.import_backup,
                          'backup', 'sftp@sftp', 'sftp')

    @patch('time.sleep')
    @patch('common.Bro')
    def test_wait_for_action_complete(self, p_bro_api, p_sleep):
        m_bro = MagicMock(name='m_bro')
        p_bro_api.return_value = m_bro

        m_state = PropertyMock(
            name='m_state', side_effect=[
                'RUNNING', 'RUNNING',
                'FINISHED', 'FINISHED'
            ])
        action = BroAction('import', '12345', '<None>', 'SUCCESS', m_state,
                           'DEFAULT', '0', '0', '', 100)
        type(action).state = m_state

        klass = BroCliBaseClass()
        try:
            klass.wait_for_action(action)
            self.assertEqual(1, p_sleep.call_count)
        finally:
            type(action).state = str

    @patch('common.Bro')
    def test_wait_for_action_cycle(self, p_bro_api):
        m_bro = MagicMock(name='m_bro')
        p_bro_api.return_value = m_bro

    @patch('common.Bro')
    def test_get_backup(self, p_bro_api):
        m_bro = MagicMock(name='m_bro')
        p_bro_api.return_value = m_bro

        m_get_backup = MagicMock(name='m_get_backup')
        m_bro.get_backup = m_get_backup

        klass = BroCliBaseClass()
        klass.get_backup('backup', 'DEFAULT')
        m_get_backup.assert_called_once_with('backup', 'DEFAULT')


class TestKubeBatchBaseClass(BaseTestCase):

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    def test_api_batch(self):
        klass = KubeBatchBaseClass()
        api_batch = klass.api_batch()
        self.assertIsInstance(api_batch, BatchV1Api)

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('common.BatchV1Api')
    def test_list_jobs(self, p_batch):
        klass = KubeBatchBaseClass()

        p_batch.return_value.list_namespaced_job.side_effect = [
            V1JobList(items=[
                V1Job(metadata=V1ObjectMeta(name='j1')),
                V1Job(metadata=V1ObjectMeta(name='j2'))
            ])
        ]

        job_names = klass.list_jobs()
        self.assertEqual(['j1', 'j2'], job_names)

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('common.time')
    @patch('common.BatchV1Api')
    def test_delete_job(self, p_batch, _):
        klass = KubeBatchBaseClass()

        job1 = V1Job(metadata=V1ObjectMeta(name='j1'))
        job2 = V1Job(metadata=V1ObjectMeta(name='j2'))

        p_batch.return_value.list_namespaced_job.side_effect = [
            V1JobList(items=[job1, job2]),
            V1JobList(items=[job1, job2]),
            V1JobList(items=[job1]),
        ]
        klass.delete_job('j2')
        p_batch.return_value.delete_namespaced_job.assert_any_call(
            'j2', klass.namespace(), body=ANY
        )

        self.reset_mocks(
            p_batch,
            p_batch.return_value.list_namespaced_job)

        p_batch.return_value.list_namespaced_job.side_effect = [
            V1JobList(items=[job1, job2])
        ]
        klass.delete_job('j3')

        self.assertEqual(
            0, p_batch.return_value.delete_namespaced_job.call_count)


class TestCommonFunctions(BaseTestCase):
    def test_get_parsed_args(self):
        parser = ArgumentParser()
        parser.add_argument('-t', dest='test')
        self.assertRaises(SystemExit, get_parsed_args, [], parser)

        parsed = get_parsed_args(['-t', 'value'], parser)
        self.assertEqual('value', parsed.test)
