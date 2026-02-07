FROM python:3.10-slim

WORKDIR /app

# Install system dependencies if needed (e.g. for Pillow or numpy)
RUN apt-get update && apt-get install -y build-essential libexpat1 ffmpeg libgl1 libglib2.0-0 fontconfig --no-install-recommends && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir numpy
RUN pip install --no-cache-dir -r requirements.txt

# Download Spacy English model for lemmatization
RUN python -m spacy download en_core_web_sm

COPY . .

# Expose port
EXPOSE 8080

# Command to run the bot
CMD ["sh", "-c", "nb orm upgrade && nb run"]
