#!/usr/bin/env python3
"""
Data Catalog Web Application
Main entry point for the Flask application
"""

from backend.app import create_app
import os

# Create Flask application
app = create_app()

if __name__ == '__main__':
    # Development server
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=app.config.get('DEBUG', False)
    )