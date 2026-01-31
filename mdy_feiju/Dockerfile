FROM python:3.10-slim

WORKDIR /app

# Install system dependencies if needed (e.g. for Pillow or numpy)
# RUN apt-get update && apt-get install -y ...

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose port
EXPOSE 8080

# Command to run the bot
CMD ["nb", "run"]
