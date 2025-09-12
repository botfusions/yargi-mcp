#!/bin/bash
# TurkLawAI Production Deployment Script (Updated)

echo "========================================="
echo "  TurkLawAI.com Production Deployment"
echo "========================================="

# Configuration
SERVER_HOST="turklawai.com"
DEPLOY_PATH="/var/www/turklawai"
API_PORT="8001"

echo ""
echo "Step 1: Preparing files for deployment..."

# Create deployment package
echo "Creating deployment directory..."
mkdir -p deployment_package
cp turklawai_api_server.py deployment_package/
cp turklawai_auth_fix.py deployment_package/
cp supabase_client.py deployment_package/
cp .env deployment_package/
cp turklawai_frontend_replacement.js deployment_package/
cp requirements.txt deployment_package/

echo "Files prepared for deployment:"
ls -la deployment_package/

echo ""
echo "Step 2: Upload files to server..."
echo "scp deployment_package/* root@$SERVER_HOST:$DEPLOY_PATH/"

echo ""
echo "Step 3: Install dependencies on server..."
echo "SSH to server and run:"
echo "cd $DEPLOY_PATH"
echo "pip3 install fastapi uvicorn supabase python-dotenv python-jose[cryptography] pydantic[email]"

echo ""
echo "Step 4: Configure environment..."
echo "Update .env file on server with production values:"
echo "PRODUCTION=true"
echo "ENABLE_AUTH=true"

echo ""
echo "Step 5: Start API server..."
echo "nohup python3 turklawai_api_server.py > api.log 2>&1 &"

echo ""
echo "Step 6: Configure Nginx reverse proxy..."
echo "Add to /etc/nginx/sites-available/turklawai.com:"
echo ""
echo "location /api/ {"
echo "    proxy_pass http://localhost:8001/;"
echo "    proxy_set_header Host \$host;"
echo "    proxy_set_header X-Real-IP \$remote_addr;"
echo "    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;"
echo "}"

echo ""
echo "Step 7: Test deployment..."
echo "curl https://turklawai.com/api/health"

echo ""
echo "============================================"
echo "  Ready for manual deployment to server!"
echo "============================================"