#!/bin/bash

pip3 install --upgrade pip
pip3 install requests kubernetes==24.2.0

export PYTHONPATH=src/:test/bur_cli/src/:testframework/
pylint src/
pylint test/test_hook.py
