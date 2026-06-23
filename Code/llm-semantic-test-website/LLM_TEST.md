# Use LLM models to test semantic HTML of a website
This needs to run on our AWS LLM box or locally with ollama.

The script has 4 layers and provides a "ticket" output of issues.

| Layer    | Type                 |
|----------|----------------------|
| DOM      | deterministic truth  |
| matrics  | mathematical signals |
| SLM      | interpretation       |
| markdown | ticket output        |

It contains a config file with all the constants and prompts.
The script can be used on `remora` and `non-remora` websites for analysis.

## Usage
Run within `venv` (make sure ollama model from config is installed `ollama list`)
```shell
# create it
python3 -m venv venv
# activate it
source venv/bin/activate
# install dependencies
pip install -r requirements.txt

# use one of the following
python web_audit.py https://example.com
python web_audit.py https://example.com --model llama3.2:3b --out-dir reports/
python web_audit.py https://example.com --no-cache --max-regions 6

python web_audit.py https://example.com --deep-ai-check

python web_audit.py https://example.com --profile remora
python web_audit.py https://example.com --profile-file my_remora_tuned.json
```
