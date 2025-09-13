#!/bin/bash

# cSpell:ignore getent appgroup appuser gosu

# Ko-Merge Backend Entrypoint Script
# Handles user creation and permissions for Unraid compatibility

set -e

# Default values for PUID and PGID (Unraid defaults)
PUID=${PUID:-99}
PGID=${PGID:-100}

echo "Starting Ko-Merge Backend with PUID=$PUID and PGID=$PGID"

# Create group if it doesn't exist
if ! getent group $PGID > /dev/null 2>&1; then
    echo "Creating group with GID $PGID"
    groupadd -g $PGID appgroup
else
    echo "Group with GID $PGID already exists"
fi

# Create user if it doesn't exist
if ! getent passwd $PUID > /dev/null 2>&1; then
    echo "Creating user with UID $PUID"
    useradd -u $PUID -g $PGID -d /app -s /bin/bash appuser
else
    echo "User with UID $PUID already exists"
fi

# Ensure data directory exists and has correct permissions
echo "Setting up data directory permissions"
mkdir -p /app/data/uploads /app/data/processed /app/data/covers
chown -R $PUID:$PGID /app/data
chmod -R 777 /app/data

# Set ownership of application files
echo "Setting application file ownership"
chown -R $PUID:$PGID /app

# Switch to the specified user and execute the command
echo "Switching to user $PUID and starting application"
exec gosu $PUID:$PGID "$@"
