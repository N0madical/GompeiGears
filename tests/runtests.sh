#!/bin/bash

source .venv/bin/activate
coverage run -m unittest tests/test_models.py
coverage run -m pytest tests/test_routes.py
coverage report -m