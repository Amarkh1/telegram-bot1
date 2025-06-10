#!/bin/bash
# Install system dependencies if needed
if [ ! -f /usr/bin/espeak ]; then
    apt-get update && apt-get install -y espeak espeak-data libespeak1 libespeak-dev ffmpeg
fi

# Start the bot
python test_webhook.py
