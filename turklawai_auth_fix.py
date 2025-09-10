"""
TurkLawAI.com Authentication Emergency Fix
Basit email/password authentication ile geçici çözüm
"""
import os
import hashlib
import jwt
import asyncio
from datetime import datetime, timedelta
from supabase_client import supabase_client

# JWT settings
JWT_SECRET = os.getenv("JWT_SECRET_KEY", "turklawai-emergency-jwt-key-2025")
JWT_ALGORITHM = "HS256"
JWT_EXPIRES_HOURS = 24

class EmergencyAuth:
    def __init__(self):
        self.supabase = supabase_client
    
    def hash_password(self, password: str) -> str:
        """Simple password hashing"""
        return hashlib.sha256(f"{password}turklawai_salt".encode()).hexdigest()
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify hashed password"""
        return self.hash_password(password) == hashed
    
    def create_jwt_token(self, user_data: dict) -> str:
        """Create JWT token for user"""
        payload = {
            "user_id": user_data["id"],
            "email": user_data["email"],
            "full_name": user_data.get("full_name", ""),
            "plan": user_data.get("plan", "free"),
            "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRES_HOURS),
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    def verify_jwt_token(self, token: str) -> dict:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            raise Exception("Token expired")
        except jwt.InvalidTokenError:
            raise Exception("Invalid token")
    
    async def register_user(self, email: str, password: str, full_name: str = "") -> dict:
        """Register new user"""
        try:
            # Check if user exists
            existing = await self.supabase.query_data("users", {"email": email})
            if existing["success"] and existing["data"]:
                return {"success": False, "message": "Kullanıcı zaten kayıtlı"}
            
            # Hash password
            hashed_password = self.hash_password(password)
            
            # Create user data (matching real table structure)
            user_data = {
                "email": email,
                "password_hash": hashed_password,
                "full_name": full_name,
                "plan": "free",
                "status": "active",
                "requests_used": 0,
                "requests_limit": 100,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            # Insert user to Supabase
            result = await self.supabase.insert_data("users", user_data)
            
            if result["success"]:
                # Create JWT token
                user_info = result["data"][0] if result["data"] else user_data
                token = self.create_jwt_token(user_info)
                
                return {
                    "success": True,
                    "message": "Kayıt başarılı",
                    "user": {
                        "id": user_info.get("id"),
                        "email": user_info["email"],
                        "full_name": user_info["full_name"],
                        "plan": user_info["plan"]
                    },
                    "token": token
                }
            else:
                return {"success": False, "message": "Kayıt sırasında hata oluştu"}
                
        except Exception as e:
            return {"success": False, "message": f"Hata: {str(e)}"}
    
    async def login_user(self, email: str, password: str) -> dict:
        """Login user"""
        try:
            # Get user from database
            result = await self.supabase.query_data("users", {"email": email})
            
            if not result["success"] or not result["data"]:
                return {"success": False, "message": "Kullanıcı bulunamadı"}
            
            user = result["data"][0]
            
            # Verify password
            if not self.verify_password(password, user["password_hash"]):
                return {"success": False, "message": "Şifre hatalı"}
            
            # Check if user is active
            if user.get("status") != "active":
                return {"success": False, "message": "Hesap deaktif"}
            
            # Create JWT token
            token = self.create_jwt_token(user)
            
            return {
                "success": True,
                "message": "Giriş başarılı",
                "user": {
                    "id": user["id"],
                    "email": user["email"],
                    "full_name": user.get("full_name", ""),
                    "plan": user.get("plan", "free")
                },
                "token": token
            }
            
        except Exception as e:
            return {"success": False, "message": f"Hata: {str(e)}"}
    
    async def verify_token(self, token: str) -> dict:
        """Verify user token and return user info"""
        try:
            payload = self.verify_jwt_token(token)
            
            # Get fresh user data from database
            result = await self.supabase.query_data("users", {"id": payload["user_id"]})
            
            if result["success"] and result["data"]:
                user = result["data"][0]
                return {
                    "success": True,
                    "user": {
                        "id": user["id"],
                        "email": user["email"],
                        "full_name": user.get("full_name", ""),
                        "plan": user.get("plan", "free"),
                        "status": user.get("status", "active")
                    }
                }
            else:
                return {"success": False, "message": "Kullanıcı bulunamadı"}
                
        except Exception as e:
            return {"success": False, "message": f"Token geçersiz: {str(e)}"}

# Global instance
emergency_auth = EmergencyAuth()

# Test functions
async def test_auth_system():
    """Test emergency auth system"""
    print("🔧 Testing Emergency Auth System...")
    
    # Test registration
    print("\n1. Testing user registration...")
    reg_result = await emergency_auth.register_user(
        email="test@turklawai.com",
        password="test123456",
        full_name="Test Kullanıcısı"
    )
    print(f"Registration result: {reg_result}")
    
    if reg_result["success"]:
        # Test login
        print("\n2. Testing user login...")
        login_result = await emergency_auth.login_user(
            email="test@turklawai.com",
            password="test123456"
        )
        print(f"Login result: {login_result}")
        
        if login_result["success"]:
            # Test token verification
            print("\n3. Testing token verification...")
            token = login_result["token"]
            verify_result = await emergency_auth.verify_token(token)
            print(f"Token verification result: {verify_result}")

if __name__ == "__main__":
    asyncio.run(test_auth_system())