# Use an official Python runtime as a parent image
FROM python:3.10-slim-bullseye

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies (incl. those required by Playwright's browsers)
COPY requirements.txt /app/requirements.txt
COPY unicrm/requirements.txt /app/unicrm/requirements.txt
# Update package list & install needed libs BEFORE fetching Playwright browsers
RUN apt-get update && apt-get install -y \
        wget curl netcat \
        # General runtime deps
        libcairo2 ffmpeg \
        # Playwright browser deps
        libnss3 libatk1.0-0 libatk-bridge2.0-0 libx11-xcb1 libxcb1 libxcomposite1 libxdamage1 \
        libxrandr2 libxss1 libxtst6 libgbm1 libgtk-3-0 libpango-1.0-0 libpangocairo-1.0-0 \
        libasound2 libdrm2 fonts-liberation libappindicator3-1 lsb-release xdg-utils \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r unicrm/requirements.txt

# RUN python -m playwright install --with-deps

# Copy the current directory contents into the container at /app
COPY . /app/

# Make port 80 available to the world outside this container
EXPOSE 80

CMD ["python", "manage.py", "runserver", "0.0.0.0:80"]
