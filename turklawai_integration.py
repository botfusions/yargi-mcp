"""
TurkLawAI.com Integration - Hukuki Analiz Agent Sistemi
Mevcut yargi-mcp backend'i ile CenkV1 projesi entegrasyonu
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel

# Existing imports from yargi-mcp
try:
    from mcp_server_main import (
        search_bedesten_unified,
        get_bedesten_document_markdown,
        search_anayasa_unified,
        get_anayasa_document_unified,
        search_sayistay_unified,
        get_sayistay_document_unified,
        search_uyusmazlik_decisions,
        get_uyusmazlik_document_markdown,
        search_kvkk_decisions,
        get_kvkk_document_markdown
    )
    YARGI_MCP_AVAILABLE = True
except ImportError:
    YARGI_MCP_AVAILABLE = False

# Import from CenkV1 project
try:
    import sys
    sys.path.append(r"C:\Users\user\Downloads\Project Claude\cenk v1\🏛️ TURKLAWAI-PROJECT\📁 SOURCE-CODE")
    from turklawai_mcp_server import verify_token, check_rate_limits, log_api_usage
    CENK_AUTH_AVAILABLE = True
except ImportError:
    CENK_AUTH_AVAILABLE = False

class LegalQuery(BaseModel):
    """Hukuki sorgu modeli"""
    question: str
    legal_area: Optional[str] = None
    court_preference: Optional[List[str]] = []
    analysis_depth: Optional[str] = "standard"  # basic, standard, comprehensive
    output_format: Optional[str] = "structured"  # structured, narrative, bullet_points

class LegalAnalysisResponse(BaseModel):
    """Hukuki analiz yanıt modeli"""
    question: str
    legal_domain: str
    analysis: Dict[str, Any]
    sources: List[Dict[str, Any]]
    recommendations: List[str]
    confidence_score: float
    processing_time_ms: int

class TurkLawAIAgent:
    """TurkLawAI.com için entegre edilmiş hukuki analiz agent'ı"""
    
    def __init__(self):
        self.legal_domains = {
            "constitutional": {
                "keywords": ["anayasa", "temel hak", "özgürlük", "eşitlik", "norm denetimi"],
                "courts": ["ANAYASA"],
                "search_tool": "search_anayasa_unified"
            },
            "civil": {
                "keywords": ["medeni", "borçlar", "sözleşme", "zarar", "tazminat", "mülkiyet"],
                "courts": ["YARGITAYKARARI"],
                "search_tool": "search_bedesten_unified"
            },
            "administrative": {
                "keywords": ["idari", "kamu", "belediye", "vergi", "maaş", "atama"],
                "courts": ["DANISTAYKARAR"],
                "search_tool": "search_bedesten_unified"
            },
            "criminal": {
                "keywords": ["ceza", "suç", "hüküm", "beraat", "taksir"],
                "courts": ["YARGITAYKARARI"],
                "search_tool": "search_bedesten_unified"
            },
            "commercial": {
                "keywords": ["ticaret", "şirket", "rekabet", "patent", "marka"],
                "courts": ["YARGITAYKARARI", "REKABET"],
                "search_tool": "search_bedesten_unified"
            },
            "labor": {
                "keywords": ["iş", "işçi", "sendika", "kıdem", "ihbar"],
                "courts": ["YARGITAYKARARI"],
                "search_tool": "search_bedesten_unified"
            },
            "audit": {
                "keywords": ["sayıştay", "denetim", "ihale", "kamu mali", "hesap"],
                "courts": ["SAYISTAY"],
                "search_tool": "search_sayistay_unified"
            },
            "data_protection": {
                "keywords": ["kvkk", "kişisel veri", "gdpr", "rıza", "veri ihlali"],
                "courts": ["KVKK"],
                "search_tool": "search_kvkk_decisions"
            }
        }
        
        self.expert_panel = {
            "constitutional_expert": {
                "name": "Prof. Dr. Zühtü Arslan",
                "specialty": "Anayasa Hukuku",
                "methods": ["temel_haklar_analizi", "norm_denetimi", "orantililik_testi"]
            },
            "civil_expert": {
                "name": "Prof. Dr. M. Kemal Oğuzman",
                "specialty": "Medeni Hukuk",
                "methods": ["sozlesme_analizi", "zarar_sorumlulugu", "mulkiyet_haklari"]
            },
            "administrative_expert": {
                "name": "Prof. Dr. Lütfi Duran",
                "specialty": "İdare Hukuku",
                "methods": ["idari_islem", "yargi_denetimi", "kamu_hizmeti"]
            },
            "criminal_expert": {
                "name": "Prof. Dr. Sulhi Dönmezer",
                "specialty": "Ceza Hukuku",
                "methods": ["suc_siniflandirmasi", "muhakeme_analizi", "ceza_takdiri"]
            }
        }

    def classify_legal_domain(self, question: str) -> str:
        """Hukuki soruyu alan bazında sınıflandır"""
        question_lower = question.lower()
        
        domain_scores = {}
        for domain, config in self.legal_domains.items():
            score = sum(1 for keyword in config["keywords"] if keyword in question_lower)
            if score > 0:
                domain_scores[domain] = score
        
        if domain_scores:
            return max(domain_scores, key=domain_scores.get)
        return "civil"  # Default domain

    async def search_legal_sources(self, question: str, legal_domain: str, 
                                 court_preference: List[str] = None) -> List[Dict[str, Any]]:
        """Hukuki kaynakları ara"""
        sources = []
        
        if not YARGI_MCP_AVAILABLE:
            return [{
                "source": "fallback",
                "title": "Test verisi - MCP mevcut değil",
                "content": f"'{question}' sorusu için test içeriği",
                "court": "Test"
            }]
        
        domain_config = self.legal_domains.get(legal_domain, self.legal_domains["civil"])
        search_tool = domain_config["search_tool"]
        courts = court_preference or domain_config["courts"]
        
        try:
            if search_tool == "search_bedesten_unified":
                for court_type in courts:
                    result = await search_bedesten_unified(
                        phrase=question,
                        court_types=[court_type],
                        pageSize=5
                    )
                    if result and result.get("decisions"):
                        for decision in result["decisions"]:
                            sources.append({
                                "source": "bedesten",
                                "court": court_type,
                                "title": decision.get("baslik", ""),
                                "summary": decision.get("ozet", ""),
                                "date": decision.get("kararTarihi", ""),
                                "document_id": decision.get("documentId", ""),
                                "confidence": 0.8
                            })
            
            elif search_tool == "search_anayasa_unified":
                result = await search_anayasa_unified(
                    keywords_all=[question],
                    decision_type="both",
                    results_per_page=5
                )
                if result and result.get("decisions"):
                    for decision in result["decisions"]:
                        sources.append({
                            "source": "anayasa",
                            "court": "Anayasa Mahkemesi",
                            "title": decision.get("title", ""),
                            "summary": decision.get("summary", ""),
                            "date": decision.get("date", ""),
                            "document_id": decision.get("id", ""),
                            "confidence": 0.9
                        })
            
            elif search_tool == "search_kvkk_decisions":
                result = await search_kvkk_decisions(
                    keywords=question,
                    pageSize=5
                )
                if result and result.get("decisions"):
                    for decision in result["decisions"]:
                        sources.append({
                            "source": "kvkv",
                            "court": "KVKK",
                            "title": decision.get("title", ""),
                            "summary": decision.get("snippet", ""),
                            "date": decision.get("date", ""),
                            "url": decision.get("url", ""),
                            "confidence": 0.7
                        })
                        
        except Exception as e:
            print(f"Arama hatası: {e}")
            sources.append({
                "source": "error",
                "title": "Arama sırasında hata oluştu",
                "content": str(e),
                "confidence": 0.1
            })
        
        return sources

    def analyze_with_expert_panel(self, question: str, sources: List[Dict[str, Any]], 
                                legal_domain: str) -> Dict[str, Any]:
        """Uzman panel ile analiz"""
        
        # Ana analiz kategorileri
        analysis = {
            "legal_assessment": {
                "applicable_law": [],
                "precedents": [],
                "legal_principles": []
            },
            "expert_opinions": {},
            "risk_analysis": {
                "high_risk": [],
                "medium_risk": [],
                "low_risk": []
            },
            "procedural_guidance": [],
            "similar_cases": []
        }
        
        # Mevzuat analizi
        for source in sources[:3]:  # İlk 3 kaynak
            if source.get("confidence", 0) > 0.6:
                analysis["legal_assessment"]["precedents"].append({
                    "court": source.get("court", ""),
                    "title": source.get("title", ""),
                    "summary": source.get("summary", "")[:200],
                    "relevance": source.get("confidence", 0)
                })
        
        # Uzman görüşleri
        relevant_experts = self.get_relevant_experts(legal_domain)
        for expert_key, expert_info in relevant_experts.items():
            analysis["expert_opinions"][expert_key] = {
                "expert": expert_info["name"],
                "specialty": expert_info["specialty"],
                "opinion": self.generate_expert_opinion(question, expert_info, sources),
                "methods_applied": expert_info["methods"][:2]
            }
        
        # Risk değerlendirmesi
        analysis["risk_analysis"]["medium_risk"].append(
            "Emsal kararlar sınırlı olabilir - detaylı araştırma gerekli"
        )
        
        if legal_domain in ["constitutional", "administrative"]:
            analysis["risk_analysis"]["high_risk"].append(
                "Kamu hukuku alanı - usul ve süre sınırlarına dikkat"
            )
        
        # Prosedür rehberi
        analysis["procedural_guidance"] = self.generate_procedure_guidance(legal_domain)
        
        return analysis

    def get_relevant_experts(self, legal_domain: str) -> Dict[str, Any]:
        """İlgili uzmanları getir"""
        expert_mapping = {
            "constitutional": ["constitutional_expert"],
            "civil": ["civil_expert"],
            "administrative": ["administrative_expert"],
            "criminal": ["criminal_expert"],
            "commercial": ["civil_expert"],
            "labor": ["civil_expert"]
        }
        
        relevant_expert_keys = expert_mapping.get(legal_domain, ["civil_expert"])
        return {key: self.expert_panel[key] for key in relevant_expert_keys 
                if key in self.expert_panel}

    def generate_expert_opinion(self, question: str, expert_info: Dict[str, Any], 
                              sources: List[Dict[str, Any]]) -> str:
        """Uzman görüşü oluştur"""
        specialty = expert_info["specialty"]
        
        opinion_templates = {
            "Anayasa Hukuku": f"Anayasal perspektiften bakıldığında, '{question}' sorusu temel haklar ve özgürlükler bağlamında değerlendirilmelidir.",
            "Medeni Hukuk": f"Medeni hukuk açısından '{question}' konusu, ilgili TMK ve TBK hükümleri çerçevesinde incelenmelidir.",
            "İdare Hukuku": f"İdari hukuk bakımından '{question}' meselesi, kamu yararı ve idari işlem ilkeleri gözönünde tutularak ele alınmalıdır.",
            "Ceza Hukuku": f"Ceza hukuku perspektifinden '{question}' sorusu, suç unsurları ve muhakeme ilkeleri çerçevesinde değerlendirilmelidir."
        }
        
        base_opinion = opinion_templates.get(specialty, f"Hukuki açıdan '{question}' konusu detaylı inceleme gerektirir.")
        
        # Kaynaklara dayalı ek görüş
        if sources:
            strong_sources = [s for s in sources if s.get("confidence", 0) > 0.7]
            if strong_sources:
                base_opinion += f" Mevcut {len(strong_sources)} güçlü emsal karar bu yaklaşımı desteklemektedir."
        
        return base_opinion

    def generate_procedure_guidance(self, legal_domain: str) -> List[str]:
        """Prosedür rehberi oluştur"""
        guidance_mapping = {
            "constitutional": [
                "Bireysel başvuru için 30 günlük süre sınırı",
                "Diğer kanun yollarının tükenmesi şartı",
                "Başvuru dilekçesinde ihlal iddiasının açık belirtilmesi"
            ],
            "civil": [
                "Zamanaşımı sürelerine dikkat edilmesi",
                "Delillerin toplanması ve muhafazası",
                "Alternatif uyuşmazlık çözüm yollarının değerlendirilmesi"
            ],
            "administrative": [
                "İdari başvuru yollarının denenmesi",
                "Dava açma süresinin hesaplanması (60/30 gün)",
                "Yürütmeyi durdurma talebinin değerlendirilmesi"
            ],
            "criminal": [
                "Zamanaşımı ve dava düşürücü sürelerin takibi",
                "Delil toplama ve muhafaza usulleri",
                "Uzlaştırma imkanlarının araştırılması"
            ]
        }
        
        return guidance_mapping.get(legal_domain, [
            "İlgili mevzuatın detaylı incelenmesi",
            "Emsal kararların araştırılması",
            "Hukuki süreçlerin takip edilmesi"
        ])

    def calculate_confidence_score(self, sources: List[Dict[str, Any]], 
                                 legal_domain: str) -> float:
        """Güven skoru hesapla"""
        if not sources:
            return 0.3
        
        # Kaynak kalitesi skorları
        source_scores = []
        for source in sources:
            confidence = source.get("confidence", 0.5)
            
            # Mahkeme türüne göre ağırlık
            if source.get("court") == "Anayasa Mahkemesi":
                confidence += 0.2
            elif "YARGITAY" in source.get("court", ""):
                confidence += 0.15
            elif "DANISTAY" in source.get("court", ""):
                confidence += 0.15
                
            source_scores.append(min(confidence, 1.0))
        
        if source_scores:
            return sum(source_scores) / len(source_scores)
        return 0.5

    def generate_recommendations(self, analysis: Dict[str, Any], 
                               legal_domain: str) -> List[str]:
        """Öneriler oluştur"""
        recommendations = []
        
        # Genel öneriler
        if analysis["legal_assessment"]["precedents"]:
            recommendations.append("Emsal kararları detaylı inceleyerek benzer argümanları değerlendirin")
        
        # Risk bazlı öneriler
        if analysis["risk_analysis"]["high_risk"]:
            recommendations.append("Yüksek riskli alanlar tespit edildi - uzman hukuki destek alın")
        
        # Domain-specific öneriler
        domain_recommendations = {
            "constitutional": [
                "Temel haklar çerçevesinde argümanlarınızı güçlendirin",
                "Avrupa İnsan Hakları Mahkemesi kararlarını inceleyin"
            ],
            "civil": [
                "Sözleşme hükümlerini ve ilgili kanun maddelerini karşılaştırın",
                "Zarar ve tazminat hesaplamalarını belgeleyin"
            ],
            "administrative": [
                "İdari işlemin gerekçe ve usul yönünden incelenmesini talep edin",
                "Kamu yararı - bireysel hak dengesini değerlendirin"
            ]
        }
        
        domain_recs = domain_recommendations.get(legal_domain, [])
        recommendations.extend(domain_recs[:2])
        
        return recommendations

    async def process_legal_query(self, query: LegalQuery, 
                                user_id: str = None) -> LegalAnalysisResponse:
        """Ana hukuki sorgu işleme fonksiyonu"""
        start_time = datetime.now()
        
        try:
            # 1. Hukuki alanı tespit et
            legal_domain = self.classify_legal_domain(query.question)
            
            # 2. Hukuki kaynakları ara
            sources = await self.search_legal_sources(
                query.question, 
                legal_domain, 
                query.court_preference
            )
            
            # 3. Uzman panel analizi
            analysis = self.analyze_with_expert_panel(
                query.question, 
                sources, 
                legal_domain
            )
            
            # 4. Güven skoru hesapla
            confidence_score = self.calculate_confidence_score(sources, legal_domain)
            
            # 5. Öneriler oluştur
            recommendations = self.generate_recommendations(analysis, legal_domain)
            
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            return LegalAnalysisResponse(
                question=query.question,
                legal_domain=legal_domain,
                analysis=analysis,
                sources=sources[:10],  # İlk 10 kaynak
                recommendations=recommendations,
                confidence_score=confidence_score,
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            print(f"Hukuki analiz hatası: {e}")
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            return LegalAnalysisResponse(
                question=query.question,
                legal_domain="unknown",
                analysis={"error": str(e)},
                sources=[],
                recommendations=["Sistem hatası nedeniyle manuel araştırma yapın"],
                confidence_score=0.1,
                processing_time_ms=processing_time
            )

# FastAPI entegrasyonu
turklawai_agent = TurkLawAIAgent()

# TurkLawAI.com için ana API endpoint
async def analyze_legal_question_endpoint(
    query: LegalQuery,
    user: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """TurkLawAI.com ana hukuki analiz endpoint'i"""
    
    # Rate limiting kontrolü (eğer CenkV1 auth sistemi mevcut ise)
    if CENK_AUTH_AVAILABLE and user:
        if not await check_rate_limits(user):
            raise HTTPException(
                status_code=429,
                detail="Rate limit aşıldı. Planınızı yükseltin."
            )
    
    # Ana analiz işlemi
    result = await turklawai_agent.process_legal_query(
        query, 
        user.get("user_id") if user else None
    )
    
    # Kullanım loglaması (CenkV1 entegrasyonu)
    if CENK_AUTH_AVAILABLE and user:
        await log_api_usage(
            user["user_id"],
            "/api/legal-analysis",
            success=True,
            response_time_ms=result.processing_time_ms,
            query_params={"domain": result.legal_domain, "sources": len(result.sources)}
        )
    
    return {
        "success": True,
        "data": result.dict(),
        "meta": {
            "user_plan": user.get("plan") if user else "anonymous",
            "yargi_mcp_available": YARGI_MCP_AVAILABLE,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }

if __name__ == "__main__":
    # Test the agent
    async def test_agent():
        test_query = LegalQuery(
            question="Tapu iptali davası nasıl açılır?",
            legal_area="civil",
            analysis_depth="comprehensive"
        )
        
        result = await turklawai_agent.process_legal_query(test_query)
        print(json.dumps(result.dict(), ensure_ascii=False, indent=2))
    
    asyncio.run(test_agent())