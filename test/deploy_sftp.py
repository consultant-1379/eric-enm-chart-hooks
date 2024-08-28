"""
SFTP Deployment Script

This script demonstrates applying a StatefulSet and retrieving the pod IP in a Kubernetes cluster.
It uses the 'kubernetes' library to interact with Kubernetes resources.

Usage:
- Run the script using Python3 and pass namespace as parameters.
"""
import sys
import logging
from kubernetes import client, config
import yaml

# Define Constants
NAMESPACE = sys.argv[1]
SFTP_YAML_FILE_PATH = "test/sftp_statefulset.yaml"
POD_NAME = "bur-sftp-server-0"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_yaml_from_file(sftp_yaml_file_path: str) -> list:
    """
    Load YAML data from SFTP YAML file.

    Args:
        sftp_yaml_file_path (str): Path to the SFTP YAML file.

    Returns:
        list: List of YAML documents.
    """
    with open(sftp_yaml_file_path, 'r', encoding='utf-8') as stream:
        try:
            return list(yaml.safe_load_all(stream))
        except yaml.YAMLError as exc:
            logger.error(f"Error loading YAML: {exc}")
            return None

def apply_secret(sftp_yaml_data: list, namespace: str) -> None:
    """
    Apply SFTP Secret using YAML data.

    Args:
        sftp_yaml_data (list): List of YAML documents.
        namespace (str): Kubernetes namespace.
    """
    config.load_kube_config()
    api_instance = client.CoreV1Api()

    try:
        api_instance.create_namespaced_secret(
            body=sftp_yaml_data[0],  # Use the first document from sftp_statefulset.yaml for Secret
            namespace=namespace,
        )
        logger.info("SFTP Secret created Successfully.")
    except Exception as err:
        logger.error("Exception when creating secrets: %s", err)


def apply_statefulset(sftp_yaml_data: list, namespace: str) -> None:
    """
    Apply SFTP StatefulSet using YAML data.

    Args:
        sftp_yaml_data (list): List of YAML documents.
        namespace (str): Kubernetes namespace.
    """
    config.load_kube_config()
    api_instance = client.AppsV1Api()

    try:
        api_response = api_instance.create_namespaced_stateful_set(
            body=sftp_yaml_data[1],  # Use the second document of sftp_statefulset.yaml for StatefulSet
            namespace=namespace,
        )
        logger.info("SFTP StatefulSet created. Status='%s'", api_response.status)
    except Exception as err:
        logger.error("Exception while creating StatefulSet: %s", err)


def get_pod_ip(pod_name: str, namespace: str) -> str:
    """
    Get the IP address of a pod in a Kubernetes cluster.

    Args:
        pod_name (str): Name of the pod.
        namespace (str): Kubernetes namespace where the pod is located.

    Returns:
        str: IP address of the pod.
    """
    config.load_kube_config()
    api_instance = client.CoreV1Api()

    try:
        pod_ip = api_instance.read_namespaced_pod(pod_name, namespace).status.pod_ip
        return pod_ip
    except Exception as err:
        return None

def main():
    """
    Main function to deploy a StatefulSet and retrieve pod IP in a Kubernetes cluster.
    """
    sftp_yaml_data = load_yaml_from_file(SFTP_YAML_FILE_PATH)

    if sftp_yaml_data:
        apply_secret(sftp_yaml_data, NAMESPACE)
        apply_statefulset(sftp_yaml_data, NAMESPACE)

        # Logic to check the pod IP only once the pod is up
        sftp_pod_ip = None
        while sftp_pod_ip is None:
            sftp_pod_ip = get_pod_ip(POD_NAME, NAMESPACE)

        # Export the SFTP_POD_IP variable for using variable in ruleset2.0.yaml
        if sftp_pod_ip:
            logger.info(f"The IP address of pod '{POD_NAME}' in namespace '{NAMESPACE}' is: {sftp_pod_ip}")
            print(sftp_pod_ip)
            return sftp_pod_ip
        else:
            logger.error("Failed to retrieve pod IP. Check logs for details.")
            return None

if __name__ == "__main__":
    main()
