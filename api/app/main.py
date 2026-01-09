from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.security import OAuth2PasswordBearer
import time
import os
from datetime import datetime
import json
import sys

from app.config.settings import (
    API_TITLE, API_VERSION, API_DESCRIPTION,
    CORS_ORIGINS, CORS_METHODS, CORS_HEADERS, CORS_MAX_AGE,
    DATA_DIR, VECTOR_STORES_DIR, VIDEOS_DIR, IS_PRODUCTION
)
from app.models.notes import Base
from app.models.model_paper_prediction import ModelPaperPrediction
from app.routers import (
    documents,
    videos,
    folders,
    ai,
    health,
    auth,
    model_papers,
    notes,
    model_paper_predictions,
    admin,
    admin_users,
    curriculum,
)
from app.routers.auth import get_current_user, oauth2_scheme

# Toggle verbose startup/router debug logs via env
ENABLE_DEBUG_LOGS = os.getenv("ENABLE_DEBUG_LOGS", "false").lower() == "true"

def debug_log(message: str):
    if ENABLE_DEBUG_LOGS:
        print(message)

# Create FastAPI app with enhanced OpenAPI configuration
app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION,
    docs_url="/docs",      # Enable Swagger docs
    redoc_url="/redoc",    # Enable ReDoc docs
    openapi_url="/openapi.json",  # Explicitly set OpenAPI JSON URL
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},  # Collapse models by default
)

# Startup event will be defined later with router registration

# Custom OpenAPI schema to include security scheme
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    # Add your custom security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "Bearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter JWT token in the format: Bearer <token>"
        }
    }
    openapi_schema["security"] = [{"Bearer": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Simple CORS configuration using FastAPI's built-in middleware
from fastapi.middleware.cors import CORSMiddleware

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request timing middleware
@app.middleware("http")
async def add_timing_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    
    # Add cache headers for GET requests to reduce redundant requests
    if request.method == "GET" and process_time < 1.0:  # Only cache fast responses
        response.headers["Cache-Control"] = "private, max-age=30"  # 30 second cache
    
    return response



# Simple global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    print(f"[ERROR] Unhandled exception: {str(exc)}")
    print(f"[ERROR] Exception type: {type(exc).__name__}")
    
    return JSONResponse(
        content={
            "detail": "Internal server error",
            "error_type": type(exc).__name__,
            "message": str(exc)
        },
        status_code=500
    )

# Handle HTTPException
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTPException"""
    print(f"[ERROR] HTTPException: {exc.status_code} - {exc.detail}")
    
    return JSONResponse(
        content={"detail": exc.detail},
        status_code=exc.status_code
    )

# Add error handling middleware
@app.middleware("http")
async def error_handling_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        error_id = f"ERR-{int(datetime.now().timestamp())}-{os.urandom(4).hex()}"
        
        # Log the error with more details
        print(f"[ERROR] {error_id}: {str(e)}")
        print(f"[ERROR] Request URL: {request.url}")
        print(f"[ERROR] Request method: {request.method}")
        print(f"[ERROR] Error type: {type(e).__name__}")
        
        # Import traceback for better error reporting
        import traceback
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        
        # Return a more informative error response
        error_detail = str(e) if not IS_PRODUCTION else "Internal server error"
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "error_id": error_id,
                "detail": error_detail,
                "timestamp": datetime.now().isoformat(),
                "path": str(request.url.path),
                "method": request.method
            }
        )

# Register routers directly with error handling
debug_log(f"[ROUTER_DEBUG] Starting router registration...")

try:
    debug_log(f"[ROUTER_DEBUG] Registering AI router...")
    from app.routers.ai import router as ai_router
    app.include_router(ai_router, prefix="")
    debug_log(f"[ROUTER_DEBUG] ✓ AI router registered successfully")
    
    # Verify the route was added
    ai_routes = [route for route in app.routes if hasattr(route, 'path') and '/api/ai' in route.path]
    debug_log(f"[ROUTER_DEBUG] AI routes found after registration: {len(ai_routes)}")
    for route in ai_routes:
        debug_log(f"[ROUTER_DEBUG]   {route.path} - {list(route.methods)}")
        
except Exception as e:
    print(f"[ROUTER_ERROR] Failed to register AI router: {str(e)}")
    print(f"[ROUTER_ERROR] Exception type: {type(e).__name__}")
    import traceback
    traceback.print_exc()

try:
    debug_log(f"[ROUTER_DEBUG] Registering other routers...")
    from app.routers.documents import router as documents_router
    from app.routers.videos import router as videos_router
    from app.routers.folders import router as folders_router
    from app.routers.health import router as health_router
    from app.routers.auth import router as auth_router
    from app.routers.model_papers import router as model_papers_router
    from app.routers.notes import router as notes_router
    from app.routers.model_paper_predictions import router as model_paper_predictions_router
    from app.routers.dashboard import router as dashboard_router
    from app.routers.curriculum import router as curriculum_router
    
    app.include_router(documents_router, prefix="")
    app.include_router(videos_router, prefix="")
    app.include_router(folders_router, prefix="")
    app.include_router(health_router, prefix="")
    app.include_router(auth_router, prefix="")
    app.include_router(model_papers_router, prefix="")
    app.include_router(notes_router, prefix="")
    app.include_router(model_paper_predictions_router, prefix="")
    app.include_router(dashboard_router, prefix="")
    app.include_router(curriculum_router, prefix="")
    app.include_router(admin.router, prefix="")
    app.include_router(admin_users.router, prefix="")
    debug_log(f"[ROUTER_DEBUG] ✓ All other routers registered successfully")
    
    # Verify curriculum router was registered
    curriculum_routes = [route for route in app.routes if hasattr(route, 'path') and '/api/curriculum' in route.path]
    debug_log(f"[ROUTER_DEBUG] Curriculum routes found: {len(curriculum_routes)}")
    for route in curriculum_routes:
        debug_log(f"[ROUTER_DEBUG]   {route.path} - {list(route.methods)}")
except Exception as e:
    print(f"[ROUTER_ERROR] Failed to register other routers: {str(e)}")
    print(f"[ROUTER_ERROR] Exception type: {type(e).__name__}")
    import traceback
    traceback.print_exc()

debug_log(f"[ROUTER_DEBUG] Router registration complete")
debug_log(f"[ROUTER_DEBUG] Total routes: {len([r for r in app.routes if hasattr(r, 'path')])}")

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {"msg": "Welcome"}

# Health check endpoint
@app.get("/health")
async def health_check():
    """Simple health check"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# Comprehensive health check endpoint
@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with CORS and configuration validation"""
    try:
        # Check CORS configuration
        cors_status = "healthy"
        cors_issues = []
        
        for origin in CORS_ORIGINS:
            if ';' in origin or ',' in origin:
                cors_status = "unhealthy"
                cors_issues.append(f"Invalid origin format: {origin}")
            elif not (origin.startswith('http://') or origin.startswith('https://')):
                cors_status = "unhealthy"
                cors_issues.append(f"Invalid origin protocol: {origin}")
        
        # Check directory access
        dir_status = "healthy"
        dir_issues = []
        
        for dir_path, dir_name in [(DATA_DIR, "Data"), (VECTOR_STORES_DIR, "Vector Stores"), (VIDEOS_DIR, "Videos")]:
            if not os.path.exists(dir_path):
                dir_status = "unhealthy"
                dir_issues.append(f"{dir_name} directory not found: {dir_path}")
            elif not os.access(dir_path, os.R_OK | os.W_OK):
                dir_status = "unhealthy"
                dir_issues.append(f"{dir_name} directory not accessible: {dir_path}")
        
        # Overall status
        overall_status = "healthy" if cors_status == "healthy" and dir_status == "healthy" else "unhealthy"
        
        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "environment": os.getenv("ENV", "unknown"),
            "python_version": sys.version,
            "cors": {
                "status": cors_status,
                "origins": CORS_ORIGINS,
                "issues": cors_issues
            },
            "directories": {
                "status": dir_status,
                "data_dir": DATA_DIR,
                "vector_stores_dir": VECTOR_STORES_DIR,
                "videos_dir": VIDEOS_DIR,
                "issues": dir_issues
            },
            "api": {
                "title": API_TITLE,
                "version": API_VERSION,
                "description": API_DESCRIPTION
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy", 
            "error": str(e), 
            "timestamp": datetime.now().isoformat(),
            "error_type": type(e).__name__
        }

# Health test endpoint
@app.get("/health/test")
async def health_test():
    """Health test endpoint for Railway health checks"""
    try:
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "environment": os.getenv("ENV", "unknown"),
            "python_version": sys.version,
            "data_dir": DATA_DIR,
            "vector_stores_dir": VECTOR_STORES_DIR,
            "videos_dir": VIDEOS_DIR
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "timestamp": datetime.now().isoformat()}

# Simple test endpoint
@app.get("/test")
async def test_endpoint():
    """Simple test endpoint to verify the API is working"""
    return {
        "message": "Backend is running!",
        "timestamp": datetime.now().isoformat(),
        "cors_origins": CORS_ORIGINS,
        "frontend_url": "https://student-panel-staging-production-d927.up.railway.app",
        "environment": os.getenv("ENV", "unknown")
    }

# CORS test endpoint
@app.get("/cors-test")
async def cors_test():
    """Test endpoint to verify CORS headers are working correctly"""
    return {
        "message": "CORS test successful",
        "timestamp": datetime.now().isoformat(),
        "cors_working": True,
        "cors_origins": CORS_ORIGINS
    }

# OPTIONS endpoint for CORS preflight
@app.options("/cors-test")
async def cors_test_options():
    """Handle CORS preflight for the test endpoint"""
    return {"message": "CORS preflight handled"}

# Auth test endpoint (no authentication required)
@app.get("/auth-test")
async def auth_test_endpoint():
    """Test endpoint to verify auth router is accessible"""
    return {
        "message": "Auth test endpoint accessible",
        "timestamp": datetime.now().isoformat(),
        "auth_router_status": "working"
    }

# OPTIONS endpoint for auth test
@app.options("/auth-test")
async def auth_test_options():
    """Handle CORS preflight for auth test endpoint"""
    return {"message": "Auth test CORS preflight handled"}

# Document upload endpoint
@app.post("/api/documents/upload")
async def upload_file(user = Depends(get_current_user)):
    """Upload document endpoint"""
    return {"msg": f"File uploaded by {user.username}"}

# Example protected endpoint
@app.get("/protected")
async def protected_route(user=Depends(get_current_user)):
    return {"message": f"Hello, {user.username}! This is a protected endpoint."}

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    try:
        debug_log(f"[STARTUP_DEBUG] ===== FASTAPI APP STARTING =====")
        debug_log(f"[STARTUP_DEBUG] App title: {API_TITLE}")
        debug_log(f"[STARTUP_DEBUG] App version: {API_VERSION}")
        debug_log(f"[STARTUP_DEBUG] Production mode: {IS_PRODUCTION}")
        debug_log(f"[STARTUP_DEBUG] Data directory: {DATA_DIR}")
        debug_log(f"[STARTUP_DEBUG] Vector stores directory: {VECTOR_STORES_DIR}")
        debug_log(f"[STARTUP_DEBUG] CORS origins: {CORS_ORIGINS}")
        debug_log(f"[INFO] Starting application initialization...")
        debug_log(f"[INFO] Environment: {os.getenv('ENV', 'unknown')}")
        debug_log(f"[INFO] Python version: {os.sys.version}")
        debug_log(f"[INFO] Working directory: {os.getcwd()}")
        debug_log(f"[INFO] Current user: {os.getuid() if hasattr(os, 'getuid') else 'unknown'}")
        
        # Create required directories
        debug_log(f"[INFO] Creating data directories...")
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            os.makedirs(VECTOR_STORES_DIR, exist_ok=True)
            os.makedirs(VIDEOS_DIR, exist_ok=True)
            debug_log(f"[INFO] Data directories created successfully")
        except Exception as e:
            print(f"[WARNING] Could not create some directories: {str(e)}")
            print(f"[WARNING] This is normal in Railway production environment")
            # Continue anyway - Railway handles directory permissions
        
        # Initialize data files if they don't exist
        debug_log(f"[INFO] Initializing data files...")
        try:
            if not os.path.exists(os.path.join(DATA_DIR, "documents.json")):
                with open(os.path.join(DATA_DIR, "documents.json"), "w") as f:
                    f.write("[]")
                debug_log(f"[INFO] documents.json initialized")
            
            if not os.path.exists(os.path.join(DATA_DIR, "videos.json")):
                with open(os.path.join(DATA_DIR, "videos.json"), "w") as f:
                    f.write("[]")
                debug_log(f"[INFO] videos.json initialized")
        except Exception as e:
            print(f"[WARNING] Could not initialize some data files: {str(e)}")
            print(f"[WARNING] This is normal in Railway production environment")
            # Continue anyway - files will be created when needed
        
        # Initialize user system (file-based)
        debug_log(f"[INFO] Initializing user system...")
        try:
            from .models.user import user_manager
            debug_log(f"[INFO] User system initialized with {len(user_manager.users)} users")
        except Exception as e:
            print(f"[WARNING] Could not initialize user system: {str(e)}")
            print(f"[WARNING] This may affect authentication functionality")
            # Continue anyway - app can still run
        
        print(f"[INFO] Application started successfully at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except Exception as e:
        print(f"[ERROR] Startup failed: {str(e)}")
        print(f"[ERROR] Error type: {type(e).__name__}")
        import traceback
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        raise e

# Router registration is handled in the startup event

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print(f"[INFO] Application shutting down at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Add explicit OpenAPI JSON endpoint
@app.get("/openapi.json", include_in_schema=False)
async def get_openapi_json():
    """Get OpenAPI schema as JSON"""
    schema = app.openapi()
    return JSONResponse(
        content=schema,
        headers={"Content-Type": "application/json"}
    ) 

# Debug endpoint to list all registered routes
@app.get("/debug/routes")
async def debug_routes():
    """Debug endpoint to list all registered routes"""
    routes = []
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            routes.append({
                "path": route.path,
                "methods": list(route.methods),
                "name": getattr(route, 'name', 'Unknown'),
                "tags": getattr(route, 'tags', [])
            })
    
    # Also check AI router specifically
    ai_routes = []
    try:
        for route in ai.router.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                ai_routes.append({
                    "path": route.path,
                    "methods": list(route.methods),
                    "name": getattr(route, 'name', 'Unknown')
                })
    except Exception as e:
        ai_routes = [{"error": str(e)}]
    
    # Check if /api/ai/ask is accessible
    ai_ask_accessible = any(
        route.path == "/api/ai/ask" and hasattr(route, 'methods') 
        for route in app.routes
    )
    
    # Check curriculum routes
    curriculum_routes = [r for r in routes if '/api/curriculum' in r.get('path', '')]
    curriculum_accessible = any(
        route.path == "/api/curriculum/validate" and hasattr(route, 'methods') 
        for route in app.routes
    )
    
    return {
        "total_routes": len(routes),
        "routes": routes,
        "ai_router_routes": ai_routes,
        "ai_router_prefix": getattr(ai.router, 'prefix', 'No prefix'),
        "ai_router_tags": getattr(ai.router, 'tags', []),
        "ai_ask_accessible": ai_ask_accessible,
        "ai_ask_path": "/api/ai/ask",
        "curriculum_routes": curriculum_routes,
        "curriculum_validate_accessible": curriculum_accessible,
        "curriculum_validate_path": "/api/curriculum/validate"
    }

# Simple CORS test endpoint
@app.get("/test-cors")
async def test_cors():
    """Simple endpoint to test CORS functionality"""
    return {
        "message": "CORS is working!",
        "timestamp": datetime.now().isoformat(),
        "status": "success"
    }

# Test endpoint that intentionally raises an error to test CORS headers
@app.get("/test-error")
async def test_error():
    """Test endpoint that raises an error to verify CORS headers are sent"""
    raise HTTPException(status_code=500, detail="This is a test error to verify CORS headers")

# Health check endpoint for vector stores
@app.get("/health/vectorstores")
async def vector_store_health_check():
    """Check vector store health"""
    try:
        from app.utils.vector_store import get_embeddings
        
        # Test embeddings
        embeddings = get_embeddings()
        
        # Test S3 connection
        from app.utils.s3_utils import list_available_templates
        templates = list_available_templates()
        
        return {
            "status": "healthy",
            "embeddings": "working",
            "s3": "working",
            "templates_count": len(templates)
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "error_type": type(e).__name__
        } 