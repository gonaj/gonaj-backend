#!/bin/bash
# Helper script to set USER_ID and GROUP_ID for docker-compose
# Run this before `docker compose up` to match your host user

export USER_ID=$(id -u)
export GROUP_ID=$(id -g)

echo "USER_ID=${USER_ID}"
echo "GROUP_ID=${GROUP_ID}"

# Update .env file if it exists
if [ -f .env ]; then
    # Remove old USER_ID and GROUP_ID lines
    sed -i '/^USER_ID=/d' .env
    sed -i '/^GROUP_ID=/d' .env
    
    # Append new values
    echo "USER_ID=${USER_ID}" >> .env
    echo "GROUP_ID=${GROUP_ID}" >> .env
    
    echo "✓ Updated .env with your host user IDs"
fi
