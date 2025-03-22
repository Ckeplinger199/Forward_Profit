"""
Launch script for the Forward Profit Trading Bot Gradio interface.
Run this script to start the interface.
"""

import gradio as gr
import sys
import os
import logging
from threading import Thread
import argparse
import socket

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("interface_launcher.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("launcher")

def is_port_in_use(port):
    """Check if a port is in use"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def find_available_port(start_port, max_attempts=10):
    """Find an available port starting from start_port"""
    port = start_port
    for _ in range(max_attempts):
        if not is_port_in_use(port):
            return port
        port += 1
    raise RuntimeError(f"Could not find an available port after {max_attempts} attempts")

def main():
    parser = argparse.ArgumentParser(description="Launch Forward Profit Trading Bot Gradio Interface")
    parser.add_argument("--port", type=int, default=7860, help="Port to run the Gradio interface on")
    parser.add_argument("--share", action="store_true", help="Create a public link for sharing")
    parser.add_argument("--no-pwa", action="store_true", help="Disable Progressive Web App functionality")
    parser.add_argument("--force-port", action="store_true", help="Force using the specified port even if it fails")
    parser.add_argument("--auto-start", action="store_true", help="Automatically initialize and start the trading bot")
    args = parser.parse_args()
    
    try:
        # Check if port is already in use
        port = args.port
        if not args.force_port and is_port_in_use(port):
            logger.warning(f"Port {port} is already in use. Finding an available port...")
            port = find_available_port(port)
            logger.info(f"Using available port: {port}")
        
        # Import gradio interface
        from gradio_interface import create_gradio_interface, initialize_bot, start_bot
        
        # Create interface
        app = create_gradio_interface()
        
        # Enable PWA by default unless explicitly disabled
        enable_pwa = not args.no_pwa
        
        # Auto-start the bot if requested
        if args.auto_start:
            logger.info("Auto-starting trading bot...")
            initialize_bot()
            start_bot()
        
        logger.info(f"Starting Gradio interface on port {port} (share={args.share}, pwa={enable_pwa})")
        app.launch(server_port=port, share=args.share, show_error=True, pwa=enable_pwa)
        
    except Exception as e:
        logger.error(f"Error launching interface: {e}")
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("Launching Forward Profit Trading Bot Interface...")
    main()
