#!/bin/bash

OS_NAME="$(uname | awk '{print tolower($0)}')"

SHELL_DIR=$(dirname $0)

CMD=${1:-$CIRCLE_JOB}

RUN_PATH=${2:-$SHELL_DIR}

USERNAME=${CIRCLE_PROJECT_USERNAME:-opsnow-tools}
REPONAME=${CIRCLE_PROJECT_REPONAME:-elasticsearch-snapshot}

BRANCH=${CIRCLE_BRANCH:-master}

PR_NUM=${CIRCLE_PR_NUMBER}
PR_URL=${CIRCLE_PULL_REQUEST}

################################################################################

# command -v tput > /dev/null && TPUT=true
TPUT=

_echo() {
    if [ "${TPUT}" != "" ] && [ "$2" != "" ]; then
        echo -e "$(tput setaf $2)$1$(tput sgr0)"
    else
        echo -e "$1"
    fi
}

_result() {
    echo
    _echo "# $@" 4
}

_command() {
    echo
    _echo "$ $@" 3
}

_success() {
    echo
    _echo "+ $@" 2
    exit 0
}

_error() {
    echo
    _echo "- $@" 1
    exit 1
}

_replace() {
    if [ "${OS_NAME}" == "darwin" ]; then
        sed -i "" -e "$1" $2
    else
        sed -i -e "$1" $2
    fi
}

_prepare() {
    # target
    mkdir -p ${RUN_PATH}/target/publish
    mkdir -p ${RUN_PATH}/target/release

    # 755
    find ./** | grep [.]sh | xargs chmod 755
}

_package() {
    if [ ! -f ${SHELL_DIR}/target/VERSION ]; then
        _error
    fi

    VERSION=$(cat ${SHELL_DIR}/target/VERSION | xargs)
    _result "VERSION=${VERSION}"

    # chart path
    CHART_PATH="${RUN_PATH}/charts/elasticsearch-snapshot"

    # replace
    _replace "s|version: .*|version: ${VERSION}|" ${CHART_PATH}/Chart.yaml
    _replace "s|appVersion: .*|appVersion: ${VERSION}|" ${CHART_PATH}/Chart.yaml
    _replace "s|tag: .*|tag: ${VERSION}|" ${CHART_PATH}/values.yaml

    # release draft.tar.gz
    pushd ${CHART_PATH}
    tar -czf ../../target/release/${REPONAME}-${VERSION}.tar.gz *
    popd
}

################################################################################

_prepare

_package
