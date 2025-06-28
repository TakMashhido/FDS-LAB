# Use a standard Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container to /code
WORKDIR /code

# Copy the dependencies file to the working directory
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app directory into the working directory
COPY app/ ./app/

# Tell Flask where to find the application
ENV FLASK_APP=app

# Force Python to print directly to the terminal without buffering
ENV PYTHONUNBUFFERED=1

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Define the command to run the app
CMD ["flask", "run", "--host=0.0.0.0"]