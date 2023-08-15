# Start from the official Python base image.
FROM python:3.10

WORKDIR /code
ENV PYTHONPATH=${PYTHONPATH}:${PWD}


COPY ./pyproject.toml /code/
RUN pip3 install poetry
RUN poetry config virtualenvs.create false
RUN poetry install --no-dev

COPY ./templates /code/templates
COPY ./auth_server /code/auth_server
COPY ./main.py /code/main.py

CMD ["poetry", "run", "python", "main.py"]
