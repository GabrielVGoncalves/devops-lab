
# Open the file and include the lines with string ERROR on it to the list $errors
with open("logs/app.log") as f:
    errors = [linha for linha in f if "ERROR" in linha ]
# Print the total of errors
print(f"Total errors: {len(errors)}")

# List all the logs from the list errors
for e in errors:
    print(e.strip())


# Open the file and include the lines with string INFO on it to the list $
with open("logs/app.log") as f:
    success = [line for line in f if "INFO" in line]
# Print the total success
print(f"Total success {len(success)}")

# List all the logs from the list success
for i in success:
    print(i.strip())
