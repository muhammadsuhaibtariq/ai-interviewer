#!/bin/bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 &

# Return to root directory
cd ..

# Start Streamlit on port 8501
cd frontend
python -m streamlit run app.py --server.port 8501 --server.address 0.0.0.0
