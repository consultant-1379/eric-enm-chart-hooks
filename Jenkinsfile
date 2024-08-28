#!/usr/bin/env groovy

/* IMPORTANT:
 *
 * In order to make this pipeline work, the following configuration on Jenkins is required:
 * - slave with a specific label (see pipeline.agent.label below)
 * - credentials plugin should be installed and have the secrets with the following names:
 *   + lciadm100credentials (token to access Artifactory)
 */


def defaultBobImage = 'armdocker.rnd.ericsson.se/proj-adp-cicd-drop/bob.2.0:1.7.0-38'
def bob = new BobCommand()
        .bobImage(defaultBobImage)
        .envVars([ISO_VERSION: '${ISO_VERSION}'])
        .needDockerSocket(true)
        .toString()
def GIT_COMMITTER_NAME = 'lciadm100'
def GIT_COMMITTER_EMAIL = 'lciadm100@ericsson.com'
def lastStage = ''
pipeline {
    agent {
        label 'Cloud_Native_Dev'
    }
    parameters {
        string(name: 'ISO_VERSION', description: 'The ENM ISO version (e.g. 1.65.77)')
        string(name: 'SPRINT_TAG', description: 'Tag for GIT tagging the repository after build')

    }
    stages {
        stage('Inject Credential Files') {
            steps {
                script {
                    lastStage = env.STAGE_NAME
                }
                withCredentials([file(credentialsId: 'lciadm100-docker-auth', variable: 'dockerConfig')]) {
                    sh "install -m 600 ${dockerConfig} ${HOME}/.docker/config.json"
                }
            }
        }
        stage('Checkout Cloud-Native SG Git Repository') {
            steps {
                script {
                    lastStage = env.STAGE_NAME
                }
                git branch: 'master',
                        url: 'ssh://gerrit-gamma.gic.ericsson.se:29418/OSS/ENM-Parent/SQ-Gate/com.ericsson.oss.containerisation/eric-enm-chart-hooks'
            }
        }

        /* WORKAROUND:
         *
         * To avoid '.dirty' version generation:
         *  - Force remove submodule directories
         *  - Run 'git checkout -- .' to discard any local changes
         * Note: The 'git clean -xdff' command usually fails to remove pycache and some other files.
         */
        stage('Submodules') {
            steps {
                script {
                    lastStage = env.STAGE_NAME
                }
                sh 'git status'
                sh 'sudo rm -rf bob/ testframework/ test/bur_cli/'
                sh 'git checkout -- .'
                sh 'git status'
                sh 'git submodule sync'
                sh 'git submodule update --init --force'
            }
        }

        stage('Linting') {
            steps {
                parallel(
                        "python-lint": {
                            sh "${bob} lint:python-lint"
                        },
                        "dockerfile-lint": {
                            sh "${bob} lint:dockerfile-lint"
                        }
                )
            }
            post {
                failure {
                    script {
                        lastStage = env.STAGE_NAME
                    }
                }
            }
        }

        stage('Run unit tests') {
            steps {
                script {
                    lastStage = env.STAGE_NAME
                }
                sh "${bob} unit-tests"
            }
            post {
                always {
                    archiveArtifacts 'cover/*.html'
                    archiveArtifacts 'cover/coverage_html.js'
                    archiveArtifacts 'cover/style.css'
                }
            }
        }

        stage('Init') {
            steps {
                script {
                    lastStage = env.STAGE_NAME
                }
                sh 'git status'
                sh "${bob} init-precodereview"
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    lastStage = env.STAGE_NAME
                }
                sh "${bob} build-image"
            }
            post {
                failure {
                    script {
                        sh "${bob} remove-image-with-all-tags"
                    }
                }
            }
        }

        stage('Publish Images to Artifactory') {
            steps {
                script {
                    lastStage = env.STAGE_NAME
                }
                sh "${bob} push-image-with-all-tags"
            }
            post {
                failure {
                    script {
                        sh "${bob} remove-image-with-all-tags"
                    }
                }
                always {
                    sh "${bob} remove-image-with-all-tags"
                }
            }
        }

        stage('Tag Cloud-Native SG Git Repository') {
            steps {
                script {
                    lastStage = env.STAGE_NAME
                }
                wrap([$class: 'BuildUser']) {
                    script {
                        def bobWithCommitterInfo = new BobCommand()
                                .bobImage(defaultBobImage)
                                .needDockerSocket(true)
                                .envVars([
                                        'AUTHOR_NAME'        : "\${BUILD_USER:-${GIT_COMMITTER_NAME}}",
                                        'AUTHOR_EMAIL'       : "\${BUILD_USER_EMAIL:-${GIT_COMMITTER_EMAIL}}",
                                        'GIT_COMMITTER_NAME' : "${GIT_COMMITTER_NAME}",
                                        'GIT_COMMITTER_EMAIL': "${GIT_COMMITTER_EMAIL}"
                                ])
                                .toString()
                        sh "${bobWithCommitterInfo} create-git-tag"
                        sh """
                            tag_id=\$(cat .bob/var.version)
                            git push origin \${tag_id}
                        """
                    }
                }
            }
            post {
                always {
                    script {
                        sh "${bob} remove-git-tag"
                    }
                }
            }
        }
        stage('Bump Version') {
            steps {
                script {
                    lastStage = env.STAGE_NAME
                    sh 'hostname'
                    Version = readFile "VERSION_PREFIX"
                    sh 'docker run --rm -v $PWD/VERSION_PREFIX:/app/VERSION -w /app armdocker.rnd.ericsson.se/proj-enm/bump patch'
                    newVersion = readFile "VERSION_PREFIX"
                    env.IMAGE_VERSION = newVersion
                    currentBuild.displayName = "${BUILD_NUMBER} - Version - " + Version
                    sh '''
                        git add VERSION_PREFIX
                        git commit -m "Version $IMAGE_VERSION"
                        git push origin HEAD:master
                    '''
                }
            }
        }

        stage('Checkout Git Repositories to Update') {
            parallel {
                stage("Checkout 'eric-enm-bro-integration' Git Repository") {
                    steps {
                        dir('eric-enm-bro-integration') {
                            git branch: 'master',
                                url: 'ssh://gerrit-gamma.gic.ericsson.se:29418/OSS/com.ericsson.oss.containerisation/eric-enm-bro-integration'
                        }
                    }
                    post {
                        failure {
                            script {
                                lastStage = env.STAGE_NAME
                            }
                        }
                    }
                }
                stage("Checkout 'eric-enm-infra-integration' Git Repository") {
                    steps {
                        dir('eric-enm-infra-integration') {
                            git branch: 'master',
                                url: 'ssh://gerrit-gamma.gic.ericsson.se:29418/OSS/com.ericsson.oss.containerisation/eric-enm-infra-integration'
                        }
                    }
                    post {
                        failure {
                            script {
                                lastStage = env.STAGE_NAME
                            }
                        }
                    }
                }
                stage("Checkout 'eric-enm-stateless-integration' Git Repository") {
                    steps {
                        dir('eric-enm-stateless-integration') {
                            git branch: 'master',
                                url: 'ssh://gerrit-gamma.gic.ericsson.se:29418/OSS/com.ericsson.oss.containerisation/eric-enm-stateless-integration'
                        }
                    }
                    post {
                        failure {
                            script {
                                lastStage = env.STAGE_NAME
                            }
                        }
                    }
                }
            }
            post {
                success {
                    script {
                        env.IMAGE_TAG = readFile ".bob/var.version"
                        env.COMMIT_MESSAGE = "NO-JIRA Update 'eric-enm-chart-hooks' version to ${env.IMAGE_TAG}"
                    }
                }
            }
        }

        stage("Update 'eric-enm-chart-hooks' Version in Checked Out Git Repositories") {
            parallel {
                stage("Update 'eric-enm-bro-integration' Git Repository") {
                    steps {
                        script {
                            withCredentials([usernamePassword(credentialsId: 'FUser_gerrit_http_username_password',
                                    usernameVariable: 'GERRIT_USERNAME',
                                    passwordVariable: 'GERRIT_PASSWORD')]) {
                                def bobWithCommitMessage = new BobCommand()
                                        .bobImage(defaultBobImage)
                                        .needDockerSocket(true)
                                        .envVars([
                                                'GERRIT_USERNAME': env.GERRIT_USERNAME,
                                                'GERRIT_PASSWORD': env.GERRIT_PASSWORD,
                                                'COMMIT_MESSAGE': env.COMMIT_MESSAGE
                                        ])
                                        .toString()
                                sh "${bobWithCommitMessage} update-chart-hooks-version-in-repos:update-bro-integration-repo"
                            }
                            GERRIT_BRO_REPO = 'OSS/com.ericsson.oss.containerisation/eric-enm-bro-integration'
                            env.BRO_GERRIT_URL = sh(returnStdout: true, script: "ssh -p 29418 gerrit-gamma.gic.ericsson.se gerrit query project:${GERRIT_BRO_REPO} message:'NO-JIRA ${env.IMAGE_TAG}' | awk '/url:/{print \$2}'").trim().readLines()[0]
                            echo env.BRO_GERRIT_URL
                            GERRIT_CHANGE_ID = sh(returnStdout: true, script: "ssh -p 29418 gerrit-gamma.gic.ericsson.se gerrit query project:${GERRIT_BRO_REPO} message:'NO-JIRA ${env.IMAGE_TAG}' | awk '/id:/{print \$2}'").trim().readLines()[0]
                            echo GERRIT_CHANGE_ID
                            sh "ssh -p 29418 gerrit-gamma.gic.ericsson.se gerrit set-reviewers --project ${GERRIT_BRO_REPO} --add Vandals_review ${GERRIT_CHANGE_ID}"
                        }
                    }
                    post {
                        success {
                            mail to: "PDLVANDALS@pdl.internal.ericsson.com",
                            from: "${env.JOB_NAME}@ericsson.com",
                            subject: "${env.COMMIT_MESSAGE}",
                            body: "Hi Team Vandals,<br><br>" +
                                "Code review has been created in " +
                                "<a href='https://gerrit-gamma.gic.ericsson.se/#/q/project:OSS/com.ericsson.oss.containerisation/eric-enm-bro-integration'>eric-enm-bro-integration</a> repo for automated " +
                                "<b>eric-enm-chart-hooks</b> Image uplift to version <b>${env.IMAGE_TAG}</b>." +
                                "<br>This change has been triggered automatically by code merge in " +
                                "<a href='https://gerrit-gamma.gic.ericsson.se/#/q/project:OSS/ENM-Parent/SQ-Gate/com.ericsson.oss.containerisation/eric-enm-chart-hooks'>eric-enm-chart-hooks</a> repo." +
                                "<br><br>Please review the commit: ${env.BRO_GERRIT_URL}" +
                                "<br><br>Thank you,<br>'<i>${env.JOB_NAME}</i>' Jenkins job",
                            mimeType: 'text/html'
                        }
                        failure {
                            script {
                                lastStage = env.STAGE_NAME
                            }
                        }
                    }
                }
                stage("Update 'eric-enm-infra-integration' Git Repository") {
                    steps {
                        script {
                            withCredentials([usernamePassword(credentialsId: 'FUser_gerrit_http_username_password',
                                    usernameVariable: 'GERRIT_USERNAME',
                                    passwordVariable: 'GERRIT_PASSWORD')]) {
                                def bobWithCommitMessage = new BobCommand()
                                        .bobImage(defaultBobImage)
                                        .needDockerSocket(true)
                                        .envVars([
                                                'GERRIT_USERNAME': env.GERRIT_USERNAME,
                                                'GERRIT_PASSWORD': env.GERRIT_PASSWORD,
                                                'COMMIT_MESSAGE': env.COMMIT_MESSAGE
                                        ])
                                        .toString()
                                sh "${bobWithCommitMessage} update-chart-hooks-version-in-repos:update-infra-integration-repo"
                            }
                            GERRIT_INFRA_REPO = 'OSS/com.ericsson.oss.containerisation/eric-enm-infra-integration'
                            env.INFRA_GERRIT_URL = sh(returnStdout: true, script: "ssh -p 29418 gerrit-gamma.gic.ericsson.se gerrit query project:${GERRIT_INFRA_REPO} message:'NO-JIRA ${env.IMAGE_TAG}' | awk '/url:/{print \$2}'").trim().readLines()[0]
                            echo env.INFRA_GERRIT_URL
                            GERRIT_CHANGE_ID = sh(returnStdout: true, script: "ssh -p 29418 gerrit-gamma.gic.ericsson.se gerrit query project:${GERRIT_INFRA_REPO} message:'NO-JIRA ${env.IMAGE_TAG}' | awk '/id:/{print \$2}'").trim().readLines()[0]
                            echo GERRIT_CHANGE_ID
                            sh "ssh -p 29418 gerrit-gamma.gic.ericsson.se gerrit set-reviewers --project ${GERRIT_INFRA_REPO} --add Vandals_review ${GERRIT_CHANGE_ID}"
                        }
                    }
                    post {
                        success {
                            mail to: "PDLVANDALS@pdl.internal.ericsson.com",
                            from: "${env.JOB_NAME}@ericsson.com",
                            subject: "${env.COMMIT_MESSAGE}",
                            body: "Hi Team Vandals,<br><br>" +
                                "Code review has been created in " +
                                "<a href='https://gerrit-gamma.gic.ericsson.se/#/q/project:OSS/com.ericsson.oss.containerisation/eric-enm-infra-integration'>eric-enm-infra-integration</a> repo for automated " +
                                "<b>eric-enm-chart-hooks</b> Image uplift to version <b>${env.IMAGE_TAG}</b>." +
                                "<br>This change has been triggered automatically by code merge in " +
                                "<a href='https://gerrit-gamma.gic.ericsson.se/#/q/project:OSS/ENM-Parent/SQ-Gate/com.ericsson.oss.containerisation/eric-enm-chart-hooks'>eric-enm-chart-hooks</a> repo." +
                                "<br><br>Please review the commit: ${env.INFRA_GERRIT_URL}" +
                                "<br><br>Thank you,<br>'<i>${env.JOB_NAME}</i>' Jenkins job",
                            mimeType: 'text/html'
                        }
                        failure {
                            script {
                                lastStage = env.STAGE_NAME
                            }
                        }
                    }
                }
                stage("Update 'eric-enm-stateless-integration' Git Repository") {
                    steps {
                        script {
                            withCredentials([usernamePassword(credentialsId: 'FUser_gerrit_http_username_password',
                                    usernameVariable: 'GERRIT_USERNAME',
                                    passwordVariable: 'GERRIT_PASSWORD')]) {
                                def bobWithCommitMessage = new BobCommand()
                                        .bobImage(defaultBobImage)
                                        .needDockerSocket(true)
                                        .envVars([
                                                'GERRIT_USERNAME': env.GERRIT_USERNAME,
                                                'GERRIT_PASSWORD': env.GERRIT_PASSWORD,
                                                'COMMIT_MESSAGE': env.COMMIT_MESSAGE
                                        ])
                                        .toString()
                                sh "${bobWithCommitMessage} update-chart-hooks-version-in-repos:update-stateless-integration-repo"
                            }
                            GERRIT_STATELESS_REPO = 'OSS/com.ericsson.oss.containerisation/eric-enm-stateless-integration'
                            env.STATELESS_GERRIT_URL = sh(returnStdout: true, script: "ssh -p 29418 gerrit-gamma.gic.ericsson.se gerrit query project:${GERRIT_STATELESS_REPO} message:'NO-JIRA ${env.IMAGE_TAG}' | awk '/url:/{print \$2}'").trim().readLines()[0]
                            echo env.STATELESS_GERRIT_URL
                            GERRIT_CHANGE_ID = sh(returnStdout: true, script: "ssh -p 29418 gerrit-gamma.gic.ericsson.se gerrit query project:${GERRIT_STATELESS_REPO} message:'NO-JIRA ${env.IMAGE_TAG}' | awk '/id:/{print \$2}'").trim().readLines()[0]
                            echo GERRIT_CHANGE_ID
                            sh "ssh -p 29418 gerrit-gamma.gic.ericsson.se gerrit set-reviewers --project ${GERRIT_STATELESS_REPO} --add Vandals_review ${GERRIT_CHANGE_ID}"
                        }
                    }
                    post {
                        success {
                            mail to: "PDLVANDALS@pdl.internal.ericsson.com",
                            from: "${env.JOB_NAME}@ericsson.com",
                            subject: "${env.COMMIT_MESSAGE}",
                            body: "Hi Team Vandals,<br><br>" +
                                "Code review has been created in " +
                                "<a href='https://gerrit-gamma.gic.ericsson.se/#/q/project:OSS/com.ericsson.oss.containerisation/eric-enm-stateless-integration'>eric-enm-stateless-integration</a> repo for automated " +
                                "<b>eric-enm-chart-hooks</b> Image uplift to version <b>${env.IMAGE_TAG}</b>." +
                                "<br>This change has been triggered automatically by code merge in " +
                                "<a href='https://gerrit-gamma.gic.ericsson.se/#/q/project:OSS/ENM-Parent/SQ-Gate/com.ericsson.oss.containerisation/eric-enm-chart-hooks'>eric-enm-chart-hooks</a> repo." +
                                "<br><br>Please review the commit: ${env.STATELESS_GERRIT_URL}" +
                                "<br><br>Thank you,<br>'<i>${env.JOB_NAME}</i>' Jenkins job",
                            mimeType: 'text/html'
                        }
                        failure {
                            script {
                                lastStage = env.STAGE_NAME
                            }
                        }
                    }
                }
            }
        }
    }
    post {
        failure {
            mail to: 'PDLVANDALS@pdl.internal.ericsson.com',
                 from: "${env.JOB_NAME}@ericsson.com",
                 subject: "Failed Release Pipeline for 'eric-enm-chart-hooks': ${env.GERRIT_CHANGE_SUBJECT} - ${currentBuild.fullDisplayName}",
                 body: "Failure on ${env.BUILD_URL} in stage ${lastStage}"
        }
        always {
            sh "sudo rm -rf ${env.WORKSPACE}/*"
        }
    }
}

// More about @Builder: http://mrhaki.blogspot.com/2014/05/groovy-goodness-use-builder-ast.html
import groovy.transform.builder.Builder
import groovy.transform.builder.SimpleStrategy

@Builder(builderStrategy = SimpleStrategy, prefix = '')
class BobCommand {
    def bobImage = 'bob.2.0:latest'
    def envVars = [:]
    def needDockerSocket = false

    String toString() {
        def env = envVars
                .collect({ entry -> "-e ${entry.key}=\"${entry.value}\"" })
                .join(' ')

        def cmd = """\
            |docker run
            |--init
            |--rm
            |--workdir \${PWD}
            |--user \$(id -u):\$(id -g)
            |-v \${PWD}:\${PWD}
            |-v /etc/group:/etc/group:ro
            |-v /etc/passwd:/etc/passwd:ro
            |-v \${HOME}/.m2:\${HOME}/.m2
            |-v \${HOME}/.docker:\${HOME}/.docker
            |${needDockerSocket ? '-v /var/run/docker.sock:/var/run/docker.sock' : ''}
            |${env}
            |\$(for group in \$(id -G); do printf ' --group-add %s' "\$group"; done)
            |${bobImage}
            |"""
        return cmd
                .stripMargin()           // remove indentation
                .replace('\n', ' ')      // join lines
                .replaceAll(/[ ]+/, ' ') // replace multiple spaces by one
    }
}
