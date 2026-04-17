# 0. check
FROM python:3.14-alpine AS check

RUN apk add --no-cache bash nodejs npm

WORKDIR /src

COPY int/requirements*.txt ./int/

RUN pip install --no-cache-dir -r int/requirements.txt -r int/requirements-dev.txt

RUN npm install -g eslint@9.32 prettier@3.7 typescript@5.9
RUN ln -sf $(which ruff) /ruff && \
    ln -sf $(which mypy) /mypy && \
    ln -sf $(which eslint) /eslint && \
    ln -sf $(which prettier) /prettier

ENTRYPOINT ["bash"]


# 1. build
FROM python:3.14-alpine AS build
WORKDIR /app

COPY int/ ./int/

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r int/requirements.txt


# 2. build-test
FROM node:24-alpine AS build-test
WORKDIR /app/tester

COPY tester/ ./

RUN npm install
RUN npx tsc


# 3. runtime
FROM python:3.14-alpine AS runtime
WORKDIR /app

COPY --from=build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY --from=build /app/int/ ./int/

ENTRYPOINT ["python3", "int/src/solint.py"]


# 4. test
FROM runtime AS test

RUN apk add --no-cache nodejs npm
RUN pip install --no-cache-dir lark

ENV SOLINT="python3 /app/int/src/solint.py"

WORKDIR /app

COPY --from=build-test /app/tester/dist ./tester/dist
COPY --from=build-test /app/tester/package*.json ./tester/

WORKDIR /app/tester
RUN npm install --omit=dev

WORKDIR /app
ENTRYPOINT ["node", "tester/dist/tester.js"]