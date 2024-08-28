#!/bin/bash

rm -f .coverage
rm -rf cover

pip3 install --upgrade pip
pip3 install requests requests_mock nose coverage kubernetes==24.2.0 pyOpenSSL

export PYTHONPATH=src/:unit-test/:test/bur_cli/src/
nosetests --nologcapture --nocapture --with-coverage --cover-package=src/ --cover-html unit-test/test_*.py
