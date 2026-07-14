# 1. Use official Python lightweight image for smaller size
FROM python:3.12-slim

# 2. Set environment variables to optimize Python behavior
# Prevents Python from writing .pyc files to disk
ENV PYTHONDONTWRITEBYTECODE=1
# Ensures Python output is logged immediately without buffering
ENV PYTHONUNBUFFERED=1

# 3. Set the working directory inside the container
WORKDIR /app

# 4. Copy ONLY the requirements file first to leverage Docker layer caching
COPY requirements.txt .

# 5. Install dependencies using Chabokan mirror (No cache to keep image small)
RUN pip install --no-cache-dir --index-url https://mirror2.chabokan.net/pypi/simple/ -r requirements.txt

# 6. Copy the rest of the application code
COPY . .

# 7. Expose the port FastAPI will run on
EXPOSE 8000

# 8. Command to run the application using Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
