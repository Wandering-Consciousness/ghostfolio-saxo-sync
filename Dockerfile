FROM python:3.11-alpine

# Install system dependencies
RUN apk add --no-cache \
    dumb-init \
    dcron \
    bash \
    ca-certificates \
    && rm -rf /var/cache/apk/*

# Set working directory
WORKDIR /root

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY main.py .
COPY SyncSaxo.py .
COPY saxo_oauth.py .
COPY mapping.yaml .
COPY entrypoint.sh .
COPY run.sh .
COPY .env .env

# Make scripts executable
RUN chmod +x /root/entrypoint.sh /root/run.sh

# Use dumb-init to handle signals properly
ENTRYPOINT ["/usr/bin/dumb-init", "--"]

# Run with timestamped logging
CMD /root/entrypoint.sh | while IFS= read -r line; do printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$line"; done
