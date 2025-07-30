# AWS CloudFront Behaviors
Script to add new behaviours to a defined CloudFront with ID

## Installation
- clone the repository
- navigate to this folder
- create virtual environment `python -m venv .venv` (if don't have `python`, might be `python3`)
- switch to virtual environment `source .venv/bin/activate` (install system requirements python env if needed)
- install the required packages with `pip install -r requirements.txt`
- if the APP is on a standalone instance in AWS then add `--single-app` as parameter below
- run the script `python update_cache_behaviors.py --id YOURCFID`
- when done, exit virtual environment with typing `deactivate`
