# app/core/clients/mssql.py
import asyncio
from typing import Any, Dict, List, Optional, Tuple, Union

import pyodbc
from loguru import logger

from app.core.clients.base import IDatabaseClient
from app.core.config import Settings
from fastapi.concurrency import run_in_threadpool


class MSSQLClientError(Exception):
    """Base exception for MSSQL client errors."""
    pass


class MSSQLClient(IDatabaseClient):
    """Client for interacting with MS SQL Server database."""
    
    def __init__(self, settings: Settings):
        """
        Initialize the MS SQL client with connection settings.
        
        Args:
            settings: Application settings containing database connection details
        """
        try:
            logger.info("Initializing MSSQLClient...")
            self.settings = settings
            self.connection = None
            connection_params = [
                f"DRIVER={{{self.settings.DB_DRIVER}}}",
                f"SERVER={self.settings.DB_SERVER}",
                f"DATABASE={self.settings.DB_DATABASE}",
                "TrustServerCertificate=yes" # SSMS'te işaretli olduğu için ekledik
            ]

            # Windows Authentication mı SQL Authentication mı kontrolü
            if self.settings.DB_USERNAME and self.settings.DB_PASSWORD:
                # SQL Server Authentication
                logger.debug("Using SQL Server Authentication.")
                connection_params.append(f"UID={self.settings.DB_USERNAME}")
                connection_params.append(f"PWD={self.settings.DB_PASSWORD}")
            else:
                # Windows Authentication (Kullanıcı adı/şifre .env'de boşsa)
                logger.debug("Using Windows Authentication (Trusted Connection).")
                connection_params.append("Trusted_Connection=yes")

            self.connection_string = ";".join(connection_params)

            log_conn_str = ";".join(p for p in connection_params if not p.startswith("PWD="))
            logger.debug(f"MSSQL Connection String prepared (password omitted): {log_conn_str}")
            
            logger.info(f"Initialized MSSQL client for server: {settings.DB_SERVER}, database: {settings.DB_DATABASE}")
        except Exception as e:
            logger.exception("Error initializing MSSQLClient: {}", e)
            raise ConnectionError(f"MSSQLClient initialization failed: {e}") from e
    
    async def connect(self) -> None:
        """
        Establish a connection to the MS SQL database asynchronously.
        
        Raises:
            ConnectionError: If unable to connect to the database
            Exception: For any other errors during connection
        """
        try:
            if self.connection and not self.connection.closed:
                logger.debug("Already connected to database")
                return
            
            logger.info("Connecting to database...")
            # Since pyodbc is not async, use run_in_threadpool
            self.connection = await run_in_threadpool(
                lambda: pyodbc.connect(self.connection_string)
            )
            logger.info("Successfully connected to database")
            
        except pyodbc.Error as e:
            error_msg = f"Failed to connect to database: {str(e)}"
            logger.error(error_msg)
            raise ConnectionError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error connecting to database: {str(e)}"
            logger.error(error_msg)
            raise MSSQLClientError(error_msg)
    
    async def disconnect(self) -> None:
        """
        Close the database connection asynchronously.
        
        Raises:
            Exception: If there's an error during disconnection
        """
        try:
            if self.connection and not self.connection.closed:
                logger.info("Disconnecting from database...")
                # Since pyodbc is not async, use run_in_threadpool
                await run_in_threadpool(lambda: self.connection.close())
                self.connection = None
                logger.info("Successfully disconnected from database")
        except Exception as e:
            error_msg = f"Error disconnecting from database: {str(e)}"
            logger.error(error_msg)
            raise MSSQLClientError(error_msg)
    
    async def query_all(
        self, query: str, params: Optional[Union[List[Any], Dict[str, Any], Tuple[Any, ...]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a query and return all results as dictionaries.
        
        Args:
            query: SQL query string
            params: Query parameters for parameterized queries
            
        Returns:
            List of dictionaries representing query results
            
        Raises:
            ValueError: If the query is invalid
            ConnectionError: If the database connection is lost
            Exception: For any other database errors
        """
        if not self.connection or self.connection.closed:
            await self.connect()
        
        try:
            logger.debug(f"Executing query: {query}, with params: {params}")
            
            # Define an inner function to run in the threadpool
            def execute_query():
                cursor = self.connection.cursor()
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                # Get column names from cursor description
                columns = [column[0] for column in cursor.description]
                
                # Convert each row to a dictionary
                results = []
                for row in cursor.fetchall():
                    results.append(dict(zip(columns, row)))
                
                cursor.close()
                return results
            
            # Run the query in a threadpool since pyodbc is not async
            results = await run_in_threadpool(execute_query)
            logger.debug(f"Query returned {len(results)} results")
            return results
            
        except pyodbc.ProgrammingError as e:
            error_msg = f"Invalid SQL query: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        except pyodbc.OperationalError as e:
            error_msg = f"Database connection error: {str(e)}"
            logger.error(error_msg)
            # Ensure connection is marked as closed
            self.connection = None
            raise ConnectionError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected database error: {str(e)}"
            logger.error(error_msg)
            raise MSSQLClientError(error_msg)
    
    async def execute(
        self, query: str, params: Optional[Union[List[Any], Dict[str, Any], Tuple[Any, ...]]] = None
    ) -> int:
        """
        Execute a non-query SQL statement (INSERT, UPDATE, DELETE, etc).
        
        Args:
            query: SQL query string
            params: Query parameters for parameterized queries
            
        Returns:
            Number of affected rows
            
        Raises:
            ValueError: If the query is invalid
            ConnectionError: If the database connection is lost
            Exception: For any other database errors
        """
        if not self.connection or self.connection.closed:
            await self.connect()
        
        try:
            logger.debug(f"Executing statement: {query}, with params: {params}")
            
            # Define an inner function to run in the threadpool
            def execute_statement():
                cursor = self.connection.cursor()
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                # Get row count
                row_count = cursor.rowcount
                
                # Commit the transaction
                self.connection.commit()
                
                cursor.close()
                return row_count
            
            # Run the statement in a threadpool since pyodbc is not async
            affected_rows = await run_in_threadpool(execute_statement)
            logger.debug(f"Statement affected {affected_rows} rows")
            return affected_rows
            
        except pyodbc.ProgrammingError as e:
            error_msg = f"Invalid SQL statement: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        except pyodbc.OperationalError as e:
            error_msg = f"Database connection error: {str(e)}"
            logger.error(error_msg)
            # Ensure connection is marked as closed
            self.connection = None
            raise ConnectionError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected database error: {str(e)}"
            logger.error(error_msg)
            raise MSSQLClientError(error_msg)
