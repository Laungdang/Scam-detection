import os

# เลือกรัน: "streamlit" หรือ "api"
MODE = os.getenv("RUN_MODE", "api")

if MODE == "streamlit":
    os.system("python -m streamlit run app/ui/streamlit_app.py")
else:
    os.system("uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000")
