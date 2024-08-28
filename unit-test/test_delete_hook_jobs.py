from unittest.mock import ANY, MagicMock, call, patch

from kubernetes.client import V1Job, V1JobList, V1ObjectMeta

from delete_hook_jobs import DeleteHookJobs, main
from test_common import BaseTestCase, PATCH_load_incluster_config, \
    PATCH_load_kube_config


class TestDeletePreInstallHookJob(BaseTestCase):
    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    def test_hook_cleanup(self):
        klass = DeleteHookJobs()

        job1 = V1Job(metadata=V1ObjectMeta(name='j1'))
        job2 = V1Job(metadata=V1ObjectMeta(name='j2'))

        klass.api_batch = MagicMock(name='m_api_batch')
        klass.api_batch.return_value.list_namespaced_job.side_effect = [
            V1JobList(items=[job1, job2])
        ]

        klass.hook_cleanup(['some_job'])

        klass.api_batch.return_value.list_namespaced_job.side_effect = [
            V1JobList(items=[job1, job2]),
            V1JobList(items=[job1])
        ]
        klass.hook_cleanup(['j2'])

        klass.api_batch.assert_has_calls(
            [call().delete_namespaced_job('j2', klass.namespace(), body=ANY)])

    @patch('delete_hook_jobs.DeleteHookJobs')
    def test_main(self, p_delete_hook):
        p_delete_hook.return_value = MagicMock(
            name='m_DeleteHookJobs')
        m_hook_cleanup = p_delete_hook.return_value.hook_cleanup = \
            MagicMock(name='m_hook_cleanup')

        self.assertRaises(SystemExit, main, [])
        main(['-j', 'j1', '-j', 'j2'])
        m_hook_cleanup.assert_called_once_with(['j1', 'j2'])
