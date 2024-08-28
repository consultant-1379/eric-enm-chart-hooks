'''
Utility functions for test_hook
'''
import re
import urllib.request

from distutils.version import LooseVersion
from html.parser import HTMLParser
from time import sleep, time

from helm3procs import add_helm_repo, helm_get_chart_from_repo, \
    helm_install_chart_from_repo_with_dict
from utilprocs import log


class BurException(Exception):
    '''
    Exception for backup & restore testing.
    '''
    pass  # pylint: disable=unnecessary-pass


class Html2Text(HTMLParser):
    '''
    Extend HTMLParser to parse data into txt attribute
    '''
    def __init__(self, *args, **kwargs):
        self.text = ''
        super().__init__(*args, **kwargs)

    def handle_data(self, data):
        self.text += data

    def error(self, message):
        print(message)
        raise BurException(message)


def get_web_page(url_addr, encoding='utf8'):
    '''
    Retrieve HTML from URL in string format.
    :param url_addr: URL Address of the page
    :param encoding: The encoding of the page
    '''
    url_handler = urllib.request.urlopen(url_addr)
    read_bytes = url_handler.read()
    page_str = read_bytes.decode(encoding)
    url_handler.close()
    return page_str


def get_text_from_html(html):
    '''
    Strip HTML tags from page and return the text.
    :param html: The HTML page in string format.
    '''
    html_handler = Html2Text()
    html_handler.feed(html)
    text = html_handler.text
    return text


def latest_chart_version(repo_url, chart_name):
    '''
    Return the latest chart version from the give URL
    :param repo_url: URL where the charts are hosted
    :param chart_name: Name of the chart
    '''
    log("Entered get chart version")
    page = get_web_page(repo_url)
    log(f'Got HTML from: {repo_url}')
    page_text = get_text_from_html(page)
    version_candidates = []
    log(f'Parsing the following text for chart versions:\n{page_text}')

    for line in page_text.split('\n'):
        line_items = line.split()
        if not line_items:
            continue

        file_name = line_items[0]
        if file_name.startswith(chart_name) and file_name.endswith('tgz'):
            version_candidates.append(file_name)

    version_candidates.sort(key=LooseVersion)
    log(f'Found the following chart candidates: {version_candidates}')
    file_name = version_candidates[-1]
    log(f'Picked following chart candidate: {file_name}')
    version_regex = f'{chart_name}-' + r'((\d{1,2}\.){2}(\d{1,3})-(\d{1,2})).tgz'
    regex_search_result = re.search(version_regex, file_name)
    log(f'Regex search results: {regex_search_result}')
    version = regex_search_result.group(1)
    log(f"Latest version from {file_name} is: {version}")
    return version


def helm_deploy_chart(name,  # pylint: disable=too-many-arguments
                      repo,
                      version,
                      namespace,
                      options=None,
                      debug=False,
                      timeout=120,
                      wait=True):
    """
    Deploy chart
    :param name: Chart name
    :param repo: Repo the chart is stored in
    :param version: Version of chart to use
    :param namespace: Namespace to deploy chart to
    :param options: Options to provide to chart
    :param debug: log the debug info
    :param timeout: Timeout to install chart
    :param wait: If true, then wait for chart to deploy
    """
    release_name = f'{name}-{namespace}'[:53]
    repo_name = f'{name}-repo'

    add_helm_repo(repo, repo_name)
    helm_get_chart_from_repo(name, version, repo_name)

    helm_install_chart_from_repo_with_dict(name,
                                           release_name,
                                           namespace,
                                           helm_repo_name=repo_name,
                                           chart_version=version,
                                           settings_dict=options,
                                           debug_boolean=debug,
                                           timeout=timeout,
                                           should_wait=wait)
    log(f'Deployment of test agent {"completed" if wait else "in progress"}')



def wait_for_agent(agents, bro, timeout=600):
    """
    Wait for agent to register
    :param agents: list of agents to wait for
    :param bro: instance of Bro class
    :param timeout: timeout for agents to register
    """
    log(f"Entered wait_for_agents with registered agents: {bro.status.agents}")
    agents.sort()
    end_time = time() + timeout

    while True:
        if time() > end_time:
            log('Timed out waiting for agents to register')
            raise BurException('Wait for Agent Timeout')

        log("Waiting for brAgent to register with BRO...")
        log(f"Registered agents: {bro.status.agents}")
        registered_agents = sorted(bro.status.agents)
        log(f'We have registered {registered_agents} and expect {agents}')
        if agents == registered_agents:
            log('All agents are now registered')
            return
        log("Not all agents are registered")
        sleep(5)
