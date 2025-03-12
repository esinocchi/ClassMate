from fastapi import FastAPI

app = FastAPI()

#root directory for testing connection
@app.get('/')
async def root():
    return {'response': 'Sample API Return'}

#enter main prompt pipeline and return response
@app.get('/endpoints/mainPipelineEntry')
async def mainPipelineEntry(prompt, promptContect, classesContext):
    #go through method routes and include meta data for output format (pdf out for example)
    return {'response': prompt}

@app.get('/endpoints/pullClasses')
async def returnPromptContext(studentID, college):
    #pull access token from database given parameters
    #pull classes from canvas api and return for display
    classes = []
    return {'classes': classes}
