# AI_agent 

https://chatgpt.com/share/6af83cba-0938-83eb-847f-c32b50b049e2

# to install environment

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# MACOT AI Agent — Person 1

Terminal-only conversation prototype. Understands multilingual customer messages and extracts structured order data. Does **not** save or confirm orders, check availability, or calculate delivery fees.

## Run

```bash
cd macot_agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Put your Gemini API key in .env
python agent.py
```

## Integration notes

- `AgentOutput` is a provisional contract; coordinate final fields with Person 2.
- The production agent must call backend tools to get menu, validate quotes, check daily availability, and atomically confirm orders.
- Only a backend-validated quote can be approved, and explicit approval must reference the latest quote version.
- Do not commit `.env` or credentials.
