FROM python:3.11-alpine3.18

WORKDIR /usr/src/app

COPY pyproject.toml .
COPY src .

RUN mkdir logs
RUN mkdir database
RUN mkdir state

RUN pip install --no-cache-dir -e .

CMD ["betulon"] 

