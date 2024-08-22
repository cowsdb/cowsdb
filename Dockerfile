FROM python:3.8.10-slim
WORKDIR /app
ADD requirements.txt .
RUN apt update && apt install -y binutils wget \
  && pip install -r requirements.txt \
#  && pip install Flask flask_httpauth \
#  && wget https://github.com/chdb-io/chdb/releases/download/v2.0.0b1/chdb-2.0.0b1-cp38-cp38-manylinux_2_5_x86_64.manylinux1_x86_64.manylinux_2_17_x86_64.manylinux2014_x86_64.whl -P /tmp/ \
#  && pip install /tmp/*.whl \
  && strip /usr/local/lib/python3.8/site-packages/chdb/_chdb.cpython-38-*-linux-gnu.so \
  && rm -rf /var/lib/apt/lists/* && rm -rf ~/.cache/pip/*
ADD main.py .
ADD public ./public
EXPOSE 8123
CMD ["python3","./main.py"]
