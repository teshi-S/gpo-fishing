#!/bin/bash

# Script to install necessary packages for GPO Fishing on Manjaro/Arch Linux

# Update package lists
sudo pacman -Syu

# Install necessary packages
sudo pacman -S git
sudo pacman -S python python-pip
sudo pacman -S nodejs npm
# Add any additional packages needed

# Clean up
sudo pacman -Rns $(pacman -Qtdq) 

echo "Installation complete!"