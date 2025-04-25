#!/usr/bin/env python3
"""
MySQL MCP Server in Python

This MCP server provides access to MySQL databases using the Model Context Protocol (MCP).
It allows:
- Connecting to a MySQL database
- Listing tables in a database
- Describing table schemas
- Executing read-only SQL queries
"""

import os
import logging
from typing import Dict, Any, Optional
from mysql.connector import connect, Error, pooling
from pythonjsonlogger import jsonlogger
from mcp.server.fastmcp import FastMCP
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

# Configure logging
logger = logging.getLogger()
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# Default configuration
DEFAULT_CONFIG = {
    'host': os.environ.get('MYSQL_HOST', 'localhost'),
    'port': int(os.environ.get('MYSQL_PORT', 3306)),
    'user': os.environ.get('MYSQL_USER'),
    'password': os.environ.get('MYSQL_PASSWORD'),
    'database': os.environ.get('MYSQL_DATABASE'),
    'row_limit': int(os.environ.get('ROW_LIMIT', 1000)),
    'query_timeout': int(os.environ.get('QUERY_TIMEOUT', 10000)) / 1000,
    'pool_size': int(os.environ.get('POOL_SIZE', 10))
}

# Create MCP server instance
mcp = FastMCP("MySQL Database Explorer")

@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Manage server startup and shutdown lifecycle."""
    # Initialize MySQL connection pool
    config = {
        'host': DEFAULT_CONFIG['host'],
        'port': DEFAULT_CONFIG['port'],
        'user': DEFAULT_CONFIG['user'],
        'password': DEFAULT_CONFIG['password'],
        'database': DEFAULT_CONFIG['database'],
        'pool_size': DEFAULT_CONFIG['pool_size']
    }
    
    try:
        pool = pooling.MySQLConnectionPool(
            pool_name="mysql_pool",
            **config
        )
        logger.info(f"Connected to MySQL at {config['host']}:{config['port']}")
        yield {"pool": pool}
    finally:
        # Cleanup
        if 'pool' in locals():
            pool.close()
            logger.info("Database connection pool closed")

# Set up server with lifespan
mcp.set_lifespan(server_lifespan)

@mcp.resource("schema://{database}")
async def get_schema(database: str) -> str:
    """Get the schema of a database"""
    ctx = mcp.request_context
    pool = ctx.lifespan_context["pool"]
    
    with pool.get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(f"USE `{database}`")
        cursor.execute("""
            SELECT 
                TABLE_NAME, 
                COLUMN_NAME,
                COLUMN_TYPE,
                IS_NULLABLE,
                COLUMN_KEY,
                COLUMN_DEFAULT,
                EXTRA
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = %s
            ORDER BY TABLE_NAME, ORDINAL_POSITION
        """, (database,))
        schema = cursor.fetchall()
        
        return "\n".join(
            f"Table {row['TABLE_NAME']}: {row['COLUMN_NAME']} ({row['COLUMN_TYPE']}) "
            f"{'NOT NULL ' if row['IS_NULLABLE'] == 'NO' else ''}"
            f"{'PRIMARY KEY ' if row['COLUMN_KEY'] == 'PRI' else ''}"
            f"{'AUTO_INCREMENT ' if 'auto_increment' in row['EXTRA'].lower() else ''}"
            for row in schema
        )

@mcp.tool()
async def list_databases() -> Dict[str, Any]:
    """List all accessible databases"""
    ctx = mcp.request_context
    pool = ctx.lifespan_context["pool"]
    
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SHOW DATABASES")
        databases = cursor.fetchall()
        return {
            "success": True,
            "databases": [db[0] for db in databases]
        }

@mcp.tool()
async def list_tables(database: Optional[str] = None) -> Dict[str, Any]:
    """List all tables in a database"""
    ctx = mcp.request_context
    pool = ctx.lifespan_context["pool"]
    
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        if database:
            cursor.execute(f"USE `{database}`")
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        return {
            "success": True,
            "tables": [table[0] for table in tables]
        }

@mcp.tool()
async def describe_table(table: str, database: Optional[str] = None) -> Dict[str, Any]:
    """Describe a table schema"""
    ctx = mcp.request_context
    pool = ctx.lifespan_context["pool"]
    
    with pool.get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        if database:
            cursor.execute(f"USE `{database}`")
        cursor.execute(f"DESCRIBE `{table}`")
        columns = cursor.fetchall()
        return {
            "success": True,
            "columns": columns
        }

@mcp.tool()
async def execute_query(query: str, database: Optional[str] = None) -> Dict[str, Any]:
    """Execute a read-only SQL query"""
    ctx = mcp.request_context
    pool = ctx.lifespan_context["pool"]
    
    # Validate query is read-only
    normalized = query.strip().upper()
    if not any(normalized.startswith(cmd) for cmd in ['SELECT', 'SHOW', 'DESCRIBE', 'EXPLAIN']):
        return {
            "success": False,
            "error": "Only SELECT, SHOW, DESCRIBE, and EXPLAIN queries are allowed"
        }
    
    try:
        with pool.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            if database:
                cursor.execute(f"USE `{database}`")
            cursor.execute(query)
            rows = cursor.fetchall()
            
            # Apply row limit
            if len(rows) > DEFAULT_CONFIG['row_limit']:
                rows = rows[:DEFAULT_CONFIG['row_limit']]
                
            return {
                "success": True,
                "rows": rows,
                "rowCount": len(rows),
                "fields": [desc[0] for desc in cursor.description] if cursor.description else []
            }
    except Error as e:
        return {
            "success": False,
            "error": str(e)
        }

@mcp.prompt()
async def connect_database() -> str:
    """Create a prompt for connecting to a database"""
    return """Please help me connect to a MySQL database. I need to:
1. Specify the host, port, username, password, and database name
2. Test the connection
3. Start exploring the database schema and data"""

if __name__ == "__main__":
    mcp.run() 