# Project Setup and Run Instructions

To run this project, follow these steps:

1. Create and activate a Python virtual environment:

```powershell
python -m venv autogen-env
.\autogen-env\Scripts\Activate.ps1
```

2. Install required packages:

```powershell
pip install autogen_ext azure-identity azure-ai-openai
```

3. Run the main script:

```powershell
python main.py
```

Make sure to share both `main.py` and `credentials.py` files with your friend to run the project successfully.

---

Replace the API key in `credentials.py` with your own Azure OpenAI API key before running.
