#!/bin/bash
# TurkLawAI.com Production Deployment Script

echo "🚀 Deploying TurkLawAI Authentication System to Production"

# Configuration
SERVER_USER="root"
SERVER_HOST="turklawai.com"
DEPLOY_PATH="/var/www/turklawai"

echo "1. Uploading API server files..."
scp turklawai_api_server.py $SERVER_USER@$SERVER_HOST:$DEPLOY_PATH/
scp turklawai_auth_fix.py $SERVER_USER@$SERVER_HOST:$DEPLOY_PATH/
scp supabase_client.py $SERVER_USER@$SERVER_HOST:$DEPLOY_PATH/
scp .env $SERVER_USER@$SERVER_HOST:$DEPLOY_PATH/

echo "2. Uploading frontend files..."
scp turklawai_frontend_fix.js $SERVER_USER@$SERVER_HOST:$DEPLOY_PATH/public/js/
scp turklawai_auth_template.html $SERVER_USER@$SERVER_HOST:$DEPLOY_PATH/public/

echo "3. Installing dependencies on server..."
ssh $SERVER_USER@$SERVER_HOST "cd $DEPLOY_PATH && pip3 install fastapi uvicorn supabase python-dotenv python-jose[cryptography]"

echo "4. Starting API server..."
ssh $SERVER_USER@$SERVER_HOST "cd $DEPLOY_PATH && nohup python3 turklawai_api_server.py > api.log 2>&1 &"

echo "5. Testing API server..."
sleep 3
curl -s http://turklawai.com:8001/health | jq '.'

echo "✅ Deployment complete!"
echo ""
echo "Next steps:"
echo "1. Configure Nginx reverse proxy for /api/ -> localhost:8001"
echo "2. Update turklawai_frontend_fix.js to use production API URL"
echo "3. Test authentication at https://turklawai.com"