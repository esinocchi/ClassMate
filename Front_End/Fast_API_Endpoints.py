from fastapi import FastAPI

app = FastAPI()

@app.get('/')
async def root():
    return {'Sample': 'Sample API Return', "Example": "Sample Response"}