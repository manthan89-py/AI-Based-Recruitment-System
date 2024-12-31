# Use the official Python 3.10 image
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Copy application files
COPY . /app

# Install pip and uv
RUN pip install --no-cache-dir uv

# install dependencies
RUN uv pip install --requirement pyproject.toml --system

# Expose the Streamlit port
EXPOSE 8501

# Command to run the application
CMD ["streamlit", "run", "app.py"]