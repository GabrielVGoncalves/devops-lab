#Import python image
FROM python:slim

COPY requirements.txt /
RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get update && apt-get upgrade -y

#Import the code to the image
COPY app.py /
COPY test_db.py /

#Expose port 5001
EXPOSE 5001

#Command to run the app 
CMD ["python3", "./app.py"]