#!/bin/bash
rm -rf ./dist/*.whl
rm -rf ./dist/*.tar.gz
rm -rf ./build/*

python3 setup.py sdist
python3 setup.py bdist_wheel
twine upload dist/*
#twine upload --repository testpypi dist/*