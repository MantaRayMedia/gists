# AWS Archive bucket to Glacier
Script migrates S3 bucket to S3 Glacier (long term storage). This file 1-to-1 copies. Please use zip instructions from notion.

## Installation
- clone the repository
- navigate to this folder
- create virtual environment `python -m venv .venv` (if don't have `python`, might be `python3`)
- switch to virtual environment `source .venv/bin/activate` (install system requirements python env if needed)
- install the required packages with `pip install -r requirements.txt`
- run script by typing `python migrate_bucket.py`
- when done, exit virtual environment with typing `deactivate`
