"""
Main entry point for the MCP server using FastMCP.
"""
import os
import logging
import shutil
import sys
import uuid
from dotenv import load_dotenv
from fastmcp import FastMCP
import chardet
from MetadataReturner import MetadataReturner

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s')
logger = logging.getLogger(__name__)

logger.info("Begin logger...")

# Load environment variables
logger.info("Env Loading...")
load_dotenv()
logger.info("Env Loaded...")

# --- Configuration from Environment Variables ---
USESSE = os.getenv("USESSE", "false").lower() == "true"

# Initialize MetadataReturner (no file arguments needed)
metadata_returner = MetadataReturner()


# Initialize FastMCP server at module level
mcp = FastMCP()
logger.info("FastMCP server initialized...")

# Register tools
@mcp.tool()
def metadatasearch(query: str, find_usages: bool = False, limit: int = 5, config: str = None):
    """Search metadata files of 1C configuration. Example: 'Справочники.Номенклатура'. 
    If find_usages is False (default), returns the matched objects with their full hierarchy directly. 
    If True, it finds where these objects are used in other parts of the metadata tree.
    Limit is the maximum number of objects to return. Default is 5.""" 
    result = metadata_returner.search_metadata(query, find_usages=find_usages, limit=limit, config=config)
    return result


if __name__ == "__main__":
    transport = "sse" if USESSE else "streamable-http"
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8000"))
    path = os.getenv("MCP_PATH", "/mcp")
    
    logger.info(f"Starting MCP server with transport={transport}, host={host}, port={port}, path={path}")
    mcp.run(transport=transport, host=host, port=port, path=path)