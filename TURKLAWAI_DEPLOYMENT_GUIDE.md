# 🚀 TurkLawAI.com Deployment Guide

## 📋 System Overview

TurkLawAI is now a **complete subscription-based Turkish Legal Search API** with the following components:

### 🏗️ **Architecture Components**

1. **TurkLawAI MCP Server** (`turklawai_mcp_server.py`)
   - Port: 8002
   - Authenticated Turkish legal search API
   - Rate limiting and usage tracking
   - Integrated with original MCP functions

2. **Subscription Management API** (`turklawai_subscription_system.py`)
   - Port: 8001
   - Stripe payment processing
   - Clerk authentication
   - User subscription management

3. **Supabase Database** (`database_schema.sql`)
   - User subscriptions and billing
   - Usage analytics and logging
   - API keys and authentication

4. **Original MCP Server** (`simple_api.py`)
   - Port: 8000 (for compatibility)
   - Enhanced with Supabase logging

---

## 🎯 **Subscription Plans**

| Plan | Price/Month | Requests/Month | Rate Limit/Min | Features |
|------|-------------|----------------|----------------|----------|
| **Free** | $0 | 100 | 5/min | Basic search, Standard support |
| **Basic** | $29.99 | 1,000 | 20/min | Full access, Email support, API |
| **Professional** | $99.99 | 5,000 | 60/min | Bulk API, Priority support, Analytics |
| **Enterprise** | $299.99 | 25,000+ | 200/min | SLA, On-premise, Custom development |

---

## ⚙️ **Environment Configuration**

### Required Environment Variables

```bash
# Supabase Configuration
SUPABASE_URL=https://supabase.turklawai.com
SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
YARGI_SCHEMA=yargi_mcp

# TurkLawAI Configuration
TURKLAWAI_DOMAIN=turklawai.com
ENABLE_SUBSCRIPTION_SYSTEM=true

# Clerk Authentication
CLERK_SECRET_KEY=sk_test_your_clerk_secret_key
CLERK_PUBLISHABLE_KEY=pk_test_your_clerk_publishable_key
CLERK_OAUTH_REDIRECT_URL=https://turklawai.com/auth/callback
CLERK_FRONTEND_URL=https://turklawai.com

# Stripe Payment Processing  
STRIPE_SECRET_KEY=sk_test_your_stripe_secret_key
STRIPE_PUBLISHABLE_KEY=pk_test_your_stripe_publishable_key
STRIPE_WEBHOOK_SECRET=whsec_your_stripe_webhook_secret

# JWT Configuration
JWT_SECRET_KEY=your-super-secret-jwt-key-min-64-chars-long
JWT_EXPIRES_IN=24h

# Rate Limiting
RATE_LIMIT_FREE_PLAN=5
RATE_LIMIT_BASIC_PLAN=20
RATE_LIMIT_PRO_PLAN=60
RATE_LIMIT_ENTERPRISE_PLAN=200

# CORS Configuration
ALLOWED_ORIGINS=https://turklawai.com,https://www.turklawai.com,https://api.turklawai.com
```

---

## 🚀 **Deployment Instructions**

### 1. **Database Setup**

```bash
# Execute the database schema on your Supabase instance
psql -h supabase.turklawai.com -U postgres -d postgres -f database_schema.sql

# Or via Supabase dashboard SQL editor
```

### 2. **Server Deployment**

#### Option A: Docker Deployment
```bash
# Build and run containers
docker-compose up -d

# Or individual containers
docker build -t turklawai-mcp .
docker run -p 8002:8002 --env-file .env turklawai-mcp
```

#### Option B: Direct Python Deployment
```bash
# Install dependencies
pip install -r requirements.txt

# Start all services
python turklawai_mcp_server.py &          # Main MCP API (Port 8002)
python turklawai_subscription_system.py & # Subscription API (Port 8001) 
python simple_api.py &                    # Legacy API (Port 8000)
```

#### Option C: Production with Gunicorn
```bash
# Install production dependencies
pip install gunicorn uvicorn[standard]

# Start with Gunicorn
gunicorn turklawai_mcp_server:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8002
```

### 3. **Load Balancer Configuration (Nginx)**

```nginx
upstream turklawai_mcp {
    server localhost:8002;
}

upstream turklawai_subscription {
    server localhost:8001;
}

server {
    listen 80;
    server_name api.turklawai.com;
    
    # MCP API endpoints
    location /api/ {
        proxy_pass http://turklawai_mcp;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    
    # Subscription management
    location /subscription/ {
        proxy_pass http://turklawai_subscription;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    # Health checks
    location /health {
        proxy_pass http://turklawai_mcp;
    }
    
    # Static files
    location /static/ {
        alias /var/www/turklawai/static/;
    }
}
```

---

## 🔐 **Authentication Setup**

### 1. **Clerk Configuration**

1. Create account at [clerk.com](https://clerk.com)
2. Create new application: "TurkLawAI"
3. Configure OAuth providers:
   - Google OAuth
   - GitHub OAuth (optional)
4. Set redirect URLs:
   - `https://turklawai.com/auth/callback`
   - `https://api.turklawai.com/auth/callback`
5. Copy API keys to `.env`

### 2. **Stripe Configuration**

1. Create account at [stripe.com](https://stripe.com)
2. Create products and prices:
   ```bash
   # Create products via Stripe CLI or dashboard
   stripe products create --name "Basic Plan" --description "1,000 requests/month"
   stripe prices create --product prod_xxx --currency usd --recurring '{"interval":"month"}' --unit-amount 2999
   ```
3. Configure webhooks:
   - Endpoint: `https://api.turklawai.com/webhook/stripe`
   - Events: `customer.subscription.*`, `invoice.payment_*`
4. Copy keys to `.env`

---

## 🛡️ **Security Checklist**

- [ ] **Environment Variables**: Never commit `.env` files
- [ ] **JWT Secrets**: Use strong, randomly generated secrets (64+ chars)
- [ ] **HTTPS**: Force HTTPS in production with valid SSL certificates
- [ ] **Rate Limiting**: Configure appropriate limits per plan
- [ ] **CORS**: Restrict origins to your domains only
- [ ] **Database**: Enable Row Level Security (RLS) policies
- [ ] **API Keys**: Rotate regularly and use different keys per environment
- [ ] **Webhooks**: Verify Stripe webhook signatures
- [ ] **Logging**: Monitor for suspicious activity
- [ ] **Backups**: Regular database backups

---

## 📊 **API Endpoints**

### **Main MCP API (Port 8002)**
```
GET  /                           # Service info
GET  /health                     # Health check  
GET  /user/profile               # User profile & usage
POST /api/search/yargitay        # Authenticated Yargitay search
POST /api/search/danistay        # Authenticated Danistay search
GET  /api/document/{type}/{id}   # Get document content
```

### **Subscription API (Port 8001)**
```
GET  /subscription/plans         # Available plans
GET  /subscription/status        # Current subscription
POST /subscription/create        # Create subscription
POST /subscription/cancel        # Cancel subscription
GET  /usage/stats               # Usage analytics
POST /webhook/stripe            # Stripe webhooks
```

### **Legacy API (Port 8000)**
```
GET  /health                    # Health with Supabase status
POST /webhook/yargitay-search   # n8n compatible search
POST /webhook/danistay-search   # n8n compatible search
```

---

## 🔍 **API Usage Examples**

### 1. **Authentication Flow**
```javascript
// Get JWT token from Clerk
const token = await clerk.session.getToken();

// Use token in requests
const response = await fetch('https://api.turklawai.com/api/search/yargitay', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    andKelimeler: 'iş kanunu',
    page_size: 10
  })
});
```

### 2. **Search Request**
```bash
curl -X POST "https://api.turklawai.com/api/search/yargitay" \\
  -H "Authorization: Bearer your_jwt_token" \\
  -H "Content-Type: application/json" \\
  -d '{"andKelimeler": "iş kanunu", "page_size": 5}'
```

### 3. **Check Usage**
```bash
curl "https://api.turklawai.com/user/profile" \\
  -H "Authorization: Bearer your_jwt_token"
```

---

## 📈 **Monitoring & Analytics**

### **Database Queries for Analytics**

```sql
-- Daily active users
SELECT DATE(timestamp) as date, COUNT(DISTINCT user_id) as active_users
FROM yargi_mcp_usage_logs 
WHERE timestamp >= NOW() - INTERVAL '30 days'
GROUP BY DATE(timestamp);

-- Revenue by plan
SELECT plan, COUNT(*) as subscribers, SUM(amount_cents)/100 as revenue
FROM yargi_mcp_billing_history 
WHERE status = 'paid'
GROUP BY plan;

-- Popular search terms
SELECT query_text, COUNT(*) as frequency
FROM yargi_mcp_search_queries
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY query_text
ORDER BY frequency DESC
LIMIT 10;
```

### **Performance Monitoring**
```bash
# Monitor API response times
curl -w "@curl-format.txt" -s -o /dev/null https://api.turklawai.com/health

# Database connection monitoring
SELECT * FROM pg_stat_activity WHERE datname = 'postgres';

# Error rate monitoring
grep "ERROR" /var/log/turklawai/*.log | wc -l
```

---

## 🛠️ **Development & Testing**

### **Local Development**
```bash
# 1. Clone repository
git clone https://github.com/your-org/turklawai.git
cd turklawai

# 2. Setup environment
cp .env.example .env
# Edit .env with your local values

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start services
python turklawai_mcp_server.py &
python turklawai_subscription_system.py &

# 5. Test APIs
curl http://localhost:8002/health
```

### **Testing Checklist**
- [ ] **Authentication**: JWT token validation
- [ ] **Rate Limiting**: Verify limits work per plan
- [ ] **Search Functionality**: All court types work
- [ ] **Billing**: Stripe webhooks process correctly
- [ ] **Usage Tracking**: Requests are logged to database
- [ ] **Error Handling**: Graceful degradation
- [ ] **Performance**: Response times under 2 seconds

---

## 🚨 **Troubleshooting**

### **Common Issues**

1. **Port Conflicts**
   ```bash
   # Check what's using ports
   netstat -tulpn | grep :8002
   
   # Kill processes if needed
   sudo kill -9 $(lsof -t -i:8002)
   ```

2. **Database Connection Issues**
   ```bash
   # Test Supabase connection
   python -c "from supabase_client import test_supabase_connection; import asyncio; print(asyncio.run(test_supabase_connection()))"
   ```

3. **Authentication Failures**
   ```bash
   # Verify JWT secret
   python -c "import jwt; print(jwt.decode('your_token', 'your_secret', algorithms=['HS256']))"
   ```

4. **Stripe Webhook Issues**
   ```bash
   # Test webhook endpoint
   stripe listen --forward-to localhost:8001/webhook/stripe
   ```

### **Logs and Debugging**
```bash
# Application logs
tail -f /var/log/turklawai/app.log

# Database logs  
tail -f /var/log/postgresql/postgresql.log

# Nginx logs
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

---

## 📞 **Support & Maintenance**

### **Regular Maintenance Tasks**
- [ ] **Monthly**: Review usage analytics and billing
- [ ] **Weekly**: Monitor error rates and performance
- [ ] **Daily**: Check system health endpoints
- [ ] **Quarterly**: Update dependencies and security patches
- [ ] **Annually**: Rotate API keys and secrets

### **Scaling Considerations**
- **Horizontal**: Add more server instances behind load balancer
- **Database**: Consider read replicas for heavy analytics queries
- **Caching**: Implement Redis for rate limiting and session storage
- **CDN**: Use CloudFlare or AWS CloudFront for static assets
- **Monitoring**: Implement comprehensive logging with ELK stack

---

## 🎯 **Production Checklist**

- [ ] **Domain**: Configure turklawai.com DNS
- [ ] **SSL**: Install Let's Encrypt or commercial certificate
- [ ] **Database**: Production Supabase instance configured
- [ ] **Environment**: All production environment variables set
- [ ] **Clerk**: Production OAuth application configured
- [ ] **Stripe**: Live mode enabled with real payment methods
- [ ] **Monitoring**: Health check endpoints configured
- [ ] **Backup**: Database backup strategy implemented
- [ ] **Scaling**: Auto-scaling groups configured
- [ ] **CDN**: Content delivery network configured
- [ ] **Monitoring**: Error tracking with Sentry or similar
- [ ] **Documentation**: API documentation published

---

## 🌟 **Success Metrics**

Track these KPIs for TurkLawAI:

- **Technical**: API response time < 2s, 99.9% uptime
- **User**: Daily/Monthly Active Users, retention rate
- **Business**: MRR growth, conversion rate, churn rate
- **Product**: Search success rate, user satisfaction

---

**🎉 Congratulations! TurkLawAI is now ready for production deployment with a complete subscription system!**

---

## 📚 **Additional Resources**

- [Supabase Documentation](https://supabase.com/docs)
- [Stripe API Reference](https://stripe.com/docs/api)
- [Clerk Authentication](https://clerk.com/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Turkish Legal Databases Info](./README.md)