from dotenv import load_dotenv
import os

from openai import OpenAI
from ..models.question import QuestionResponse

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# Persona-to-role mapping
persona_roles = {
    "HR": "HR specialist",
    "Recruiter": "recruiter",
    "Hiring Manager": "hiring manager",
    "Technical Interviewer": "technical expert"
}

def generate_interview_questions(persona: str, job_description: str):
    try:
        # Prepare the system message to guide the AI
        system_message = (
            "You are an AI assistant that generates interview questions for candidates based on a given job description. "
            "You must tailor the questions according to the interviewer's persona (HR, Recruiter, Hiring Manager, Technical Interviewer). "
            "Each question must include a suggested answer to serve as a benchmark for evaluating responses."
        )

        if persona == "HR":
            user_message = (
                f"Generate 10 to 15 general screening interview questions for a candidate applying for the role described below. "
                f"As an **HR specialist**, focus on:\n"
                f"- Cultural fit\n"
                f"- Basic qualifications\n"
                f"- Salary expectations\n"
                f"- Work authorization and availability\n\n"
                f"Each question must include a suggested answer to help evaluate the candidate's response.\n\n"
                f"**Job Description:** {job_description}"
            )
        elif persona == "Recruiter":
            user_message = (
                f"Generate 10 to 15 preliminary interview questions for a candidate applying for the role described below. "
                f"As a **recruiter**, focus on:\n"
                f"- Work experience and key competencies\n"
                f"- Career background and motivations\n"
                f"- Logistical considerations (e.g., availability, relocation, notice period)\n\n"
                f"Each question must include a suggested answer to help evaluate the candidate's response.\n\n"
                f"**Job Description:** {job_description}"
            )
        elif persona == "Hiring Manager":
            user_message = (
                f"Generate 10 to 15 in-depth interview questions for a candidate applying for the role described below. "
                f"As a **hiring manager**, focus on:\n"
                f"- Role alignment and long-term fit\n"
                f"- Past achievements and impact\n"
                f"- Scenario-based questions (e.g., 'Tell me about a time when...')\n"
                f"- Strategic problem-solving and decision-making\n\n"
                f"Include at least 5-6 scenario-based questions, asking how the candidate would respond in real-life situations.\n"
                f"Each question must include a suggested answer to help evaluate the candidate's response.\n\n"
                f"**Job Description:** {job_description}"
            )
        elif persona == "Technical Interviewer":
            user_message = (
                f"Generate 10 to 15 technical interview questions for a candidate applying for the role described below. "
                f"As a **technical expert**, focus on:\n"
                f"- Role-specific technical skills (e.g., coding, system design, troubleshooting scenarios)\n"
                f"- Practical problem-solving exercises\n"
                f"- Hands-on assessments where possible\n"
                f"- Industry best practices\n\n"
                f"Each question must include a suggested answer or an example of an ideal response.\n\n"
                f"**Job Description:** {job_description}"
            )
        else:
            user_message = (
                f"Generate 10 interview questions for a candidate applying for the role described below. "
                f"The questions should be tailored to the {persona_roles.get(persona, 'interviewer')} persona. "
                f"Each question must include a suggested answer to help evaluate the candidate's response.\n\n"
                f"**Job Description:** {job_description}"
            )

        # API call to OpenAI GPT model
        completion = client.beta.chat.completions.parse(  # Ensure structured response
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
            response_format=QuestionResponse
        )

        # Debugging: Check the raw response
        raw_response = completion.choices[0].message.parsed

        # Ensure the response is in the correct format for FastAPI
        questions = raw_response.questions
        suggested_answers = raw_response.suggested_answers

        # If no questions were generated, log and return empty lists
        if not questions or not suggested_answers:
            print("No questions or suggested answers were generated.")
            return {"questions": [], "suggested_answers": []}

        return {"questions": questions, "suggested_answers": suggested_answers}

    except Exception as e:
        print(f"Error generating questions: {e}")
        return {"questions": [], "suggested_answers": []}