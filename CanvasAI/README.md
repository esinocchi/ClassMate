# CanvasAI

A RAG-based AI assistant for Canvas LMS.

## Setup

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv myenv
   source myenv/bin/activate  # On Windows use: myenv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   - Copy `.env.example` to `.env`
   - Fill in your actual values in `.env`:
     ```
     API_KEY='your-openai-api-key'
     CANVAS_TOKEN='your-canvas-token'
     CANVAS_URL='your-canvas-url'
     ```

## Running the Application

1. Make sure your virtual environment is activated
2. Run the desired script:
   ```bash
   python -m canvas_rag.canvas_api  # To list courses
   python -m canvas_rag.rag         # To use the RAG system
   ```
