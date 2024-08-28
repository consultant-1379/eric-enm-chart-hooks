import datetime
import os
import subprocess
import time
from datetime import datetime, timedelta

from helm3procs import helm_delete_release, \
    helm_install_chart_from_repo_with_dict
from kubernetes import client
from kubernetes.client.exceptions import ApiException
from utilprocs import log, execute_command

from bro_test_utils import helm_deploy_chart, wait_for_agent, \
    latest_chart_version, BurException
from lib.broapi import Bro
from common import KubeApi, BroCliBaseClass

SCOPE = 'ROLLBACK'
BACKUP_NAME = 'PreUpgradeBackup'
CONFIG_MAP = "backup-restore-configmap"

SECRET_NAME = 'hook-sftp-secret'
SFTP_PASSWORD = '12shroot'
SFTP_USERNAME = 'brsftp'
SFTP_POD_IP = os.environ["SFTP_POD_IP"]
# SFTP_POD_IP = '192.168.197.209'
SFTP_URI = f'sftp://{SFTP_USERNAME}@{SFTP_POD_IP}:22/bro_test'

os.environ['BRO_HOST'] = 'eric-ctrl-bro'
os.environ['BRO_PORT'] = '7001'
BRO = Bro(host='eric-ctrl-bro', port='7001')
NAMESPACE = os.environ['kubernetes_namespace']
HELM_REPO = os.environ['helm_repo']
CHART_NAME = os.environ['baseline_chart_name']

BASELINE_CHART_VERSION = os.environ['baseline_chart_version']
TEST_AGENT_RELEASE = f'{CHART_NAME}-{NAMESPACE}'[:53]
BRO_AGENT = f'{TEST_AGENT_RELEASE}-bragent'
SIDECAR_AGENT = 'sidecar-agent'
POD_AGENT = 'pod-agent'
AGENTS = [POD_AGENT, SIDECAR_AGENT, BRO_AGENT]


def create_restore_configmap():
    """
    Create an empty configmap for restore purpose
    """
    config_data = {
        "RESTORE_STATE": "",
        "RESTORE_SCOPE": "",
        "RESTORE_BACKUP_NAME": ""
    }
    kubeclass = KubeApi()
    cmap = client.V1ConfigMap()
    cmap.metadata = client.V1ObjectMeta(name=CONFIG_MAP)
    cmap.data = config_data
    try:
        kubeclass.create_configmap(cmap)
        log(f"Successfully created {CONFIG_MAP}.\n")
    except ApiException as api_exc:
        log(f"Exception: {api_exc}.\n")


def create_service_account():
    """
    Create a service account to provide permissions to
    "create", "get", "list", "patch" and "delete" jobs, configmaps and pods
    """
    service_account = client.V1ServiceAccount(
        api_version="v1",
        kind="ServiceAccount",
        metadata=client.V1ObjectMeta(name="hook-restore-sa"),
    )
    role = client.V1Role(
        metadata=client.V1ObjectMeta(name="hook-restore-role"),
        rules=[
            client.V1PolicyRule(
                api_groups=[""], resources=["configmaps", "pods"],
                verbs=["get", "list", "patch", "delete"]
            ),
            client.V1PolicyRule(
                api_groups=["batch"], resources=["jobs"],
                verbs=["create", "list", "delete"]
            )
        ],
    )
    role_binding = client.V1RoleBinding(
        metadata=client.V1ObjectMeta(name="hook-binding"),
        subjects=[client.V1Subject(kind="ServiceAccount",
                                   name="hook-restore-sa")],
        role_ref=client.V1RoleRef(api_group="rbac.authorization.k8s.io",
                                  kind="Role", name="hook-restore-role"),
    )
    try:
        v1_core_api = client.CoreV1Api()
        v1_core_api.create_namespaced_service_account(
            NAMESPACE, service_account)
        api_instance = client.RbacAuthorizationV1Api()
        api_instance.create_namespaced_role(NAMESPACE, role)
        api_instance.create_namespaced_role_binding(NAMESPACE, role_binding)
        log("Service account created successfully.\n")
    except ApiException as err:
        print(f"Error creating service account : {err}.\n")


def create_secret():
    """
    Create sftp secret with URI and password
    """
    try:
        local_execute_command("kubectl create secret "
                              f"generic {SECRET_NAME} "
                              "--from-literal=externalStorageURI="
                              f"{SFTP_URI} "
                              "--from-literal=externalStorageCredentials="
                              f"'{SFTP_PASSWORD}' -n {NAMESPACE}")
    except ValueError as err:
        log(f"Failed to create secret: {err}.\n")
    else:
        log(f"Successfully Created SFTP Secret {SECRET_NAME}.\n")


def create_sftp_config_file():
    """
    Save the SFTP externalStorageURI and externalStorageCredentials
    to file which will be by bro_restore_trigger.py
    to import the backup from SFTP Server
    """
    try:
        external_storage_uri = "/test/externalStorageURI"
        external_storage_credentials = "/test/externalStorageCredentials"

        with open(external_storage_uri, 'w',
                  encoding='utf-8') as uri_file:
            uri_file.write(SFTP_URI)

        with open(external_storage_credentials, 'w',
                  encoding='utf-8') as credentials_file:
            credentials_file.write(SFTP_PASSWORD)
    except FileNotFoundError as err:
        log(f"Error to write SFTP config to file: {err}.\n")
    else:
        log("SFTP config files created successfully.\n")


def get_pod(pod_prefix):
    """
    Retrieve a list of pod names in
    a Kubernetes namespace based on a prefix.
    :param pod_prefix:
    :return:
        string: Matched pod names.
        list: An empty list.
    """
    v1_core_api = client.CoreV1Api()
    try:
        pod_list = v1_core_api.list_namespaced_pod(NAMESPACE)
    except client.rest.ApiException as err:
        raise ValueError("Error communicating with "
                         f"Kubernetes API: {err}.") from err
    matching_pods = [
        pod.metadata.name
        for pod in pod_list.items
        if pod.metadata.name.startswith(pod_prefix)
    ]
    if matching_pods:
        log(f"The matching pod name: {matching_pods[0]}.")
    else:
        log(f"No matching pods found with prefix: {pod_prefix}.")
        return []
    return matching_pods[0]


def set_upgrade_state(state):
    """
    Execute the command base on the input to
    set the uprade_state to either partial or full
    :param state: String partial or ''
    :return
        string: The actual upgrade state.
    """
    try:
        local_execute_command(f"python3 /src/upgrade_state.py --{state}")
        kube_class = KubeApi()
        upgrade_state_cmap = kube_class.get_configmap('upgrade-state')
        actual_state = upgrade_state_cmap.data['Upgrade-State']
    except ValueError as error:
        print(error)
    return actual_state


def set_schedule_control(input_option):
    """
    Execute the command base on the input to
    disable or enable the schedule.
    :param input_option: string disabled or enabled
    :return
        boolean: The state of schedule control.
    """
    schedule_enable = None
    try:
        local_execute_command("python3 /src/bro_schedule_control.py"
                              f" --{input_option}")
        schedule_enable = BRO.get_schedule().enabled
    except ValueError as err:
        print(f"Failed to {input_option} schedule with error {err}.")
    return schedule_enable


def restore_runner_check():
    """
    Checks the status of the executor pod responsible for restoring a backup.
    It logs the progress and raises an assertion error if the pod does not
    reach the 'Succeeded' state within a specified number of attempts.
    """
    log("Running executor job to restore the backup...")
    max_attempts = 5
    attempts = 0
    time.sleep(5)
    pod_phase = ''
    while attempts < max_attempts:
        try:
            executor_pod = get_pod("eric-enm-bro-restore-executor-job-")
            if not executor_pod:
                command_output = local_execute_command(
                    "kubectl describe jobs/"
                    "eric-enm-bro-restore-executor-job "
                    "-n hook-test-ns")
                log(f"The restore job is not running {command_output}.")
                break
            v1_core_api = client.CoreV1Api()
            pod_info = v1_core_api.read_namespaced_pod_status(
                executor_pod, NAMESPACE)
            pod_phase = pod_info.status.phase
            if pod_phase in ('Failed', 'Succeeded'):
                break
        except ApiException as err:
            log(f"Exception when reading pod status: {err}.")
        attempts += 1
        log(f"Restore status: {pod_phase}")
        time.sleep(5)
    assert pod_phase == "Succeeded", \
        ('Restore Executor job status is not "Succeeded". '
         f'Actual status: "{pod_phase}".')


def restore_process(scope, backup_name):
    """
    Restore process that Uninstall the test chart and re-install
    the Helm chart with restore state.
    The restore process are performe by running delete_hook_jobs.py
    :param scope: (str): The scope from which to get the backup
    :param backup_name: (str): The name of the backup to restore.
    :return
        string: Extracted word from the response.
    """
    response = ''
    log("=======Deleting BrAgent Test Chart=======")
    helm_delete_release(TEST_AGENT_RELEASE, NAMESPACE, timeout=300)
    time.sleep(5)
    log("Test Chart is Deleted ...\n")
    # Deploy Test Chart in restore mode
    log("============Deploying Test Chart in restore mode==============")
    baseline_version = os.environ['baseline_chart_version']

    restore_options = {"backupRestore.restoreState": "ongoing",
                       "backupRestore.backupName": backup_name,
                       "backupRestore.restoreScope": scope,
                       "brAgent.backupTypeList[0]": "ROLLBACK"}
    log(f"restore options: {restore_options}")
    helm_install_chart_from_repo_with_dict(
        CHART_NAME,
        f'{CHART_NAME}-{NAMESPACE}'[:53],
        NAMESPACE,
        helm_repo_name=f'{CHART_NAME}-repo',
        chart_version=baseline_version,
        settings_dict=restore_options,
        debug_boolean=False,
        timeout=120,
        should_wait=False
    )
    try:
        restore_command = ("python3 /src/bro_restore_trigger.py "
                           "-A hook-restore-sa "
                           "-S /test -j eric-enm-bro-restore-executor-job "
                           f"-b {backup_name} -s {scope} "
                           f"-c backup-restore-configmap")
        response = local_execute_command(restore_command)
    except ValueError as error:
        print(f"Failed to run restore trigger with error: {error}.")

    extracted_result = extract_command_output(response, "Triggered")
    return extracted_result


def local_execute_command(command):
    """
    Executes commands
    :param command: Command to be executed
    :return:
        str: response of executed command.
    """
    print('Executing Command: ' + '"' + command + '"')
    try:
        response = subprocess.run(
            command,
            shell=True,
            check=True,
            universal_newlines=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return response.stdout
    except subprocess.CalledProcessError as error:
        print(f"\n{error.stderr}")
        raise ValueError('\nThere was an error while trying '
                         f'to execute the command "{command}" '
                         f'\n {error.output}.') from error


def run_backup_manager_config(backupname="-", scope="-",
                              schedule=None, retention=None):
    """
    Configure the Backup Manager using the 'bro_bm_config.py' script.
    with the specified parameters
    :param backupname: (str, optional):
    The name of the backup. Defaults to "-".
    :param scope:  scope (str, optional):
    The scope for the backup. Defaults to "-".
    :param schedule: (str, optional):
    The schedule info contain config and interval. Defaults to None.
    :param retention: (str, optional):
    The retention information for the housekeeping. Defaults to None.
    :return
        string: Response of command execution.
    """
    # use execute command in test framework
    config_map = "backup-restore-configmap"
    command = (f"python3 /src/bro_bm_config.py "
               f"-b {backupname} "
               f"-s {scope} "
               f"-S {SECRET_NAME} "
               f"-c {config_map} "
               f"-V {schedule} "
               f"-R {retention}")
    try:
        return local_execute_command(command)
    except ValueError as err:  # pylint: disable=broad-except
        print(f'Exception found in create bro config - {err}.')
        return ''


def check_last_created_backup():
    """
    This function queries BRO to get the schedule information
    and checks if there is a recently created backup.
    If the maximum number of attempts is reached without
    success an error is raised.
    :return:
        str: The name of the last backup created by BRO Scheduler.
    """
    log("Check if the backup is created")
    max_attempts = 6
    attempts = 0
    while attempts < max_attempts:
        try:
            schedule = BRO.get_schedule("DEFAULT")
            if schedule.recent_created:
                print(f"This is the last backup created by BRO Scheduler \
                {schedule.recent_created}.")
                return schedule.recent_created
            print("BRO Scheduler hasn't created any backups yet.")
            time.sleep(5)
            attempts += 1
        except ApiException as api_exception:
            print(f"Exception when reading pod status: {api_exception}.")
    assert attempts < max_attempts, ("Max attempts reached "
                                     "without success Backup created.")


def generate_restore_report(scope):
    """
    Generate the report for restore action.
    :param scope: Scope the Backup been restored.
    :return
        string: Extracted word of the response.
    """
    try:
        response = local_execute_command(
            "python3 /src/bro_restore_report.py "
            f"-c {CONFIG_MAP} -s {scope}"
        )
        result_output = extract_command_output(response, 'Result:')
    except ValueError as err:
        log(f"Failed with error {err}.")
    return result_output


def deploy_required_resources():
    """
        The deployment of required resources for the restore process.
    """
    log('============== Deploying required resources ==========')
    create_restore_configmap()
    create_service_account()
    create_secret()
    create_sftp_config_file()


def extract_command_output(command_output, regex_word):
    """
    Return the except result after the input regex word
    :param command_output:
    :param regex_word:
    :return:
        str: Extracted word after regex word
    """
    for line in command_output.split('\n'):
        try:
            start_index = line.find(regex_word)
            if start_index != -1:
                # Extract the substring starting just after regex_word
                substring = line[start_index + len(regex_word):].strip()
                # Split the substring by space to get the next word
                parts = substring.split(' ', 1)
                if parts:
                    result_value = parts[0]
                    print(f"Extracted Text: {result_value}.")
                    return result_value
        except Exception as index_exception:  # pylint: disable=broad-except
            print(f"Error to filter the texts {index_exception}.")
    return None


# The test case start from here
def test_set_state_partial():
    print('\n======================================\n')
    actual_state = set_upgrade_state("partial")
    assert actual_state == "Partial", \
        (f"Failed to set Upgrade-State to partial"
         f" the actual state is {actual_state}.")
    log("Successfully set upgrade state to partial.")



def test_set_state_full():
    print('\n======================================\n')
    actual_state = set_upgrade_state("full")
    assert actual_state == "", ("Failed to set Upgrade-State to full, "
                                f"the actual state is {actual_state}.")
    log("Successfully set upgrade state to full.")

def test_bro_partial_rollback():
    print('\n======================================\n')
    kube_class = KubeApi()
    try:
        kube_class.delete_configmap("upgrade-state")
        response = local_execute_command("python3 "
                                         "/src/bro_partial_rollback.py")
        schedule_enable = BRO.get_schedule().enabled
        upgrade_state_cmap = kube_class.get_configmap('upgrade-state')
        actual_state = upgrade_state_cmap.data['Upgrade-State']
    except Exception as err: # pylint: disable=broad-except
        assert False, f"Unexpected exception error : {err} "
    assert actual_state == "Partial", \
        ("Failed to create a configmap {upgrade-state}"
         "with the value 'Partial',"
         f" the actual state is {actual_state}.")
    assert schedule_enable is True, \
        ("Failed to enable schedule "
         f"with error {response}.")
    log("Successfully created a new ConfigMap upgrade-state "
        "and enabled the schedule.")
def test_disable_schedule():
    print('\n======================================\n')
    response = set_schedule_control("disabled")
    assert response is False, \
        (f"Failed to disable schedule, "
         f"the actual state is {response}.")
    log("Successfully disabled the schedule.")


def test_create_preupgrade_backup():
    print('\n======================================\n')
    backups_list = []
    try:
        log("Create a pre-upgrade backup")
        local_execute_command(f"python3 /src/bro_pre_upgrade_backup_trigger.py"
                              f" -b {BACKUP_NAME} ")
    except ValueError as err:  # pylint: disable=broad-except
        print(f' {err}')
    else:
        i = 0
        while i < 6:
            time.sleep(5)
            backups_list = BRO.backups(SCOPE)
            if len(backups_list) > 0:
                break
            i += 1
    assert len(backups_list) > 0, \
        'Failed to create a backup in time.'
    backup = backups_list[0]
    assert backup.id == 'PreUpgradeBackup', \
        (f"Backup name '{backup.id}' does not "
         "match expected backup name 'PreUpgradeBackup'.")
    assert backup.status == 'COMPLETE', \
        ("Backup status is not COMPLETE; "
         f"the actual status is: {backup.status}.")
    log("Pre-upgrade Backup created successfully.")


def test_rollback_restore():
    print('\n======================================\n')
    deploy_required_resources()
    log("Running Rollback Restore Process ...")
    restore_result = restore_process("ROLLBACK", BACKUP_NAME)
    assert restore_result == 'restore', \
        ("Restore executor job was not triggered successfully. "
         f"Actual command response '{restore_result}' "
         "does not match expected response 'restore'.")
    log(f'Restoring backup: {BACKUP_NAME}, in scope ROLLBACK.')
    restore_runner_check()


def test_generate_rollback_report():
    print('\n======================================\n')
    result_output = generate_restore_report(scope="ROLLBACK")
    assert result_output == 'SUCCESS', \
        (f"Actual bro_restore_report.py response '{result_output}' "
         "does not match expected response 'SUCCESS'.")
    log("Successfully generated report for ROLLBACK restore.")


def test_enable_schedule():
    print('\n======================================\n')
    out_put = set_schedule_control("enabled")
    assert out_put is True, \
        ("Failed to enable schedule, "
         f"the actual state is {out_put}.")
    log("Successfully enabled the schedule.")


def test_set_config():
    print('\n======================================\n')
    current_time = datetime.now()
    start_time = (current_time + timedelta(seconds=10)
                  ).strftime("%Y-%m-%dT%H:%M:%S")
    stop_time = (current_time + timedelta(seconds=50)
                 ).strftime("%Y-%m-%dT%H:%M:%S")
    schedule = None
    schedule_interval = None
    retention = None
    schedule_info = (
        f"'{{"
        f'"backupPrefix":"SCHEDULED_BACKUP",'
        f'"schedules":[{{'
        f'"every":"1m",'
        f'"start":"{start_time}",'
        f'"stop":"{stop_time}"'
        f'}}]'
        f"}}'"
    )
    retention_info = '\'{"autoDelete":true,"limit":2}\''
    try:
        run_backup_manager_config(
            None, None, schedule_info, retention_info)
    except Exception as err:  # pylint: disable=broad-except
        print(f'Exception found in create bro config - {err}.')
    else:
        try:
            time.sleep(10)
            schedule = BRO.get_schedule("DEFAULT")
            retention = BRO.get_retention("DEFAULT")
            if schedule.intervals:
                log(f"This is the interval {schedule.intervals[0]}.")
                schedule_interval = schedule.intervals
        except BurException as bur_exception:
            print("Exception when reading the interval schedule:"
                  f" {bur_exception}.")
    assert len(schedule_interval) > 0, \
        "No schedule had been created."
    assert retention.limit == 2, \
        (f"The Retention limit '{retention.limit}' "
         "does not match expected limit '2'.")
    assert retention.purge is True, \
        "The Retention purge is not set to True."
    log("Schedule and Retention configured successfully.")


def test_delete_hook_job():
    print('\n======================================\n')
    try:
        local_execute_command("python3 /src/delete_hook_jobs.py "
                              "-j eric-enm-bro-restore-executor-job")
        pod_name_list = get_pod("eric-enm-bro-restore-executor-job-")
    except ValueError as err:
        print(f"failed with err{err}.")
    assert not pod_name_list, \
        "Executor job has not been deleted."
    log("Successfully deleted job eric-enm-bro-restore-executor-job.")


def test_full_restore():
    print('\n======================================\n')
    backup_name = check_last_created_backup()
    bro_class = BroCliBaseClass()
    action = BRO.status.action

    if action:
        log(f"Waiting for Action {action.name} to be complete")
        bro_class.wait_for_action(action)
    log("Cleaning up the PVC for External Restore")
    assert bro_class.exists(backup_name, "DEFAULT"), \
        f"Backup '{backup_name}' does not exist."
    BRO.delete(backup_name, "DEFAULT")
    time.sleep(5)

    backup_filename = f'{backup_name}.tar.gz'
    log(f"Running full backup restore from"
        f" external with {backup_filename}")
    restore_result = restore_process("DEFAULT", backup_filename)
    assert restore_result == 'restore', \
        ("Restore executor job was not triggered successfully. "
         f"Actual command response '{restore_result}' "
         "does not match expected response 'restore'.")
    log(f'Restoring backup: {BACKUP_NAME}, in scope DEFAULT.')
    restore_runner_check()


def test_generate_full_restore_report():
    print('\n======================================\n')
    result_output = generate_restore_report(scope="DEFAULT")
    assert result_output == 'SUCCESS', \
        (f"Actual bro_restore_report.py response '{result_output}' "
         "does not match expected response 'SUCCESS'.")
    log("Successfully generated report for DEFAULT restore.")


def test_restore_config():
    print('\n======================================\n')
    backup_name = check_last_created_backup()
    log(f"Restore the BM config from backup {backup_name}.")
    try:
        command_output = run_backup_manager_config(backup_name, "DEFAULT")
    except ValueError as err:  # pylint: disable=broad-except
        print(f'Exception found in restore bro config - {err}')
    test_result = extract_command_output(command_output, 'Result:')
    assert test_result == 'SUCCESS', \
        ("Failed to restore BM config. "
         f"Command response '{test_result}' "
         "doesn't match expected "
         "response 'SUCCESS'.")
    log("Successfully restored BM configuration.")


def setup():
    """
    Setup function for nostests, deploys the helm chart specified by the OS
    var, baseline_chart_name, then waits for the agents to register.
    """
    global BASELINE_CHART_VERSION  # pylint: disable=global-statement
    if BASELINE_CHART_VERSION == 'latest':
        log('Looking up latest chart version')
        try:
            BASELINE_CHART_VERSION = latest_chart_version(
                f'{HELM_REPO}backup-restore-agent/{CHART_NAME}',
                CHART_NAME)
            os.environ['baseline_chart_version'] = BASELINE_CHART_VERSION
        except Exception as err:  # pylint: disable=broad-except
            log(f'Failed to determine latest chart version: {err}.')
            raise
    log(f'Test setup using chart version: {BASELINE_CHART_VERSION}.')
    try:
        helm_deploy_chart(name=CHART_NAME,
                          repo=HELM_REPO,
                          version=BASELINE_CHART_VERSION,
                          options={"brAgent.backupTypeList[0]": "ROLLBACK"},
                          namespace=NAMESPACE)
        wait_for_agent(AGENTS, BRO)
        log("Set up is finished. \n")
    except Exception as err:  # pylint: disable=broad-except
        log(f'Exception during setup: {err}.')
        teardown()
        raise


def teardown():
    """
    Delete the helm chart release in the namespace.
    """
    log('Removing Test Agent helm releases in namespace')
    name = execute_command(f'helm ls --all --namespace={NAMESPACE} '
                           f'-q --filter {TEST_AGENT_RELEASE}')
    name = name.replace('\n', ' ').strip()

    if name:
        log(f'Deleting {name}')
        helm_delete_release(TEST_AGENT_RELEASE, NAMESPACE, timeout=300)
    else:
        log(f'{TEST_AGENT_RELEASE} does not exist.')
    log('Teardown complete.')
