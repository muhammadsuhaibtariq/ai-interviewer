from fastapi import FastAPI, APIRouter, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from .services.execute_custom_extractors import process_extract_text
from .services.ai_service import generate_interview_questions
from .config.mongo_db import client, users_collection

from .models.user import User, SaveResponseRequest
from .models.question import QuestionRequest

import os
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

HOST = '0.0.0.0'
PORT = 8000


# Create an instance of the FastAPI application
app = FastAPI(
    title="AI POWERED INTERVIEW QUESTIONS API",
)

# Define the list of allowed origins for CORS
origins = [
    "http://localhost:8000", 
    "frontend-ai-interviewer-c9eycfc7hqgkdkhc.canadacentral-01.azurewebsites.net"  # Localhost development server
    # Add more origins as needed
]

# Add CORS middleware to the FastAPI application
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,    # Allow specified origins
    allow_credentials=True,   # Allow cookies and other credentials
    allow_methods=["*"],      # Allow all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],      # Allow all headers
)

# Define the router
router = APIRouter()

@router.get("/")
async def root():
    return {"message": "Hello World"}

@router.get("/check-mongo")
async def check_mongo():
    try:
        # Attempt to get the server information to check connection
        client.server_info()
        return JSONResponse(content={"message": "MongoDB connection successful!"}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": f"Error connecting to MongoDB: {e}"}, status_code=500)

# route to save user details
@router.post("/save-user/")
async def save_user(user: User):
    """Save user details by email in MongoDB."""
    existing_user = users_collection.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")

    user_dict = user.model_dump()
    users_collection.insert_one(user_dict)

    return {"message": "User saved successfully"}

# Allowed file extensions
ALLOWED_EXTENSIONS = {'pdf', 'docx'}

@router.post("/extract-text/", summary="Upload a document file (PDF or DOCX) or raw text")
async def extract_text(
    file: UploadFile = File(None),  # Explicitly mark as a File input
    text: str = Form(None)  # Ensure text input is from form data
):
    """
    Upload a job description document (PDF, DOCX) or input plain text.

    **Parameters:**
    - `file`: Upload a job description file (PDF or DOCX).
    - `text`: Provide job description as plain text.

    **Returns:**
    - Extracted text from the document or the provided text.
    """
    if file and text:
        raise HTTPException(status_code=400, detail="Provide either a file OR plain text, not both.")

    if file:
        if not file.filename.lower().endswith(tuple(ALLOWED_EXTENSIONS)):
            raise HTTPException(status_code=400, detail="Invalid file type. Only PDF or DOCX allowed.")
        return await process_extract_text(file)

    if text:
        return text

    raise HTTPException(status_code=400, detail="No file or text provided.")


persona_roles = {
    "HR": "HR specialist",
    "Recruiter": "recruiter",
    "Hiring Manager": "hiring manager",
    "Technical Interviewer": "technical expert"
}

@app.post("/generate-questions/")
async def generate_questions(request: QuestionRequest):
    email = request.email
    persona = request.persona
    job_description = request.job_description

    if persona not in persona_roles:
        raise HTTPException(status_code=400, detail="Invalid persona selected.")

    # Generate interview questions and suggested answers
    response = generate_interview_questions(persona, job_description)

    # Find the user by email
    user = users_collection.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

        # If the job description is not set, update it at the user level
    if "job_description" not in user or not user["job_description"]:
        users_collection.update_one(
            {"email": email},
            {"$set": {"job_description": job_description}}
        )

    # Prepare assessment result
    assessment_result = {
        "persona": persona,
        "questions": response["questions"],
        "suggested_answers": response["suggested_answers"]
    }

    # Update the user's document with assessment results
    users_collection.update_one(
        {"email": email},
        {"$push": {"assessment_results": assessment_result}}  # Add new result to the array
    )

    return {"questions": response["questions"]}


@app.post("/save-response/")
async def save_response(request: SaveResponseRequest):
    email = request.email
    persona = request.persona
    answers = request.answers

    # Find user
    user = users_collection.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Update persona's assessment with multiple answers
    updated = users_collection.update_one(
        {"email": email, "assessment_results.persona": persona},
        {"$push": {"assessment_results.$.responses": {"$each": answers}}}  # Append multiple answers
    )

    if updated.modified_count == 0:
        raise HTTPException(status_code=400, detail="Persona assessment not found or responses not saved.")

    return {"message": "Responses saved successfully!"}


@router.get("/get-results/{email}")
def get_user_results(email: str):
    user_record = users_collection.find_one({"email": email})

    if not user_record:
        return JSONResponse(content={"message": "No assessment results found."}, status_code=404)

    # Extract user details
    user_data = {
        "name": user_record.get("name", "Unknown Candidate"),  # Ensure name is included
        "email": user_record.get("email"),
        "assessment_results": user_record.get("assessment_results", [])
    }

    return JSONResponse(content=user_data, status_code=200)

@router.get("/compare-answers-ai/{email}")
def compare_answers_ai(email: str):
    user_record = users_collection.find_one({"email": email})
    if not user_record:
        raise HTTPException(status_code=404, detail="User not found")

    assessment_results = user_record.get("assessment_results", [])
    similarity_scores = {}

    for assessment in assessment_results:
        persona = assessment.get("persona", "Unknown Persona")
        user_responses = assessment.get("responses", [])
        suggested_answers = assessment.get("suggested_answers", [])

        if not user_responses or not suggested_answers:
            similarity_scores[persona] = 0
            continue

        messages = [
            {"role": "system", "content": "You are an AI evaluator that gives a similarity score between 0 and 100 based on how closely a user's response matches the suggested answer."},
            {"role": "user", "content": "\n".join(
                [f"User Response: {resp}\nSuggested Answer: {ans}" for resp, ans in zip(user_responses, suggested_answers)]
            )},
            {"role": "user", "content": "Evaluate the similarity and return only the percentage score as a number (e.g., 85.5)."}
        ]

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=10
        )

        try:
            score = float(response.choices[0].message.content.strip())
        except ValueError:
            score = 0

        similarity_scores[persona] = round(score, 2)

    return JSONResponse(content=similarity_scores, status_code=200)


# Include the router in the FastAPI application
app.include_router(router)

if __name__ == '__main__':
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=True,
    )