from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow specific origins (replace with the required ones)
origins = [
    "https://psu.instructure.com",  # The origin where the request is coming from
    "https://canvasclassmate.me",   # Your domain
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,            # Domains allowed to access your API
    allow_credentials=True,
    allow_methods=["*"],              # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],              # Allow all headers
)

@app.get('/')
async def root():
    return {'response': 'Sample API Return'}