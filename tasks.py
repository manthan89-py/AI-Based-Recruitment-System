from typing import Literal, Tuple
import json
import PyPDF2
from datetime import datetime, timedelta
import pytz

import streamlit as st
from phi.agent import Agent
from phi.utils.log import logger


def init_session_state() -> None:
    """Initialize only necessary session state variables."""
    defaults = {
        "candidate_email": "",
        "model_provider": "",
        "api_key": "",
        "resume_text": "",
        "analysis_complete": False,
        "is_selected": False,
        "zoom_account_id": "",
        "zoom_client_id": "",
        "zoom_client_secret": "",
        "email_sender": "",
        "email_passkey": "",
        "company_name": "",
        "current_pdf": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def extract_text_from_pdf(pdf_file) -> str:
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        st.error(f"Error extracting PDF text: {str(e)}")
        return ""


def add_job_details(job_role, job_description, additional_instructions):
    job_role = job_role.strip()
    job_description = job_description.strip()
    additional_instructions = additional_instructions.strip()
    file_path = "data/job_descriptions.json"
    if job_role and job_description:
        try:
            with open(file_path, "r") as file:
                job_descriptions_data = json.load(file)
            temp = {
                "job_description": job_description,
                "additional_instructions": additional_instructions,
            }
            job_descriptions_data[job_role] = temp
            with open("data/job_descriptions.json", "w") as f:
                json.dump(job_descriptions_data, f, indent=4)
            return True
        except Exception as e:
            logger.error(f"Error occurred while storing job_descriptions< {e}")
            return False
    else:
        return False


def analyze_resume(
    resume_text: str,
    role_requirements,
    role,
    analyzer: Agent,
) -> Tuple[bool, str]:
    try:
        response = analyzer.run(
            f"""Analyze the provided resume against the specified role requirements and provide a detailed evaluation as a JSON object.
            Resume Text: {resume_text}
            Job Role: {role}
            Role Requirements: {role_requirements['job_description']}
            Additional Instructions from Recruiter Side (Must follow if provided):
            {role_requirements['additional_instructions']}
            Your JSON response must adhere to this structure:
            {{
                "selected": true/false,
                "feedback": "Detailed feedback explaining the decision",
                "matching_skills": ["skill1", "skill2"],
                "missing_skills": ["skill3", "skill4"],
                "experience_level": "junior/mid/senior"
            }}
    
            Evaluation Guidelines:
            - Skill Match: Ensure at least 75% alignment with the role's required skills. Highlight specific examples when skills are demonstrated.
            - Practical Experience: Emphasize hands-on experience, real-world applications, and significant projects related to the role.
            - Transferable Skills: Consider similar technologies or adjacent skills that add value.
            - Continuous Learning: Identify evidence of growth, such as certifications, courses, or self-initiated projects.
            - Soft Skills & Adaptability: Note any mention of leadership, teamwork, problem-solving, or adaptability that enhances suitability for the role.
            
            Important:
            - Prioritize clarity and accuracy in your analysis.
            - Provide constructive feedback to guide the decision-making process.
            - Return ONLY the JSON object without additional formatting or text.
            """
        )

        assistant_message = next(
            (msg.content for msg in response.messages if msg.role == "assistant"), None
        )
        if not assistant_message:
            raise ValueError("No assistant message found in response.")
        response = assistant_message.strip("```").strip("json")
        result = json.loads(response)
        if not isinstance(result, dict) or not all(
            k in result for k in ["selected", "feedback"]
        ):
            raise ValueError("Invalid response format")

        return result["selected"], result["feedback"]

    except (json.JSONDecodeError, ValueError) as e:
        st.error(f"Error processing response: {str(e)}")
        return False, f"Error analyzing resume: {str(e)}"


def send_selection_email(email_agent: Agent, to_email: str, role: str) -> None:
    email_agent.run(
        f"""
        Send an email to {to_email} regarding their selection for the {role} position.
        The email should:
        1. Start by congratulating the candidate on being selected for the interview.
        Use professional and courteous language throughout the email.
        2. Briefly highlight why their profile stood out (e.g., skills, experience, or potential).
        3. Clearly outline the next steps in the process.
        4. Mention that they will receive the interview details, including date, time, and format, shortly.
        5. Encourage them to prepare for the interview and let them know they can reach out with questions or concerns.
        6. Use a clear structure with paragraphs and bullet points for readability.
        End with a friendly and professional closing, signed by 'AI Recruiting Team.'
        """
    )


def send_rejection_email(
    email_agent: Agent, to_email: str, role: str, feedback: str
) -> None:
    """
    Send a rejection email with constructive feedback.
    """
    email_agent.run(
        f"""
        Send an email to {to_email} regarding their application for the {role} position.
        The email should:
        1. Be empathetic, respectful, and human in tone.
        2. Acknowledge their effort and interest in applying for the role.
        3. Provide specific feedback from: {feedback}, focusing on areas where they could improve.
        4. Suggest actionable steps to enhance their skills or experience based on the feedback.
        5. Recommend relevant learning resources, such as online courses, books, or certifications, tailored to the missing skills.
        6. Encourage them to reapply in the future once they’ve addressed the areas of improvement.
        7. End the email with the exact closing:
        best,
        the ai recruiting team
        8. Ensure the email is concise yet thoughtful, with professional wording and a supportive tone.
        """
    )


def schedule_interview(
    scheduler: Agent, candidate_email: str, email_agent: Agent, role: str
) -> None:
    """
    Schedule interviews during business hours (9 AM - 5 PM IST).
    """
    try:
        # Get current time in IST
        ist_tz = pytz.timezone("Asia/Kolkata")
        current_time_ist = datetime.now(ist_tz)

        tomorrow_ist = current_time_ist + timedelta(days=1)
        interview_time = tomorrow_ist.replace(
            hour=11, minute=0, second=0, microsecond=0
        )
        formatted_time = interview_time.strftime("%Y-%m-%dT%H:%M:%S")

        meeting_response = scheduler.run(
            f"""Schedule a 60-minute technical interview with these specifications:
            - Title: '{role} Technical Interview'
            - Date: {formatted_time}
            - Timezone: IST (India Standard Time)
            - Attendee: {candidate_email}
            
            Important Notes:
            - The meeting must be between 9 AM - 5 PM IST
            - Use IST (UTC+5:30) timezone for all communications
            - Include timezone information in the meeting details
            """
        )

        email_agent.run(
            f"""Send an email confirming the scheduled interview for the {role} position.

            The email should:
            1. Start with a polite and enthusiastic confirmation of the interview details.
            2. Include the following information clearly:
            Role: {role} position
            Meeting Details: {meeting_response}
            3. Clearly state that the time is in IST (India Standard Time) and provide a link for timezone conversion to help the candidate plan accordingly.
            4. Politely request the candidate to join 5 minutes early to ensure a smooth start.
            5. Encourage the candidate to be confident and well-prepared for the interview. Offer tips or resources if appropriate (e.g., topics to review or format expectations).
            6. Conclude with a friendly note, wishing them the best for the interview.
            
            Tone and Style:
            - Use professional yet warm language to create a positive impression.
            - Format the email for readability with bullet points or short paragraphs.
            """
        )

        st.success("Interview scheduled successfully! Check your email for details.")

    except Exception as e:
        logger.error(f"Error scheduling interview: {str(e)}")
        st.error("Unable to schedule interview. Please try again.")
