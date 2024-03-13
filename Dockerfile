FROM python:3.8.10-slim
ENV VERSION 0.14.2
WORKDIR /app
ADD requirements.txt .
RUN apt update && apt install -y binutils \
  && pip install -r requirements.txt \
  && strip /usr/local/lib/python3.8/site-packages/chdb/_chdb.cpython-38-*-linux-gnu.so \
  && rm -rf /var/lib/apt/lists/* && rm -rf ~/.cache/pip/*
ADD main.py .
ADD public ./public
EXPOSE 8123
CMD ["python3","./main.py"]
