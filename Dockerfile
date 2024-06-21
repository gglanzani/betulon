FROM python:3.11-alpine3.18

WORKDIR /usr/src/app

COPY pyproject.toml .
COPY src .

RUN pip install --no-cache-dir -e .

RUN mkdir logs
RUN mkdir database
RUN mkdir state


CMD ["betulon"] 

