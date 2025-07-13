FROM node:20-alpine AS build
ENV VITE_CLICKHOUSE_SELFSERVICE="true"
WORKDIR /app
RUN apk add git
RUN git clone -b patch-1 https://github.com/lmangani/ch-ui /app
RUN npm install -g pnpm
RUN npx update-browserslist-db@latest
RUN npm install && npm run build

FROM python:3.10.18-slim
WORKDIR /app
ENV VITE_CLICKHOUSE_SELFSERVICE="true"
ADD requirements.txt .
RUN apt update && apt install -y binutils wget \
  && pip install -r requirements.txt \
  && strip /usr/local/lib/python3.10/site-packages/chdb/_chdb.cpython-*-*-linux-gnu.so \
  && rm -rf /var/lib/apt/lists/* && rm -rf ~/.cache/pip/*
ADD main.py .
# ADD public ./public
COPY --from=build /app/dist ./public
EXPOSE 8123
CMD ["python3","./main.py"]
