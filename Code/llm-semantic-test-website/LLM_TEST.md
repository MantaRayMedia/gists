# Use LLM models to test semantic HTML of a website
This needs to run on our AWS LLM box or locally with ollama.

The script has 4 layers and provides a "ticket" output of issues.

| Layer    | Type                 |
|----------|----------------------|
| DOM      | deterministic truth  |
| matrics  | mathematical signals |
| SLM      | interpretation       |
| markdown | ticket output        |
