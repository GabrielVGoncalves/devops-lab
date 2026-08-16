#Import python image
FROM python3:latest

COPY requirements.txt /
RUN pip install --no-cache-dir -r requirements.txt

#Import the code to the image
COPY app.py /

#Expose port 5001
EXPOSE 5001

#Command to run the app 
CMD ["python3", "./app.py"]

