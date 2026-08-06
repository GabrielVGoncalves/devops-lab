#!/bin/bash

# Install dependencies
pip3 install -f requirements.txt


# Create non-root user
sudo useradd --system --no-create-home --shell /sbin/nologin appuser



# Configure Firewall
#Enable Firewall 
sudo ufw enable
#Open ports (app,ssh,http)
sudo ufw allow 5001
sudo ufw allow 22
sudo ufw 80
