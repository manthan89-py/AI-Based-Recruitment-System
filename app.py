import json
import streamlit as st
from phi.utils.log import logger
from streamlit_pdf_viewer import pdf_viewer
from tasks import (
    init_session_state,
    schedule_interview,
    extract_text_from_pdf,
    analyze_resume,
    send_selection_email,
    send_rejection_email,
    add_job_details,
)
from agents import (
    create_resume_analyzer_agent,
    create_scheduler_agent,
    create_email_agent,
)


def main() -> None:
    st.title("AI Recruitment System")

    init_session_state()
    with st.sidebar:
        st.header("Configuration")

        # API Configuration
        st.subheader("LLM Models")
        model_provider = st.selectbox("Model Provider", ["OpenAI", "Claude", "Mistral"])
        api_key = st.text_input(
            "API Key",
            type="password",
            value=st.session_state.api_key,
            help="Get your API key",
        )
        if model_provider:
            st.session_state.model_provider = model_provider
        if api_key:
            st.session_state.api_key = api_key

        st.subheader("Zoom Settings")
        zoom_account_id = st.text_input(
            "Zoom Account ID", type="password", value=st.session_state.zoom_account_id
        )
        zoom_client_id = st.text_input(
            "Zoom Client ID", type="password", value=st.session_state.zoom_client_id
        )
        zoom_client_secret = st.text_input(
            "Zoom Client Secret",
            type="password",
            value=st.session_state.zoom_client_secret,
        )

        st.subheader("Email Settings")
        email_sender = st.text_input(
            "Sender Email",
            value=st.session_state.email_sender,
            help="Email address to send from",
        )
        email_passkey = st.text_input(
            "Email App Password",
            type="password",
            value=st.session_state.email_passkey,
            help="App-specific password for email",
        )
        company_name = st.text_input(
            "Company Name",
            value=st.session_state.company_name,
            help="Name to use in email communications",
        )

        if zoom_account_id:
            st.session_state.zoom_account_id = zoom_account_id
        if zoom_client_id:
            st.session_state.zoom_client_id = zoom_client_id
        if zoom_client_secret:
            st.session_state.zoom_client_secret = zoom_client_secret
        if email_sender:
            st.session_state.email_sender = email_sender
        if email_passkey:
            st.session_state.email_passkey = email_passkey
        if company_name:
            st.session_state.company_name = company_name

        required_configs = {
            "Model Provide": st.session_state.model_provider,
            "API Key": st.session_state.api_key,
            "Zoom Account ID": st.session_state.zoom_account_id,
            "Zoom Client ID": st.session_state.zoom_client_id,
            "Zoom Client Secret": st.session_state.zoom_client_secret,
            "Email Sender": st.session_state.email_sender,
            "Email Password": st.session_state.email_passkey,
            "Company Name": st.session_state.company_name,
        }

    missing_configs = [k for k, v in required_configs.items() if not v]
    if missing_configs:
        st.warning(
            f"Please configure the following in the sidebar: {', '.join(missing_configs)}"
        )
        return

    if not st.session_state.api_key:
        st.warning("Please enter your API Key in the sidebar to continue.")
        return

    with st.expander("Add Job Role & Descriptions", expanded=False):
        job_role = st.text_input("Job Role")
        job_description = st.text_area("Job Description (Use Markdown)")
        additional_instructions = st.text_area(
            "Additional Instructions (Optional)",
            placeholder="Add additional instructions for candidate selection for this particular job role.",
        )
        button = st.button("Add details")
        if button:
            resonse = add_job_details(
                job_role, job_description, additional_instructions
            )
            if resonse:
                st.success("Data Saved Successfully.!!")
            else:
                st.error(
                    "Error occurred while storing the data. Make sure to provide Job Role and Job Description."
                )
    with open("data/job_descriptions.json", "r") as f:
        json_descriptions_data = json.load(f)

    role = st.selectbox(
        "Select the role you're applying for:",
        json_descriptions_data.keys(),
    )
    with st.expander("Job Description", expanded=True):
        text_markdown = """
        {job_descriptions}        
        """
        st.markdown(
            text_markdown.format(
                job_descriptions=json_descriptions_data[role]["job_description"],
            )
        )

    # Add a "New Application" button before the resume upload
    if st.button("📝 New Application"):
        # Clear only the application-related states
        keys_to_clear = [
            "resume_text",
            "analysis_complete",
            "is_selected",
            "candidate_email",
            "current_pdf",
        ]
        for key in keys_to_clear:
            if key in st.session_state:
                st.session_state[key] = None if key == "current_pdf" else ""
        st.rerun()

    resume_file = st.file_uploader(
        "Upload your resume (PDF)", type=["pdf"], key="resume_uploader"
    )
    if resume_file is not None and resume_file != st.session_state.get("current_pdf"):
        st.session_state.current_pdf = resume_file
        st.session_state.resume_text = ""
        st.session_state.analysis_complete = False
        st.session_state.is_selected = False
        st.rerun()

    if resume_file:
        st.subheader("Uploaded Resume")
        col1, col2 = st.columns([4, 1])

        with col1:
            import tempfile, os

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(resume_file.read())
                tmp_file_path = tmp_file.name
            resume_file.seek(0)
            try:
                pdf_viewer(tmp_file_path)
            finally:
                os.unlink(tmp_file_path)

        with col2:
            st.download_button(
                label="📥 Download",
                data=resume_file,
                file_name=resume_file.name,
                mime="application/pdf",
            )
        # Process the resume text
        if not st.session_state.resume_text:
            with st.spinner("Processing your resume..."):
                resume_text = extract_text_from_pdf(resume_file)
                if resume_text:
                    st.session_state.resume_text = resume_text
                    st.success("Resume processed successfully!")
                else:
                    st.error("Could not process the PDF. Please try again.")

    # Email input with session state
    email = st.text_input(
        "Candidate's email address",
        value=st.session_state.candidate_email,
        key="email_input",
    )
    st.session_state.candidate_email = email

    # Analysis and next steps
    if (
        st.session_state.resume_text
        and email
        and not st.session_state.analysis_complete
    ):
        if st.button("Analyze Resume"):
            with st.spinner("Analyzing your resume..."):
                resume_analyzer = create_resume_analyzer_agent()
                email_agent = create_email_agent()  # Create email agent here

                if resume_analyzer and email_agent:
                    print("DEBUG: Starting resume analysis")
                    is_selected, feedback = analyze_resume(
                        resume_text=st.session_state.resume_text,
                        role_requirements=json_descriptions_data[role],
                        role=role,
                        analyzer=resume_analyzer,
                    )
                    print(
                        f"DEBUG: Analysis complete - Selected: {is_selected}, Feedback: {feedback}"
                    )

                    if is_selected:
                        st.success(
                            "Congratulations! Your skills match our requirements."
                        )
                        st.session_state.analysis_complete = True
                        st.session_state.is_selected = True
                        st.rerun()
                    else:
                        st.warning(
                            "Unfortunately, your skills don't match our requirements."
                        )
                        st.write(f"Feedback: {feedback}")

                        # Send rejection email
                        with st.spinner("Sending feedback email..."):
                            try:
                                send_rejection_email(
                                    email_agent=email_agent,
                                    to_email=email,
                                    role=role,
                                    feedback=feedback,
                                )
                                st.info(
                                    "We've sent you an email with detailed feedback."
                                )
                            except Exception as e:
                                logger.error(f"Error sending rejection email: {e}")
                                st.error(
                                    "Could not send feedback email. Please try again."
                                )

    if st.session_state.get("analysis_complete") and st.session_state.get(
        "is_selected", False
    ):
        st.success("Congratulations! Your skills match our requirements.")
        st.info(
            "Click 'Proceed with Application' to continue with the interview process."
        )

        if st.button("Proceed with Application", key="proceed_button"):
            print("DEBUG: Proceed button clicked")  # Debug
            with st.spinner("🔄 Processing your application..."):
                try:
                    print("DEBUG: Creating email agent")  # Debug
                    email_agent = create_email_agent()
                    print(f"DEBUG: Email agent created: {email_agent}")  # Debug

                    print("DEBUG: Creating scheduler agent")  # Debug
                    scheduler_agent = create_scheduler_agent()
                    print(f"DEBUG: Scheduler agent created: {scheduler_agent}")  # Debug

                    # 3. Send selection email
                    with st.status(
                        "📧 Sending confirmation email...", expanded=True
                    ) as status:
                        print(
                            f"DEBUG: Attempting to send email to {st.session_state.candidate_email}"
                        )  # Debug
                        send_selection_email(
                            email_agent, st.session_state.candidate_email, role
                        )
                        print("DEBUG: Email sent successfully")  # Debug
                        status.update(label="✅ Confirmation email sent!")

                    # 4. Schedule interview
                    with st.status(
                        "📅 Scheduling interview...", expanded=True
                    ) as status:
                        print("DEBUG: Attempting to schedule interview")  # Debug
                        schedule_interview(
                            scheduler_agent,
                            st.session_state.candidate_email,
                            email_agent,
                            role,
                        )
                        print("DEBUG: Interview scheduled successfully")  # Debug
                        status.update(label="✅ Interview scheduled!")

                    print("DEBUG: All processes completed successfully")  # Debug
                    st.success(
                        """
                        🎉 Application Successfully Processed!
                        
                        Please check your email for:
                        1. Selection confirmation ✅
                        2. Interview details with Zoom link 🔗
                        
                        Next steps:
                        1. Review the role requirements
                        2. Prepare for your technical interview
                        3. Join the interview 5 minutes early
                    """
                    )

                except Exception as e:
                    print(f"DEBUG: Error occurred: {str(e)}")  # Debug
                    print(f"DEBUG: Error type: {type(e)}")  # Debug
                    import traceback

                    print(f"DEBUG: Full traceback: {traceback.format_exc()}")  # Debug
                    st.error(f"An error occurred: {str(e)}")
                    st.error("Please try again or contact support.")

    # Reset button
    if st.sidebar.button("Reset Application"):
        for key in st.session_state.keys():
            if key != "api_key":
                del st.session_state[key]
        st.rerun()


if __name__ == "__main__":
    main()
