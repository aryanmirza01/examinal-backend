# Use official Python image
FROM python:3.11

# Create a non-root user
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

# Copy your backend files into the container
COPY --chown=user . .

# Install the dependencies
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Use Railway's PORT environment variable (defaults to 8000 if not set)
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
