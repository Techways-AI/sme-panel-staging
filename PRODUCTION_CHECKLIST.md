# Production Deployment Checklist

## ⚠️ CRITICAL: Pre-Deployment Requirements

### 1. Environment Variables (REQUIRED)
Ensure all these are set in your production environment (Railway/Vercel/etc.):

#### Required Variables:
- ✅ `ENV=production`
- ✅ `JWT_SECRET_KEY` - Strong random secret (minimum 32 characters)
- ✅ `CORS_ORIGINS` - Comma-separated list of allowed frontend URLs (e.g., `https://yourdomain.com,https://www.yourdomain.com`)
- ✅ `DATABASE_URL` - PostgreSQL connection string

#### Recommended Variables:
- ✅ `OPENAI_API_KEY` OR `GOOGLE_API_KEY` - At least one AI provider key
- ✅ `AWS_ACCESS_KEY_ID` - For S3 file storage
- ✅ `AWS_SECRET_ACCESS_KEY` - For S3 file storage
- ✅ `S3_BUCKET_NAME` - S3 bucket name
- ✅ `AWS_REGION` - AWS region (default: `ap-south-1`)

#### Optional Variables:
- `ACCESS_TOKEN_EXPIRE_MINUTES` - JWT token expiration (default: 1440 = 24 hours)
- `MAX_FILE_SIZE` - Max upload size in bytes (default: 10485760 = 10MB)
- `LOG_LEVEL` - Logging level (default: INFO in production)
- `AI_PROVIDER` - `openai` or `google` (default: `google`)
- `CHAT_MODEL` - Model name to use
- `EMBEDDING_MODEL` - Embedding model name

### 2. Security Checklist

#### ✅ Fixed Issues:
- [x] Error messages no longer expose sensitive details in production
- [x] Debug/test endpoints disabled in production (`/test`, `/cors-test`, `/auth-test`, `/debug/routes`, `/test-cors`, `/test-error`)
- [x] Security headers added (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, HSTS)
- [x] CORS configuration requires environment variable in production
- [x] Hardcoded credentials removed from documentation

#### ⚠️ Still Need to Verify:
- [ ] All secrets are in environment variables (not in code)
- [ ] Database credentials are secure and rotated
- [ ] API keys are valid and have proper rate limits
- [ ] S3 bucket has proper IAM permissions (read/write only where needed)
- [ ] HTTPS is enabled (production URLs should use `https://`)
- [ ] CORS origins only include your production frontend URLs

### 3. Database Setup

- [ ] Database migrations run successfully
- [ ] Database connection string is correct
- [ ] Database has proper backups configured
- [ ] Database user has minimal required permissions

### 4. Frontend Configuration

- [ ] `NEXT_PUBLIC_API_URL` points to production backend URL
- [ ] Frontend is built for production (`npm run build`)
- [ ] Environment variables are set in deployment platform
- [ ] CORS origins in backend match frontend URL

### 5. Testing Checklist

Before deploying, test:
- [ ] Health check endpoint: `GET /health`
- [ ] Authentication: Login and token generation
- [ ] Document upload and processing
- [ ] AI chat functionality
- [ ] File storage (S3) operations
- [ ] Error handling (should not expose stack traces)

### 6. Monitoring & Logging

- [ ] Logging is configured and working
- [ ] Error tracking is set up (if using service like Sentry)
- [ ] Application logs are accessible
- [ ] Health check monitoring is configured

### 7. Performance

- [ ] File upload size limits are appropriate
- [ ] Rate limiting is configured (if needed)
- [ ] Database connection pooling is configured
- [ ] Static assets are optimized

## 🚀 Deployment Steps

1. **Set Environment Variables** in your deployment platform
2. **Verify CORS_ORIGINS** includes your production frontend URL
3. **Deploy Backend** (Railway/Heroku/etc.)
4. **Deploy Frontend** (Vercel/Netlify/etc.)
5. **Test Health Endpoint**: `https://your-api.com/health`
6. **Test Authentication**: Login from frontend
7. **Monitor Logs** for any errors

## 🔒 Security Best Practices

1. **Never commit** `.env` files or secrets to version control
2. **Rotate secrets** regularly (especially JWT_SECRET_KEY)
3. **Use HTTPS** for all production URLs
4. **Limit CORS origins** to only your production domains
5. **Monitor** for suspicious activity
6. **Keep dependencies** up to date
7. **Review logs** regularly for errors

## ⚠️ Known Issues Fixed

- ✅ Error messages now hide details in production
- ✅ Debug endpoints disabled in production
- ✅ Security headers added
- ✅ CORS validation improved
- ✅ Hardcoded credentials removed from docs

## 📝 Post-Deployment

After deployment:
1. Monitor application logs for 24-48 hours
2. Test all critical user flows
3. Verify file uploads work correctly
4. Check AI chat functionality
5. Monitor error rates
6. Verify database connections are stable

## 🆘 Troubleshooting

### CORS Errors
- Verify `CORS_ORIGINS` environment variable includes your frontend URL
- Check that frontend URL matches exactly (including `https://` and port if any)
- Ensure `CORS_ALLOW_ALL` is NOT set to `true` in production

### Database Connection Errors
- Verify `DATABASE_URL` is correct
- Check database is accessible from deployment platform
- Verify SSL mode if required

### Authentication Errors
- Verify `JWT_SECRET_KEY` is set and strong
- Check token expiration settings
- Verify frontend is sending tokens correctly

### File Upload Errors
- Verify S3 credentials are correct
- Check S3 bucket permissions
- Verify `MAX_FILE_SIZE` is appropriate

## 📞 Support

If you encounter issues:
1. Check application logs
2. Verify all environment variables are set
3. Test health endpoint: `/health`
4. Review error messages (but they won't expose sensitive details in production)

