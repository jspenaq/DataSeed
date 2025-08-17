# Auto-Refresh Functionality Documentation

## Overview

The DataSeed dashboard includes robust auto-refresh functionality that automatically updates data at configurable intervals while respecting API rate limits and providing a smooth user experience.

## Features

### 1. **Auto-Refresh Toggle and Interval Selection**
- **Toggle Control**: Enable/disable auto-refresh functionality
- **Interval Options**: 15s, 30s, 1m, 5m, 10m
- **Default State**: OFF (users must explicitly enable)
- **Persistent Settings**: User preferences are maintained across sessions

### 2. **Efficient Caching with ETag Support**
- **ETag Headers**: Fully utilizes `ETag` and `If-None-Match` headers
- **304 Not Modified**: Handles server responses efficiently
- **Cache Management**: Automatic cache invalidation and refresh
- **Bandwidth Optimization**: Reduces unnecessary data transfer

### 3. **Rate Limiting and Exponential Backoff**
- **429 Detection**: Automatically detects rate limit responses
- **Exponential Backoff**: Doubles retry interval on each 429 response
- **Maximum Delay**: Caps at 60 seconds to prevent excessive waits
- **User Feedback**: Clear messaging about rate limit status
- **Auto-Pause**: Temporarily pauses auto-refresh during rate limiting

### 4. **State Management**
- **Session Persistence**: Settings maintained across page refreshes
- **Cross-Page Consistency**: Shared state between Overview and Analytics pages
- **Error Recovery**: Graceful handling of API failures
- **Status Tracking**: Real-time status indicators

## Implementation Details

### API Client Enhancements

The `DataSeedAPIClient` class includes:

```python
class DataSeedAPIClient:
    def __init__(self):
        self.base_retry_delay = 1.0
        self.max_retry_delay = 60.0
        # Rate limiting state in session
        
    def _check_rate_limit(self) -> Optional[float]:
        """Check if currently rate limited"""
        
    def _handle_rate_limit_response(self) -> float:
        """Handle 429 response with exponential backoff"""
        
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limiting status for UI"""
```

### State Management

Enhanced `RefreshState` dataclass:

```python
@dataclass
class RefreshState:
    enabled: bool = False
    interval_seconds: int = 300  # 5 minutes default
    last_refresh: Optional[datetime] = None
    next_refresh: Optional[datetime] = None
    is_paused: bool = False
    rate_limited: bool = False
    rate_limit_until: Optional[datetime] = None
```

### UI Components

The `render_auto_refresh_controls()` function provides:
- Toggle switch for enable/disable
- Interval selection dropdown
- Real-time countdown display
- Progress bars for visual feedback
- Rate limit status indicators
- Manual refresh button
- Pause/Resume controls

## Usage

### For Page Developers

Wrap your page content with the auto-refresh functionality:

```python
def render_my_page():
    state = get_dashboard_state()
    api_client = get_api_client()
    
    render_page_header(
        title="My Page",
        description="Page description",
        show_refresh=False  # Let wrapper handle refresh
    )
    
    render_auto_refresh_page_wrapper(
        page_content_func=render_my_page_content,
        page_title="My Page",
        state=state,
        api_client=api_client,
        key_prefix="my_page"
    )

def render_my_page_content():
    # Your actual page content here
    pass
```

### For Users

1. **Enable Auto-Refresh**: Use the sidebar toggle
2. **Set Interval**: Choose from predefined intervals
3. **Monitor Status**: Watch the countdown and progress indicators
4. **Handle Rate Limits**: System automatically pauses and shows wait time
5. **Manual Control**: Use manual refresh or pause/resume as needed

## Rate Limiting Behavior

### Normal Operation
- Requests include `If-None-Match` headers when ETags are available
- 304 responses use cached data without processing
- Successful responses reset rate limit counters

### Rate Limited (429 Response)
1. **First 429**: 1-second backoff
2. **Second 429**: 2-second backoff  
3. **Third 429**: 4-second backoff
4. **Continues**: Up to 60-second maximum
5. **Recovery**: Successful request resets to 1-second base delay

### User Experience During Rate Limiting
- Auto-refresh automatically pauses
- Clear error message with countdown
- Progress bar shows time remaining
- Manual refresh disabled during backoff
- Automatic resume when rate limit clears

## Error Handling

### API Errors
- **Network Issues**: Retry with exponential backoff
- **Rate Limiting**: Automatic pause and backoff
- **Server Errors**: Display user-friendly messages
- **Timeout**: Configurable timeout with retry logic

### State Recovery
- **Page Refresh**: Settings persist in session state
- **Browser Restart**: Settings reset to defaults
- **API Unavailable**: Graceful degradation with cached data

## Performance Considerations

### Bandwidth Optimization
- ETag-based caching reduces data transfer
- 304 responses minimize server processing
- Configurable intervals prevent excessive requests

### Memory Management
- Automatic cache expiration (5-minute TTL)
- Session state cleanup on errors
- Efficient data structures for state management

### User Experience
- Non-blocking refresh operations
- Visual feedback during operations
- Responsive UI during rate limiting

## Configuration

### Default Settings
```python
DEFAULT_INTERVAL = 300  # 5 minutes
DEFAULT_ENABLED = False  # Must be explicitly enabled
MAX_RETRY_DELAY = 60    # Maximum backoff delay
BASE_RETRY_DELAY = 1.0  # Starting backoff delay
```

### Available Intervals
- 15 seconds (for development/testing)
- 30 seconds (high-frequency monitoring)
- 1 minute (active monitoring)
- 5 minutes (default, balanced)
- 10 minutes (low-frequency updates)

## Testing

The implementation includes comprehensive tests:

```bash
python test_auto_refresh.py
```

Tests cover:
- Rate limiting logic and exponential backoff
- Refresh state management and timing
- Dashboard state persistence
- API error handling
- UI component functionality

## Troubleshooting

### Common Issues

**Auto-refresh not working**
- Check if enabled in sidebar
- Verify API connectivity
- Look for rate limiting messages

**Rate limiting too aggressive**
- Increase refresh interval
- Check API server configuration
- Monitor network conditions

**Settings not persisting**
- Verify session state is working
- Check for browser storage issues
- Restart dashboard if needed

### Debug Information

Enable debug logging to see:
- Rate limit state changes
- Cache hit/miss ratios
- API response times
- Refresh timing details

## Future Enhancements

Potential improvements:
- Smart interval adjustment based on data freshness
- User-configurable rate limit thresholds
- Advanced caching strategies
- Real-time WebSocket updates
- Cross-tab synchronization