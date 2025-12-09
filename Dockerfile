FROM python:3.9-slim
RUN apt-get update && \
    apt-get install -y openjdk-17-jre-headless wget unzip android-sdk-libsparse-utils && \
    apt-get clean
WORKDIR /app
RUN wget https://bitbucket.org/iBotPeaches/apktool/downloads/apktool_2.9.3.jar -O /app/apktool.jar
RUN wget https://github.com/patrickfav/uber-apk-signer/releases/download/v1.3.0/uber-apk-signer-1.3.0.jar -O /app/uber-apk-signer.jar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
