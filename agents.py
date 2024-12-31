import streamlit as st
from phi.agent import Agent
from phi.model.mistral import MistralChat
from phi.model.anthropic import Claude
from phi.model.openai import OpenAIChat
from phi.tools.email import EmailTools
from tools import CustomZoomTool


def get_the_model():
    mdoel_provider = st.session_state.model_provider
    model_function_map = {
        "OpenAI": OpenAIChat(id="gpt-4o", api_key=st.session_state.api_key),
        "Mistral": MistralChat(
            id="mistral-large-latest", api_key=st.session_state.api_key
        ),
        "Claude": Claude(
            id="claude-3-5-sonnet-latest", api_key=st.session_state.api_key
        ),
    }
    return model_function_map[mdoel_provider]


def create_resume_analyzer_agent() -> Agent:
    """Creates and returns a resume analysis agent."""
    if not st.session_state.api_key:
        st.error("Please enter your API Key first.")
        return None

    return Agent(
        model=get_the_model(),
        description="You are an expert technical recruiter who analyzes resumes.",
        instructions=[
            "Analyze the resume against the provided job requirements",
            "Be lenient with AI/ML candidates who show strong potential",
            "Consider project experience as valid experience",
            "Value hands-on experience with key technologies",
            "Return a JSON response with selection decision and feedback",
        ],
        markdown=True,
    )


def create_email_agent() -> Agent:
    return Agent(
        model=get_the_model(),
        tools=[
            EmailTools(
                receiver_email=st.session_state.candidate_email,
                sender_email=st.session_state.email_sender,
                sender_name=st.session_state.company_name,
                sender_passkey=st.session_state.email_passkey,
            )
        ],
        description="You are a professional recruitment coordinator handling email communications.",
        instructions=[
            "Draft and send professional recruitment emails",
            "Properly formatted (Headers, Bullet points, Paragraphs and CamcelCase) without markdown email should be written."
            "Act like a human writing an email and use all lowercase letters",
            "Maintain a friendly yet professional tone",
            "Always end emails with exactly: 'best,\nthe ai recruiting team'",
            "Never include the sender's or receiver's name in the signature",
            f"The name of the company is '{st.session_state.company_name}'",
        ],
        markdown=False,
        show_tool_calls=False,
    )


def create_scheduler_agent() -> Agent:
    zoom_tools = CustomZoomTool(
        account_id=st.session_state.zoom_account_id,
        client_id=st.session_state.zoom_client_id,
        client_secret=st.session_state.zoom_client_secret,
    )

    return Agent(
        name="Interview Scheduler",
        model=get_the_model(),
        tools=[zoom_tools],
        description="You are an interview scheduling coordinator.",
        instructions=[
            "You are an expert at scheduling technical interviews using Zoom.",
            "Schedule interviews during business hours (9 AM - 5 PM EST)",
            "Create meetings with proper titles and descriptions",
            "Ensure all meeting details are included in responses",
            "Use ISO 8601 format for dates",
            "Handle scheduling errors gracefully",
        ],
        markdown=False,
        show_tool_calls=False,
    )

