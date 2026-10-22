"""Run MedSafe-AI research application on loopback only."""
import uvicorn

if __name__ == '__main__':
    uvicorn.run('medsafe.api:app', host='127.0.0.1', port=8000)
