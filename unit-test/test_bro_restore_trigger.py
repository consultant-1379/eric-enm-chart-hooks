import os
from collections import namedtuple
from os.path import join
from unittest.mock import ANY, MagicMock, patch

from kubernetes.client.models.v1_config_map import V1ConfigMap
from kubernetes.client.models.v1_container import V1Container
from kubernetes.client.models.v1_job import V1Job
from kubernetes.client.models.v1_job_list import V1JobList
from kubernetes.client.models.v1_object_meta import V1ObjectMeta
from kubernetes.client.models.v1_pod import V1Pod
from kubernetes.client.models.v1_pod_spec import V1PodSpec

from bro_restore_trigger import BroImportAndRestoreTrigger, main
from common import HookException
from test_common import BaseTestCase, BroAction, BroBackup, \
    PATCH_load_incluster_config, PATCH_load_kube_config

BroService = namedtuple('Service', ['name', 'agent_id', 'version'])


class TestBroImportTrigger(BaseTestCase):

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('common.CoreV1Api')
    @patch('common.Bro')
    def test_import_backup_already_imported(self, p_bro_api, p_apicore):
        m_bro = MagicMock(name='m_bro')
        p_bro_api.return_value = m_bro

        pv_cfg_map = V1ConfigMap(
            metadata=V1ObjectMeta(
                name='product-version-configmap',
                annotations={
                    'ericsson.com/product-revision': '12.34'
                }
            )
        )

        p_apicore.return_value.read_namespaced_config_map.side_effect = [pv_cfg_map]

        m_product_number_config_map = MagicMock(name='m_product_number')
        p_apicore.return_value.product_number_config_map = \
            m_product_number_config_map

        backup = BroBackup(
            'backup', [BroService('Ericsson Network Manager', 'APPLICATION_INFO', '12.34')]
        )
        m_backups = MagicMock(name='m_backups', return_value=[backup])
        m_bro.backups = m_backups

        m_import_backup = MagicMock(name='m_import_backup')
        m_bro.import_backup = m_import_backup

        m_bro.get_backup.return_value = backup

        klass = BroImportAndRestoreTrigger()

        klass.import_backup('/secrets', 'backup', 'ROLLBACK')
        m_import_backup.assert_not_called()

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('common.Bro')
    def test_import_backup_no_secrets(self, p_bro_api):
        m_bro = MagicMock(name='m_bro')
        p_bro_api.return_value = m_bro

        m_backups = MagicMock(name='m_backups', return_value=[])
        m_bro.backups = m_backups

        klass = BroImportAndRestoreTrigger()
        self.assertRaises(HookException, klass.import_backup,
                          '/secrets', 'backup', 'ROLLBACK')

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('common.CoreV1Api')
    @patch('common.Bro')
    def test_import_backups(self, p_bro_api, p_apicore):
        m_bro = MagicMock(name='m_bro')
        p_bro_api.return_value = m_bro

        m_apicore = MagicMock(name='m_apicore')
        p_apicore.return_value = m_apicore
        pv_cfg_map = V1ConfigMap(
            metadata=V1ObjectMeta(
                name='product-version-configmap',
                annotations={
                    'ericsson.com/product-revision': '12.34'
                }
            )
        )

        p_apicore.return_value.read_namespaced_config_map.side_effect = [pv_cfg_map]

        m_product_number_config_map = MagicMock(name='m_product_number')
        p_apicore.return_value.product_number_config_map = \
            m_product_number_config_map

        backup = BroBackup(
            'backup', [BroService('Ericsson Network Manager', 'APPLICATION_INFO', '12.34')]
        )
        m_backups = MagicMock(name='m_backups', return_value=[backup])
        m_bro.backups = m_backups

        m_bro.get_backup.return_value = backup

        restore_action = BroAction(name='RESTORE', id='12345', progress_info = None,
                                   result='SUCCESS',
                                   state='COMPLETE', scope='DEFAULT',
                                   start_time='', completion_time='',
                                   progress=0,
                                   additional_info=None)

        m_import_backup = MagicMock(name='m_import_backup',
                                    return_value=restore_action)
        m_bro.import_backup = m_import_backup

        klass = BroImportAndRestoreTrigger()

        with open(join(self.tmpdir, 'externalStorageURI'), 'w') as _writer:
            _writer.write('externalStorageURI')
        with open(join(self.tmpdir,
                       'externalStorageCredentials'), 'w') as _writer:
            _writer.write('externalStorageCredentials')

        klass.import_backup(self.tmpdir, 'external_backup', 'ROLLBACK')
        m_import_backup.assert_called_once_with(
            'external_backup',
            'externalStorageURI',
            'externalStorageCredentials')

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('common.Bro')
    @patch('common.CoreV1Api')
    def test_create_job_definition(self, p_apicore, _):
        m_apicore = MagicMock(name='m_apicore')
        p_apicore.return_value = m_apicore

        runner_pod = V1Pod(
            spec=V1PodSpec(containers=[
                V1Container(
                    name='container',
                    image='some_image',
                    image_pull_policy='Always'
                )
            ])
        )
        m_read_namespaced_pod = MagicMock(
            name='m_read_namespaced_pod',
            return_value=runner_pod
        )
        m_apicore.read_namespaced_pod = m_read_namespaced_pod

        klass = BroImportAndRestoreTrigger()

        job = klass.create_job_definition(
            'test_job', 'test_backup', 'bro-cm', 'acc', 'ROLLBACK')

        self.assertEqual(1, len(job.spec.template.spec.containers))
        cmd_line = job.spec.template.spec.containers[0].command[-1]
        self.assertEqual(
            'exec_hook bro_restore_runner.py -b test_backup '
            '-c bro-cm -s ROLLBACK',
            cmd_line)

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('common.Bro')
    @patch('common.CoreV1Api')
    def test_create_job_definition_no_envvars(self, _core, _bro):
        klass = BroImportAndRestoreTrigger()

        try:
            del os.environ['BRO_HOST']
            self.assertRaises(HookException, klass.create_job_definition,
                              '/secrets', 'backup', 'cm', 'acc', 'sc')

            os.environ['BRO_HOST'] = 'localhost'
            del os.environ['BRO_PORT']
            self.assertRaises(HookException, klass.create_job_definition,
                              '/secrets', 'backup', 'cm', 'acc', 'sc')
        finally:
            os.environ['BRO_HOST'] = 'localhost'
            os.environ['BRO_PORT'] = '0'

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('common.BatchV1Api')
    @patch('common.CoreV1Api')
    def test_trigger_restore(self, p_coreapi, p_batchapi):
        m_coreapi = MagicMock(name='m_coreapi')
        p_coreapi.return_value = m_coreapi

        m_batchapi = MagicMock(name='m_batchapi')
        p_batchapi.return_value = m_batchapi

        runner_pod = V1Pod(
            spec=V1PodSpec(containers=[
                V1Container(
                    name='container',
                    image='some_image',
                    image_pull_policy='Always'
                )
            ])
        )
        list_jobs_results = [
            V1JobList(items=[
                V1Job(metadata=V1ObjectMeta(name='j1')),
                V1Job(metadata=V1ObjectMeta(name='j2')),
                V1Job(metadata=V1ObjectMeta(name='eric-enm-restore-job'))]),

            V1JobList(items=[
                V1Job(metadata=V1ObjectMeta(name='j1')),
                V1Job(metadata=V1ObjectMeta(name='j2')),
                V1Job(metadata=V1ObjectMeta(name='eric-enm-restore-job'))]),

            V1JobList(items=[
                V1Job(metadata=V1ObjectMeta(name='j1')),
                V1Job(metadata=V1ObjectMeta(name='j2'))])
        ]

        m_coreapi.read_namespaced_pod = MagicMock(
            name='m_read_namespaced_pod',
            return_value=runner_pod)

        m_batchapi.list_namespaced_job = MagicMock(
            name='m_list_namespaced_job',
            side_effect=list_jobs_results
        )

        m_delete_namespaced_job = MagicMock(
            name='m_delete_namespaced_job'
        )
        m_batchapi.delete_namespaced_job = m_delete_namespaced_job

        m_create_namespaced_job = MagicMock()
        m_batchapi.create_namespaced_job = m_create_namespaced_job

        klass = BroImportAndRestoreTrigger()
        klass.trigger_restore(
            'eric-enm-restore-job', 'backup_name', 'cfgmap', 'acc', 'ROLLBACK')

        m_create_namespaced_job.assert_called_once_with(
            klass.namespace(), ANY)
        m_delete_namespaced_job.assert_called_once_with(
            'eric-enm-restore-job', self.namespace(), body=ANY
        )

    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('common.Bro')
    @patch('common.BatchV1Api')
    @patch('common.CoreV1Api')
    def test_import_and_trigger(self, p_apicore, p_batchapi, p_bro_api):
        m_apicore = MagicMock(name='m_apicore')
        p_apicore.return_value = m_apicore

        m_batchapi = MagicMock(name='m_batchapi')
        p_batchapi.return_value = m_batchapi

        m_bro = MagicMock(name='m_bro')
        p_bro_api.return_value = m_bro

        backup = BroBackup(
            'backup', [BroService('Ericsson Network Manager', 'APPLICATION_INFO', '12.34')]
        )
        m_backups = MagicMock(name='m_backups', return_value=[backup])
        m_bro.backups = m_backups

        m_bro.get_backup.return_value = backup

        pv_cfg_map = V1ConfigMap(
            metadata=V1ObjectMeta(
                name='product-version-configmap',
                annotations={
                    'ericsson.com/product-revision': '12.34'
                }
            )
        )

        cfg_map = V1ConfigMap(
            metadata=V1ObjectMeta(name='bro_cm'),
            data={}
        )

        p_apicore.return_value.read_namespaced_config_map.side_effect = [pv_cfg_map, cfg_map]

        response = namedtuple('R', ['status'])(status='OK')
        m_create_namespaced_job = MagicMock(
            name='m_create_namespaced_job',
            return_value=response
        )
        m_batchapi.create_namespaced_job = m_create_namespaced_job

        runner_pod = V1Pod(
            spec=V1PodSpec(containers=[
                V1Container(
                    name='container',
                    image='some_image',
                    image_pull_policy='Always'
                )
            ])
        )
        m_read_namespaced_pod = MagicMock(
            name='m_read_namespaced_pod',
            return_value=runner_pod
        )
        m_apicore.read_namespaced_pod = m_read_namespaced_pod

        klass = BroImportAndRestoreTrigger()
        klass.import_and_trigger(
            'acc', '/secrets', 'job_name', 'backup', 'cfgmap', 'ROLLBACK')

        m_create_namespaced_job.assert_called_once_with(
            klass.namespace(), ANY
        )

    @patch('bro_restore_trigger.BroImportAndRestoreTrigger')
    def test_main(self, p_bro_restore_trigger):
        p_bro_restore_trigger.return_value = MagicMock(
            name='m_BroRestoreRunner')

        m_import_and_trigger = p_bro_restore_trigger.return_value. \
            import_and_trigger = MagicMock(name='m_import_and_trigger')

        self.assertRaises(SystemExit, main, [])
        main(['-S', '/secrets',
              '-A', 'serviceaccount',
              '-b', 'backup',
              '-j', 'runner_job',
              '-s', 'ROLLBACK',
              '-c', 'cfg_map'
              ])
        m_import_and_trigger.assert_called_once_with(
            'serviceaccount', '/secrets', 'runner_job', 'backup', 'cfg_map',
            'ROLLBACK')
