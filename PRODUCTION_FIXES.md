# Production AI Ask Endpoint Fixes

## Issues Identified

Based on the terminal logs showing successful local operation but failures in production, the following issues were identified:

### 1. **Silent Failures in S3 Downloads** (CRITICAL)
**Problem**: The `download_all_vectorstore_files()` function was catching all exceptions and silently returning without raising errors. This meant:
- If S3 access failed, the function would just return without downloading files
- The calling code (`load_vector_store`) wouldn't know that downloads failed
- The code would continue and fail later with unclear error messages

**Location**: `api/app/utils/s3_utils.py:397-439`

**Fix**: 
- Added proper error propagation with detailed error messages
- Added check for S3 availability before attempting downloads
- Added validation to ensure essential files are downloaded
- Now raises exceptions with clear error messages instead of silently failing

### 2. **Missing Error Context** (HIGH)
**Problem**: When errors occurred, they were logged but not properly propagated with context, making debugging difficult in production.

**Location**: `api/app/utils/vector_store.py:72-143`

**Fix**:
- Improved error messages with more context (doc_id, file paths, sizes)
- Added proper exception chaining to preserve error context
- Added detailed logging at each step
- Now raises exceptions instead of returning None on failure

### 3. **Incomplete Error Handling in Cache Function** (MEDIUM)
**Problem**: The `get_cached_vector_store()` function wasn't properly handling errors from `load_vector_store()`, making it difficult to diagnose issues.

**Location**: `api/app/routers/ai.py:2673-2722`

**Fix**:
- Added proper exception handling and propagation
- Added validation of cached vector stores before returning
- Improved error messages with full tracebacks
- Now properly raises exceptions to allow caller to handle appropriately

## Common Production Issues to Check

### Environment Variables
Ensure these are set correctly in production:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION` (must not be empty)
- `S3_BUCKET_NAME`
- `GOOGLE_API_KEY` or `OPENAI_API_KEY` (depending on provider)

### S3 Permissions
Ensure the AWS credentials have:
- `s3:GetObject` permission for the vector store files
- `s3:ListBucket` permission for the bucket
- Access to the correct S3 bucket and region

### Network/Timeout Issues
- Production environments may have slower network connections
- Consider increasing timeout values if needed
- Check firewall rules allow S3 access

### Temporary Directory Issues
- Some production environments (like Railway, Heroku) have ephemeral filesystems
- Temporary directories are cleaned up automatically
- Ensure sufficient disk space for vector store downloads

### Memory Limits
- Loading multiple vector stores simultaneously can consume significant memory
- Monitor memory usage in production
- Consider implementing memory limits or cleanup strategies

## Testing the Fixes

1. **Check S3 Access**:
   ```python
   # The code will now raise clear errors if S3 is not accessible
   # Check logs for: "S3 is not available. Missing environment variables: ..."
   ```

2. **Check Downloads**:
   ```python
   # The code will now raise errors if downloads fail:
   # "Failed to download essential vector store files for doc_id=..."
   ```

3. **Check Vector Store Loading**:
   ```python
   # The code will now raise errors with full context:
   # "Failed to load vector store for doc_id=...: ..."
   ```

## Error Messages to Look For

### S3 Configuration Issues
- `"S3 is not available. Missing environment variables: ..."`
- `"S3 client is not available. Check AWS credentials and configuration."`
- `"AWS_REGION is required and cannot be empty."`

### Download Issues
- `"No vector store files found in S3 for doc_id=..."`
- `"Error listing vector store files in S3 for doc_id=..."`
- `"Failed to download essential vector store files for doc_id=..."`

### Loading Issues
- `"Essential vector store files missing after download for doc_id=..."`
- `"Vector store files are empty for doc_id=..."`
- `"Failed to load embeddings model: ..."`
- `"All loading strategies failed for doc_id=..."`

## Next Steps

1. Deploy the fixes to production
2. Monitor logs for the new error messages
3. Verify S3 credentials and permissions
4. Check that all environment variables are set correctly
5. Test with a simple question to verify the endpoint works

## Additional Recommendations

1. **Add Health Check Endpoint**: Create an endpoint that tests S3 connectivity
2. **Add Metrics**: Track vector store load times and failure rates
3. **Implement Retry Logic**: Add retry logic for transient S3 errors
4. **Add Circuit Breaker**: Prevent cascading failures if S3 is down
5. **Improve Caching**: Consider using Redis or similar for vector store caching in production

