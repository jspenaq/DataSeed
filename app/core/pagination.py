import base64
import binascii
import json
from datetime import datetime
from typing import Tuple


def encode_cursor(published_at: datetime, item_id: int) -> str:
    """
    Encode a cursor from published_at datetime and item_id.
    
    Args:
        published_at: The published_at datetime of the item
        item_id: The ID of the item
        
    Returns:
        Base64-encoded cursor string
    """
    cursor_data = {
        "p": published_at.isoformat(),
        "i": item_id
    }
    cursor_json = json.dumps(cursor_data, separators=(',', ':'))
    cursor_bytes = cursor_json.encode('utf-8')
    return base64.b64encode(cursor_bytes).decode('ascii')


def decode_cursor(cursor: str) -> Tuple[datetime, int]:
    """
    Decode a cursor string to get published_at datetime and item_id.
    
    Args:
        cursor: Base64-encoded cursor string
        
    Returns:
        Tuple of (published_at, item_id)
        
    Raises:
        ValueError: If cursor is invalid or malformed
    """
    try:
        cursor_bytes = base64.b64decode(cursor.encode('ascii'))
        cursor_json = cursor_bytes.decode('utf-8')
        cursor_data = json.loads(cursor_json)
        
        published_at = datetime.fromisoformat(cursor_data["p"])
        item_id = cursor_data["i"]
        
        return published_at, item_id
        
    except (binascii.Error, json.JSONDecodeError, KeyError, ValueError) as e:
        raise ValueError(f"Invalid cursor format: {e}")