# PHP Markdown documentation generator
Script to generate docs from PHPDoc and comments for Drupal or non-drupal projects.

## Installation
- clone the repository
- navigate to this folder
- create virtual environment `python -m venv .venv` (if don't have `python`, might be `python3`)
- switch to virtual environment `source .venv/bin/activate` (install system requirements python env if needed)
- install the required packages with `pip install -r requirements.txt`
- run the script:
```shell
# example for Drupal
python generate_php_docs.py \
  --drupal \
  --target=/home/user/projects/MRM/espen-remora \
  --source=web/modules/custom

# example with overridden parameters and/or non-drupal project
python generate_php_docs.py \
  --target=/home/user/projects/MRM/iu-planner \
  --source=src \
  --output=docs-non-standard
```
- when done, exit virtual environment with typing `deactivate`
