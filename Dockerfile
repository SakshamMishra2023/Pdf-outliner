# Use official slim Python image
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Copy script and PDF file to container
COPY tx.py sample.pdf ./

# Install required Python package
RUN pip install --no-cache-dir pdfminer.six

# Run the script on container start
CMD ["python", "tx.py"]
