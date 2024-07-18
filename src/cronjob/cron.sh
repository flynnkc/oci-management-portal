#!/bin/bash

# For use on a VM/Bare Metal server

crontab -l > cron
echo "0 0 * * * python3 update.py" >> cron
crontab cron
rm cron