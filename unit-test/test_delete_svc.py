from unittest.mock import ANY, MagicMock, call, patch

from test_common import BaseTestCase, PATCH_load_incluster_config, \
    PATCH_load_kube_config, KubeApi

from collections import namedtuple

from delete_svc import DeleteService, main

from kubernetes.client import V1Service, V1ObjectMeta, V1ServiceSpec

class TestDeleteService(BaseTestCase):
    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('common.KubeApi.delete_service')
    def test_service_cleanup(self, p_delete_service):
        klass = DeleteService()

        myService = V1Service(metadata=V1ObjectMeta(name='service'), spec=V1ServiceSpec(cluster_ip='service_ip'))
        klass.service_cleanup(myService)
        p_delete_service.assert_called_once_with('service')


    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('common.KubeApi.list_service_details')
    def test_service(self, p_list_service_details):
        klass = DeleteService()
        klass.service('service')
        p_list_service_details.assert_called_once_with('service')


    @patch('delete_svc.DeleteService')
    def test_main_service_cleanup_called(self, p_delete_svc):
        self.assertRaises(SystemExit, main, [])

        p_delete_svc.return_value = MagicMock(
            name='m_DeleteService')
        m_service = MagicMock(name='m_service')
        p_delete_svc.return_value.service = m_service
        m_service_cleanup = MagicMock(name='m_service_cleanup')
        p_delete_svc.return_value.service_cleanup = m_service_cleanup

        main(['-s', 'service'])
        m_service.assert_called_once_with('service')
        m_service_cleanup.assert_called_with(m_service.return_value)
    @patch('delete_svc.DeleteService')
    def test_main_service_cleanup_skipped(self, p_delete_svc):
        self.assertRaises(SystemExit, main, [])

        p_delete_svc.return_value = MagicMock(
            name='m_DeleteService')
        m_service = MagicMock(name='m_service')
        p_delete_svc.return_value.service = m_service
        m_service.return_value = None
        m_service_cleanup = MagicMock(name='m_service_cleanup')
        p_delete_svc.return_value.service_cleanup = m_service_cleanup

        main(['-s', 'service'])
        m_service.assert_called_once_with('service')
        m_service_cleanup.assert_not_called()
