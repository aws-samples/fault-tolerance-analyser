FROM python:3.9

RUN apt-get update -y
#RUN apt-get install -y python-pip python-dev build-essential

COPY ./src/requirements.txt /src/

WORKDIR /src
RUN pip install --no-cache-dir -r requirements.txt

COPY ./src/*.py /src/
COPY ./src/service_specific_analysers/ /src/service_specific_analysers/

ENTRYPOINT ["python3", "./account_resiliency_analyser.py"]
