from fastapi import FastAPI

app = FastAPI()

@app.get('/')
async def root():
    return {'response': 'Sample API Return'}

@app.get('/endpoints/mainPipelineEntry')
async def mainPipelineEntry(int1, int2):
    total = int1 + int2
    return {'response': total}
