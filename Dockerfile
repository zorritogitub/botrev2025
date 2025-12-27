FROM python:3.9-slim-bullseye
COPY ..

RUN pip3 install -r requirements.txt

RUN apt update; apt-get install -yy apache2

CMD ["bash","run.sh"]

EXPOSE 10000
