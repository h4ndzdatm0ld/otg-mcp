# Use Python image as the base
FROM python:3.11-slim

# Install Node.js for better HTML parsing 
RUN apt-get update && apt-get install -y \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the project files
COPY . .

# Install project in development mode
RUN pip install -e .

# Expose port for the MCP server (default for most MCP servers)
EXPOSE 3000

# Run the MCP server
CMD ["python", "-m", "otg_mcp"]
