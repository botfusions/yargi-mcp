# LEGAL_EXPERT_PANEL.md - Hukuki Uzman Panel Sistemi

TurkLawAI.com için SuperClaude Framework tabanlı hukuki uzman panel sistemi.

## Hukuki Uzmanlar

### Türk Hukuk Uzmanları
```yaml
constitutional_law:
  expert: "Prof. Dr. Zühtü Arslan"
  expertise: "Anayasa hukuku, temel haklar, norm denetimi"
  methods: ["constitutional_review", "fundamental_rights_analysis", "proportionality_test"]

civil_law:
  expert: "Prof. Dr. M. Kemal Oğuzman"  
  expertise: "Medeni hukuk, borçlar hukuku, aile hukuku"
  methods: ["contract_analysis", "tort_liability", "property_rights"]

criminal_law:
  expert: "Prof. Dr. Sulhi Dönmezer"
  expertise: "Ceza hukuku, ceza muhakemesi, suç teorisi"
  methods: ["crime_classification", "procedural_analysis", "penalty_assessment"]

administrative_law:
  expert: "Prof. Dr. Lütfi Duran"
  expertise: "İdare hukuku, idari yargı, kamu yönetimi"
  methods: ["administrative_review", "public_service_analysis", "judicial_control"]

commercial_law:
  expert: "Prof. Dr. Ünal Tekinalp"
  expertise: "Ticaret hukuku, şirketler hukuku, rekabet hukuku"
  methods: ["corporate_governance", "competition_analysis", "commercial_transactions"]

labor_law:
  expert: "Prof. Dr. Nuri Çelik"
  expertise: "İş hukuku, sosyal güvenlik, sendika hakları"
  methods: ["employment_rights", "collective_bargaining", "social_security"]
```

## Hukuki Analiz Modları

### 1. Emsal Analizi (Precedent Analysis)
```bash
/legal-panel @karar_metni.pdf --mode "precedent_analysis"
# Yargıtay/Danıştay içtihatları ile karşılaştırma
# Benzer kararlar ve hukuki gerekçelendirmeler
```

### 2. Norm Denetimi (Constitutional Review)
```bash
/legal-panel @kanun_tasarisi.pdf --mode "constitutional_review"
# Anayasaya uygunluk denetimi
# Temel haklar ve özgürlükler analizi
```

### 3. Hukuki Risk Analizi (Legal Risk Assessment)
```bash
/legal-panel @sozlesme.pdf --mode "risk_assessment" --experts "civil_law,commercial_law"
# Potansiyel hukuki sorunlar
# Risk azaltma önerileri
```

### 4. Karşılaştırmalı Hukuk (Comparative Law)
```bash
/legal-panel @mevzuat.pdf --mode "comparative" --focus "eu_law"
# AB hukuku ile karşılaştırma
# Uyumlaştırma önerileri
```

## TurkLawAI.com Entegrasyonu

### Hukuki Araştırma Workflow'u
```yaml
research_stages:
  stage_1: "/legal-panel @user_question --mode discovery"
  stage_2: "/search yargi-mcp --filter relevant_courts"  
  stage_3: "/legal-panel @search_results --mode analysis"
  stage_4: "/legal-panel 'synthesize legal opinion' --mode conclusion"
```

### Otomatik Hukuki Analiz
```python
class LegalAnalysisAgent:
    """TurkLawAI.com için hukuki analiz agent'ı"""
    
    def __init__(self):
        self.yargi_mcp = YargiMCPClient()
        self.legal_experts = LegalExpertPanel()
        
    async def analyze_legal_question(self, question: str):
        # 1. Hukuki alanı tespit et
        legal_domain = self.classify_legal_domain(question)
        
        # 2. İlgili mahkeme kararlarını ara
        decisions = await self.yargi_mcp.search_unified(
            query=question,
            court_types=self.get_relevant_courts(legal_domain)
        )
        
        # 3. Uzman panel analizi
        expert_analysis = await self.legal_experts.analyze(
            question=question,
            decisions=decisions,
            experts=self.get_relevant_experts(legal_domain)
        )
        
        return expert_analysis
```

## Hukuki Sembol Sistemi

```yaml
legal_symbols:
  ⚖️: "hukuki analiz"
  📜: "mevzuat/kanun"
  🏛️: "mahkeme kararı"  
  👨‍⚖️: "hakim görüşü"
  📋: "hukuki gerekçe"
  ⚡: "hukuki ihtilaf"
  🔍: "emsal araştırma"
  📊: "içtihat analizi"
  🎯: "hukuki sonuç"
  ⚠️: "hukuki risk"
```

## Çıktı Formatları

### Hukuki Mütalaa Formatı
```markdown
## ⚖️ HUKUKİ MÜTALAA

**📜 Hukuki Dayanak**: [İlgili mevzuat]
**🏛️ Emsal Kararlar**: [Yargıtay/Danıştay kararları]
**👨‍⚖️ Uzman Görüşü**: [Hukukçu analizi]
**📋 Gerekçe**: [Hukuki mantık]
**🎯 Sonuç**: [Hukuki değerlendirme]
**⚠️ Riskler**: [Potansiyel sorunlar]
```

### Dava Analizi Formatı
```markdown
## 📊 DAVA ANALİZİ

**⚖️ Hukuki Nitelik**: [Dava türü ve hukuki alan]
**📜 Uygulanacak Mevzuat**: [İlgili kanunlar]
**🏛️ İçtihat Durumu**: [Emsal kararlar]
**📋 Tarafların Durumu**: [Hukuki pozisyonlar]
**🎯 Muhtemel Sonuç**: [Karar tahmini]
**⚠️ Dikkat Edilecekler**: [Kritik noktalar]
```

## Performans Hedefleri

```yaml
response_quality:
  legal_accuracy: "> 95%"
  citation_correctness: "> 90%"
  practical_relevance: "> 85%"

response_time:
  simple_question: "< 30 saniye"
  complex_analysis: "< 2 dakika"
  comparative_research: "< 5 dakika"

integration_metrics:
  yargi_mcp_success: "> 98%"
  document_retrieval: "> 95%"
  expert_consensus: "> 80%"
```

Bu sistem TurkLawAI.com'da kullanıcıların hukuki sorularına kapsamlı, uzman düzeyinde yanıtlar verebilir.