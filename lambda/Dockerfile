ARG FUNCTION_DIR="/function"

FROM python:3.11 as build-image

ARG FUNCTION_DIR

RUN mkdir -p ${FUNCTION_DIR}
COPY lambda.py ${FUNCTION_DIR}
COPY requirements.txt ${FUNCTION_DIR}

RUN pip install --target ${FUNCTION_DIR} -r "${FUNCTION_DIR}/requirements.txt"
RUN pip install --target ${FUNCTION_DIR} awslambdaric

FROM python:3.11-slim

ARG FUNCTION_DIR
WORKDIR ${FUNCTION_DIR}

COPY --from=build-image ${FUNCTION_DIR} ${FUNCTION_DIR}

ENTRYPOINT [ "/usr/local/bin/python", "-m", "awslambdaric" ]
CMD [ "lambda.handler" ]
