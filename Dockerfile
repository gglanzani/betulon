FROM python:3.11-alpine3.18

WORKDIR /usr/src/app

COPY . .

RUN pip install --no-cache-dir -e .

CMD ["betulon"] 
