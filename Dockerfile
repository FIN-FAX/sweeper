# pull official base image
FROM python:3.9.5-slim-buster as builder

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install system dependencies
RUN apt-get update && apt-get install -y netcat

RUN pip install pyarmor

# Copy application source code
COPY . .

# Obfuscate Python code
# RUN pyarmor obfuscate -e " --exclude tests --exclude venv --exclude __pycache__  --exclude Dockerfile --exclude requirements.txt --exclude entrypoint.sh" app.py
RUN pyarmor-7 obfuscate src/app.py
RUN ls -al /usr/src/app/dist/

# Start a new stage from a slim version to keep the final image clean and small
FROM python:3.9.5-slim-buster

RUN apt-get update -y && apt-get upgrade -y
WORKDIR /usr/src/app
RUN rm -rf /usr/src/app/src/*
COPY --from=builder /usr/src/app/dist /usr/src/app/src
RUN ls -al /usr/src/app/src/

RUN mkdir -p /usr/src/inbox/
RUN mkdir -p /usr/src/outbox/
RUN mkdir -p /usr/src/thumbnails/

# install dependencies
RUN pip install --upgrade pip
COPY ./requirements.txt ./requirements.txt
COPY ./entrypoint.sh ./entrypoint.sh
RUN pip install -r requirements.txt
RUN rm requirements.txt



# run entrypoint.sh
ENTRYPOINT ["/usr/src/app/entrypoint.sh"]