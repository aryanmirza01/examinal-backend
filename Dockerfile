# Use official Python image
FROM python:3.9

# Create a non-root user for Hugging Face security
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

# Copy your backend files into the container
COPY --chown=user . .

# Install the dependencies
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Hugging Face Spaces uses port 7860 by default
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
