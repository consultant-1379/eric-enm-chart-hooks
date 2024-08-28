from unittest.mock import MagicMock, call, patch

from delete_secrets import DeleteSecrets, main
from test_common import BaseTestCase, PATCH_load_incluster_config, \
    PATCH_load_kube_config


class TestDeleteSecrets(BaseTestCase):
    @patch('common.load_incluster_config', new=PATCH_load_incluster_config)
    @patch('common.load_kube_config', new=PATCH_load_kube_config)
    @patch('common.KubeApi.delete_secret')
    def test_cleanup_secret(self, p_delete_secret):
        klass = DeleteSecrets()

        klass.cleanup_secrets(["secret1", "secret2"])
        calls = [call("secret1"), call("secret2")]
        p_delete_secret.assert_has_calls(calls)


    @patch('delete_secrets.DeleteSecrets')
    def test_main(self, p_delete_secret):
        p_delete_secret.return_value = MagicMock(
            name='m_DeleteSecrets')
        m_cleanup_secret = p_delete_secret.return_value.cleanup_secrets = \
            MagicMock(name='m_cleanup_secret')

        self.assertRaises(SystemExit, main, [])
        main(['-s', 'secret1', '-s', 'secret2'])
        m_cleanup_secret.assert_called_once_with(['secret1', 'secret2'])

