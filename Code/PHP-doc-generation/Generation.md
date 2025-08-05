# PHP Markdown documentation generator
Script to generate docs from PHPDoc and comments

## Installation
- clone the repository
- navigate to this folder
- create virtual environment `python -m venv .venv` (if don't have `python`, might be `python3`)
- switch to virtual environment `source .venv/bin/activate` (install system requirements python env if needed)
- install the required packages with `pip install -r requirements.txt`
- run the script:
```shell
# example with target only
python generate_php_docs.py --target /home/user/projects/MRM/espen-remora

# example with overridden parameters
python generate_php_docs.py \
  --target /home/user/projects/MRM/espen-remora \
  --source /home/user/projects/MRM/espen-remora/web/modules/custom \
  --output /home/user/projects/MRM/espen-remora/.docs
```
- when done, exit virtual environment with typing `deactivate`
