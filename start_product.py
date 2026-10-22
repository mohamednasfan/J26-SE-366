"""Start MedSafe-AI locally with: python start_product.py"""
import uvicorn
if __name__ == '__main__':
    uvicorn.run('medsafe.api_product:app',host='127.0.0.1',port=8000,reload=False)
