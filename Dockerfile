# Use an official Python base image
FROM python:3.10.14-slim

# Set working directory in the container
WORKDIR /app

# Ensure tzdata and required libraries are installed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire source code
COPY . .

# Expose the API port
EXPOSE 7860

# Add a user to run the application (Hugging Face Spaces requirement)
RUN useradd -m -u 1000 user
USER user

# Default environment variables
ENV HOST=0.0.0.0
ENV PORT=7860
ENV USE_REAL_API=false

# Run the pre-validation check
RUN python pre_validation.py

# Start the OpenEnv FastAPI Server natively using Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
