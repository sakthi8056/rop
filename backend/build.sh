#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "Upgrading pip..."
pip install --upgrade pip

echo "Installing project dependencies (with CPU PyTorch for cloud optimization)..."
pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
