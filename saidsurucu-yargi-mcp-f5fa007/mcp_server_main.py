# mcp_server_main.py
import asyncio
import atexit
import logging
import os
import httpx
import json
import time
from collections import defaultdict
from pydantic import HttpUrl, Field 
from typing import Optional, Dict, List, Literal, Any, Union
import urllib.parse
import tiktoken
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.server.dependencies import get_access_token, AccessToken
from fastmcp import Context

# Use standard exception for tool errors
class ToolError(Exception):
    """Tool execution error"""
    pass

# --- Logging Configuration Start ---
LOG_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
if not os.path.exists(LOG_DIRECTORY):
    os.makedirs(LOG_DIRECTORY)
LOG_FILE_PATH = os.path.join(LOG_DIRECTORY, "mcp_server.log")

root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG) 

log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(threadName)s - %(message)s')

file_handler = logging.FileHandler(LOG_FILE_PATH, mode='a', encoding='utf-8')
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG)
root_logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO) 
root_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)
# --- Logging Configuration End ---

# --- Token Counting Middleware ---
class TokenCountingMiddleware(Middleware):
    """Middleware for counting input/output tokens using tiktoken."""
    
    def __init__(self, model: str = "cl100k_base"):
        """Initialize token counting middleware.
        
        Args:
            model: Tiktoken model name (cl100k_base for GPT-4/Claude compatibility)
        """
        self.encoder = tiktoken.get_encoding(model)
        self.model = model
        self.token_stats = defaultdict(lambda: {"input": 0, "output": 0, "calls": 0})
        self.logger = logging.getLogger("token_counter")
        
        # Create separate log file for token metrics
        token_log_path = os.path.join(LOG_DIRECTORY, "token_metrics.log")
        token_handler = logging.FileHandler(token_log_path, mode='a', encoding='utf-8')
        token_formatter = logging.Formatter('%(asctime)s - %(message)s')
        token_handler.setFormatter(token_formatter)
        token_handler.setLevel(logging.INFO)
        self.logger.addHandler(token_handler)
        self.logger.setLevel(logging.INFO)
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken."""
        if not text:
            return 0
        try:
            return len(self.encoder.encode(str(text)))
        except Exception as e:
            logger.warning(f"Token counting failed: {e}")
            return 0
    
    def extract_text_content(self, data: Any) -> str:
        """Extract text content from various data types."""
        if isinstance(data, str):
            return data
        elif isinstance(data, dict):
            # Extract text from common response fields
            text_parts = []
            for key, value in data.items():
                if isinstance(value, str):
                    text_parts.append(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, str):
                            text_parts.append(item)
                        elif isinstance(item, dict) and 'text' in item:
                            text_parts.append(str(item['text']))
            return ' '.join(text_parts)
        elif isinstance(data, list):
            text_parts = []
            for item in data:
                text_parts.append(self.extract_text_content(item))
            return ' '.join(text_parts)
        else:
            return str(data)
    
    def log_token_usage(self, operation: str, input_tokens: int, output_tokens: int, 
                       tool_name: str = None, duration_ms: float = None):
        """Log token usage with structured format."""
        log_data = {
            "operation": operation,
            "tool_name": tool_name,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "duration_ms": duration_ms,
            "timestamp": time.time()
        }
        
        # Update statistics
        key = tool_name if tool_name else operation
        self.token_stats[key]["input"] += input_tokens
        self.token_stats[key]["output"] += output_tokens
        self.token_stats[key]["calls"] += 1
        
        # Log as JSON for easy parsing
        self.logger.info(json.dumps(log_data))
        
        # Also log human-readable format to main logger
        logger.info(f"Token Usage - {operation}" + 
                   (f" ({tool_name})" if tool_name else "") +
                   f": {input_tokens} in + {output_tokens} out = {input_tokens + output_tokens} total")
    
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """Count tokens for tool calls."""
        start_time = time.perf_counter()
        
        # Extract tool name and arguments
        tool_name = getattr(context.message, 'name', 'unknown_tool')
        tool_args = getattr(context.message, 'arguments', {})
        
        # Count input tokens (tool arguments)
        input_text = self.extract_text_content(tool_args)
        input_tokens = self.count_tokens(input_text)
        
        try:
            # Execute the tool
            result = await call_next(context)
            
            # Count output tokens (tool result)
            output_text = self.extract_text_content(result)
            output_tokens = self.count_tokens(output_text)
            
            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Log token usage
            self.log_token_usage("tool_call", input_tokens, output_tokens, 
                               tool_name, duration_ms)
            
            return result
            
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.log_token_usage("tool_call_error", input_tokens, 0, 
                               tool_name, duration_ms)
            raise
    
    async def on_read_resource(self, context: MiddlewareContext, call_next):
        """Count tokens for resource reads."""
        start_time = time.perf_counter()
        
        # Extract resource URI
        resource_uri = getattr(context.message, 'uri', 'unknown_resource')
        
        try:
            # Execute the resource read
            result = await call_next(context)
            
            # Count output tokens (resource content)
            output_text = self.extract_text_content(result)
            output_tokens = self.count_tokens(output_text)
            
            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Log token usage (no input tokens for resource reads)
            self.log_token_usage("resource_read", 0, output_tokens, 
                               resource_uri, duration_ms)
            
            return result
            
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.log_token_usage("resource_read_error", 0, 0, 
                               resource_uri, duration_ms)
            raise
    
    async def on_get_prompt(self, context: MiddlewareContext, call_next):
        """Count tokens for prompt retrievals."""
        start_time = time.perf_counter()
        
        # Extract prompt name
        prompt_name = getattr(context.message, 'name', 'unknown_prompt')
        
        try:
            # Execute the prompt retrieval
            result = await call_next(context)
            
            # Count output tokens (prompt content)
            output_text = self.extract_text_content(result)
            output_tokens = self.count_tokens(output_text)
            
            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Log token usage
            self.log_token_usage("prompt_get", 0, output_tokens, 
                               prompt_name, duration_ms)
            
            return result
            
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.log_token_usage("prompt_get_error", 0, 0, 
                               prompt_name, duration_ms)
            raise
    
    def get_token_stats(self) -> Dict[str, Any]:
        """Get current token usage statistics."""
        return dict(self.token_stats)
    
    def reset_token_stats(self):
        """Reset token usage statistics."""
        self.token_stats.clear()

# --- End Token Counting Middleware ---

# Create FastMCP app directly without authentication wrapper
from fastmcp import FastMCP

def create_app(auth=None):
    """Create FastMCP app with standard capabilities and optional auth."""
    global app
    if auth:
        # Set auth on existing app instead of creating new one
        app.auth = auth
        app.name = "Yargı MCP Server"
        logger.info("MCP server created with Bearer authentication enabled")
    else:
        # Update placeholder app name only
        app.name = "Yargı MCP Server"
        logger.info("MCP server created with standard capabilities (FastMCP handles tools.listChanged automatically)")
    
    # Add token counting middleware
    token_counter = TokenCountingMiddleware()
    app.add_middleware(token_counter)
    logger.info("Token counting middleware added to MCP server")
    
    return app

# --- Module Imports ---
from yargitay_mcp_module.client import YargitayOfficialApiClient
from yargitay_mcp_module.models import (
    YargitayDetailedSearchRequest, YargitayDocumentMarkdown, CompactYargitaySearchResult,
    YargitayBirimEnum, CleanYargitayDecisionEntry
)
from bedesten_mcp_module.client import BedestenApiClient
from bedesten_mcp_module.models import (
    BedestenSearchRequest, BedestenSearchData,
    BedestenDocumentMarkdown, BedestenCourtTypeEnum
)
from bedesten_mcp_module.enums import BirimAdiEnum
from danistay_mcp_module.client import DanistayApiClient
from danistay_mcp_module.models import (
    DanistayKeywordSearchRequest, DanistayDetailedSearchRequest,
    DanistayDocumentMarkdown, CompactDanistaySearchResult
)
from emsal_mcp_module.client import EmsalApiClient
from emsal_mcp_module.models import (
    EmsalSearchRequest, EmsalDocumentMarkdown, CompactEmsalSearchResult
)
from uyusmazlik_mcp_module.client import UyusmazlikApiClient
from uyusmazlik_mcp_module.models import (
    UyusmazlikSearchRequest, UyusmazlikSearchResponse, UyusmazlikDocumentMarkdown,
    UyusmazlikBolumEnum, UyusmazlikTuruEnum, UyusmazlikKararSonucuEnum
)
from anayasa_mcp_module.client import AnayasaMahkemesiApiClient
from anayasa_mcp_module.bireysel_client import AnayasaBireyselBasvuruApiClient
from anayasa_mcp_module.unified_client import AnayasaUnifiedClient
from anayasa_mcp_module.models import (
    AnayasaNormDenetimiSearchRequest,
    AnayasaSearchResult,
    AnayasaDocumentMarkdown,
    AnayasaBireyselReportSearchRequest,
    AnayasaBireyselReportSearchResult,
    AnayasaBireyselBasvuruDocumentMarkdown,
    AnayasaUnifiedSearchRequest,
    AnayasaUnifiedSearchResult,
    AnayasaUnifiedDocumentMarkdown,
    # Removed enum imports - now using Literal strings in models
)
# KIK Module Imports
from kik_mcp_module.client import KikApiClient
from kik_mcp_module.models import ( 
    KikKararTipi, 
    KikSearchRequest,
    KikSearchResult,
    KikDocumentMarkdown 
)

from rekabet_mcp_module.client import RekabetKurumuApiClient
from rekabet_mcp_module.models import (
    RekabetKurumuSearchRequest,
    RekabetSearchResult,
    RekabetDocument,
    RekabetKararTuruGuidEnum
)

from sayistay_mcp_module.client import SayistayApiClient
from sayistay_mcp_module.models import (
    GenelKurulSearchRequest, GenelKurulSearchResponse,
    TemyizKuruluSearchRequest, TemyizKuruluSearchResponse,
    DaireSearchRequest, DaireSearchResponse,
    SayistayDocumentMarkdown,
    SayistayUnifiedSearchRequest, SayistayUnifiedSearchResult,
    SayistayUnifiedDocumentMarkdown
)
from sayistay_mcp_module.enums import DaireEnum, KamuIdaresiTuruEnum, WebKararKonusuEnum
from sayistay_mcp_module.unified_client import SayistayUnifiedClient

# KVKK Module Imports
from kvkk_mcp_module.client import KvkkApiClient
from kvkk_mcp_module.models import (
    KvkkSearchRequest,
    KvkkSearchResult,
    KvkkDocumentMarkdown
)

# BDDK Module Imports
from bddk_mcp_module.client import BddkApiClient
from bddk_mcp_module.models import (
    BddkSearchRequest,
    BddkSearchResult,
    BddkDocumentMarkdown
)


# Create a placeholder app that will be properly initialized after tools are defined
from fastmcp import FastMCP

# Placeholder app for decorators - will be replaced in create_app() after all tools are defined
app = FastMCP("Yargı MCP Server Placeholder")

# --- Tool Documentation Resources ---
@app.resource("docs://tools/yargitay")
async def get_yargitay_tools_documentation() -> str:
    """Get document content as Markdown."""
    return """
# Yargıtay (Court of Cassation) Tools Documentation

## Court Hierarchy and Position
Yargıtay is Turkey's highest civil and criminal court. It serves as the final appellate authority and establishes legal precedents for civil and criminal cases.

**Dual API System:**
- **Primary API (search_yargitay_detailed)**: Official karararama.yargitay.gov.tr
- **Bedesten API (search_bedesten_unified)**: Unified access to bedesten.adalet.gov.tr (see docs://tools/bedesten_unified)

## Chamber Filtering Options (52 Total)

### Civil Chambers (Hukuk Daireleri)
- **Civil General Assembly** (Hukuk Genel Kurulu)
- **1st Civil Chamber** through **23rd Civil Chamber** (23 civil chambers)
- **Civil Chambers Presidents Board** (Hukuk Daireleri Başkanlar Kurulu)

### Criminal Chambers (Ceza Daireleri)  
- **Criminal General Assembly** (Ceza Genel Kurulu)
- **1st Criminal Chamber** through **23rd Criminal Chamber** (23 criminal chambers)
- **Criminal Chambers Presidents Board** (Ceza Daireleri Başkanlar Kurulu)

### General Assemblies
- **Grand General Assembly** (Büyük Genel Kurulu)

## Search Techniques

### Primary API (search_yargitay_detailed)
```
Simple search: "mülkiyet"
AND operator: "mülkiyet AND tapu"
OR operator: "mülkiyet OR tapu" 
NOT operator: "mülkiyet NOT satış"
Wildcard: "mülk*"
Exact phrase: "\"mülkiyet hakkı\""
```

### Bedesten API (search_bedesten_unified)
For detailed usage, see docs://tools/bedesten_unified
```
Regular search: phrase="mülkiyet kararı", court_types=["YARGITAYKARARI"]
Exact phrase: phrase="\"mülkiyet kararı\"", court_types=["YARGITAYKARARI"]
Date filtering: kararTarihiStart="2024-01-01T00:00:00.000Z"
```

## Usage Scenarios
- **Precedent research**: Supreme court decisions on specific topics
- **Chamber-specific search**: Relevant chambers for specific legal areas  
- **Historical analysis**: Decision trends in specific periods
- **Jurisprudence tracking**: Changes in legal opinions

## Best Practices
1. **Use dual APIs**: Try both APIs for maximum coverage
2. **Chamber filtering**: Select chambers based on relevant legal area
3. **Exact phrases**: Use "\"term\"" for precise terms in Bedesten API
4. **Date range**: Focus on last 2-3 years for recent developments

## Common Civil Chambers
- **1st Civil**: Property, land registry, liens
- **4th Civil**: Labor law, collective agreements
- **11th Civil**: Insurance, social security
- **15th Civil**: Compensation, tort
- **21st Civil**: Execution and bankruptcy

## Common Criminal Chambers  
- **1st Criminal**: General criminal offenses
- **8th Criminal**: Economic and commercial crimes
- **12th Criminal**: Official misconduct
"""

@app.resource("docs://tools/danistay")  
async def get_danistay_tools_documentation() -> str:
    """Get document content as Markdown."""
    return """
# Danıştay (Council of State) Tools Documentation

## Court Hierarchy and Position
Danıştay is Turkey's highest administrative court. It makes final decisions on administrative acts and actions.

**Triple API System:**
- **Keyword API (search_danistay_by_keyword)**: AND/OR/NOT logic
- **Detailed API (search_danistay_detailed)**: Comprehensive criteria  
- **Bedesten API (search_bedesten_unified)**: Unified access (see docs://tools/bedesten_unified)

## Chamber Filtering Options (27 Total)

### Main Councils
- **Grand General Assembly** (Büyük Gen.Kur.)
- **Administrative Cases Council** (İdare Dava Daireleri Kurulu)
- **Tax Cases Council** (Vergi Dava Daireleri Kurulu)
- **Precedents Unification Council** (İçtihatları Birleştirme Kurulu)

### Chambers (1-17)
- **1st Chamber** through **17th Chamber** (Administrative case chambers)

### Military Courts
- **Military High Administrative Court** (Askeri Yüksek İdare Mahkemesi)
- **Military High Administrative Court 1st-3rd Chambers**

## Search Techniques

### Keyword API
```
AND logic: andKelimeler=["imar", "plan"]
OR logic: orKelimeler=["iptal", "yürütmeyi durdurma"]  
NOT logic: notKelimeler=["ceza"]
```

### Detailed API
```
Chamber selection: daire="3. Daire"
Case year: esasYil="2024"
Decision date: kararTarihiBaslangic="01.01.2024"
Legislation: mevzuatId=123
```

### Bedesten API  
```
Regular: phrase="idari işlem"
Exact: phrase="\"idari işlem\""
Date: kararTarihiStart="2024-01-01T00:00:00.000Z"
```

## Usage Scenarios
- **Administrative law research**: Public administration decisions
- **Tax law**: Financial matters and tax disputes
- **Urban planning law**: City planning and building permits
- **Personnel law**: Civil servant rights

## Common Chamber Specializations
- **1st Chamber**: Municipal, urban planning, environment  
- **2nd Chamber**: Tax, customs, financial
- **3rd Chamber**: Personnel, personal rights
- **5th Chamber**: Administrative fines
- **8th Chamber**: Higher education, education
- **10th Chamber**: Health, social security

## Best Practices
1. **Triple API**: Use all three APIs for maximum coverage
2. **Chamber selection**: Choose specialized chambers by subject area
3. **Mevzuat bağlantısı**: İlgili kanun/tüzükle filtreleme
4. **Kesin terim**: İdari hukuk terminolojisi için exact search
"""

@app.resource("docs://tools/constitutional_court")
async def get_constitutional_court_tools_documentation() -> str:
    """Get document content as Markdown."""
    return """
# Anayasa Mahkemesi (Constitutional Court) Tools Documentation

## Court Position
Constitutional Court is Turkey's highest judicial body. It has two main functions:

### 1. Norm Control (Norm Control)
**Tool**: search_anayasa_norm_denetimi_decisions
- Reviews constitutional compliance of laws and regulations
- Abstract and concrete norm control

### 2. Individual Application (Individual Application)  
**Tool**: search_anayasa_bireysel_basvuru_report
- Citizens' fundamental rights violation applications
- Turkey's human rights protection mechanism

## Norm Control Features

### Comprehensive Filtering
- **Application type**: Annulment, Objection, Other
- **Applicant**: President, Parliament, Courts
- **Legislation type**: Law, Decree, Regulation, Rules of procedure
- **Result type**: Annulment, Rejection, Partial annulment

### Advanced Search
- **Member names**: Full names of participating justices
- **Rapporteur**: Case rapporteur 
- **Dissenting opinion**: Minority opinion, different view
- **Press release**: Important decisions

## Bireysel Başvuru Özellikleri

### Temel Haklar Kategorileri
- **Yaşam hakkı**: Ölüm olayları, güvenlik
- **Adil yargılanma**: Süre, tarafsızlık, duruşma hakkı  
- **İfade özgürlüğü**: Basın, düşünce, akademik özgürlük
- **Din özgürlüğü**: İbadet, vicdan özgürlüğü
- **Mülkiyet hakkı**: Kamulaştırma, tapu
- **Özel hayat**: Gizlilik, aile hayatı

### Başvuru Süreci
- **Yurtiçi yollar**: Önce mahkeme kararı gerekli
- **Süre sınırı**: 30 gün (60 gün istisnai)
- **Kabul edilebilirlik**: Ön inceleme kriterleri

## Paginated Content (5,000 characters)
Her iki tool da sayfalanmış Markdown döndürür:
- **page_number**: Sayfa numarası (1'den başlar)
- **total_pages**: Toplam sayfa sayısı
- **current_page**: Mevcut sayfa

## Usage Scenarios

### Norm Denetimi
- **Kanun anayasaya uygunluk**: Yeni çıkan kanunların kontrolü
- **Mahkeme iptali**: Kanunun belirli maddeleri
- **Mevzuat uyum**: Anayasa değişikliği sonrası

### Bireysel Başvuru
- **İnsan hakları araştırması**: AİHM öncesi iç hukuk
- **Temel hak ihlalleri**: Sistematik ihlal tespiti
- **Emsal karar**: Benzer davalar için içtihat

## Parameter Details
### search_anayasa_norm_denetimi_decisions
- **keywords_all**: Keywords for AND logic (all must be present)
- **keywords_any**: Keywords for OR logic (any can be present) 
- **keywords_exclude**: Keywords to exclude from results
- **period**: Constitutional period - "ALL", "1" (1961 Constitution), "2" (1982 Constitution)
- **case_number_esas**: Case registry number (e.g., '2023/123')
- **decision_number_karar**: Decision number (e.g., '2023/456')
- **first_review_date_start/end**: First review date range (DD/MM/YYYY)
- **decision_date_start/end**: Decision date range (DD/MM/YYYY)
- **application_type**: "ALL", "1" (İptal), "2" (İtiraz), "3" (Diğer)
- **applicant_general_name**: General applicant name
- **applicant_specific_name**: Specific applicant name
- **official_gazette_date_start/end**: Official Gazette date range
- **official_gazette_number_start/end**: Official Gazette number range
- **has_press_release**: "ALL", "0" (No), "1" (Yes)
- **has_dissenting_opinion**: "ALL", "0" (No), "1" (Yes)
- **has_different_reasoning**: "ALL", "0" (No), "1" (Yes)
- **attending_members_names**: List of attending members' exact names
- **rapporteur_name**: Rapporteur's exact name
- **norm_type**: Type of reviewed norm (law, decree, regulation, etc.)
- **norm_id_or_name**: Number or name of the norm
- **norm_article**: Article number of the norm
- **review_outcomes**: List of review outcomes
- **reason_for_final_outcome**: Main reason for decision outcome
- **basis_constitution_article_numbers**: Supporting Constitution article numbers
- **results_per_page**: Results per page (10, 20, 30, 40, 50)
- **page_to_fetch**: Page number to fetch
- **sort_by_criteria**: Sort criteria ('KararTarihi', 'YayinTarihi', 'Toplam')

### search_anayasa_bireysel_basvuru_report
- **keywords**: Keywords for AND logic (all must be present)
- **page_to_fetch**: Page number for the report (default: 1)

### Document Tools
- **document_url**: URL path or full URL of the decision
- **page_number**: Page number for paginated content (1-indexed, default: 1)

## Best Practices
1. **Norm control önce**: Kanun iptal edilmiş mi kontrol
2. **Bireysel başvuru ikinci**: Kişisel hak ihlalleri için
3. **Tarih aralığı**: Anayasa değişiklikleri sonrası dönemler
4. **Anahtar kelime kombinasyonu**: Temel hak + konu alanı
5. **Sayfa yönetimi**: Uzun kararlarda sayfa sayfa okuyun
"""

@app.resource("docs://tools/emsal")
async def get_emsal_tools_documentation() -> str:
    """Get document content as Markdown."""
    return """
# Emsal (UYAP Precedent System) Tools Documentation

## System Position
Central precedent decision system providing access to all court decisions through the UYAP system.

## Court Options
- **Yargıtay**: First and second instance courts
- **Danıştay**: Administrative court decisions
- **Other**: Regional courts of justice, civil courts

## Advanced Filtering Features
- **Court type**: Civil, criminal, administrative
- **Case/Decision number**: File tracking system
- **Date range**: Flexible date selection
- **Content search**: Keyword search within decision text

## Usage Scenarios
- **Kapsamlı emsal**: Tüm mahkeme seviyelerinden karar toplama
- **Güncel içtihat**: En son hukuki gelişmeler
- **Cross-reference**: Farklı mahkeme görüşlerini karşılaştırma

## Best Practices
1. **Spesifik terimler**: Hukuki terminoloji kullanın
2. **Geniş arama**: Önce genel, sonra spesifik
3. **Tarih stratejisi**: Mevzuat değişiklikleri dikkate alın
4. **Cross-platform**: Aynı konuyu farklı mahkemelerde arayın
"""

@app.resource("docs://tools/uyusmazlik")
async def get_uyusmazlik_tools_documentation() -> str:
    """Get document content as Markdown."""
    return """
# Uyuşmazlık Mahkemesi Tools Documentation

## Court Position
Adli ve idari yargı arasındaki görev uyuşmazlıklarını çözen özel yetkili mahkeme.

## Dispute Types
- **Görev uyuşmazlığı**: Hangi mahkeme bakacak konusunda anlaşmazlık
- **Hüküm uyuşmazlığı**: Çelişkili mahkeme kararları
- **Yetki uyuşmazlığı**: Yerel yetki sorunları

## Form-Based Search Criteria
- **Karar türü**: Müspet, menfi, hüküm uyuşmazlığı
- **Taraf mahkemeler**: Adli-idari yargı organları
- **Konu alanı**: Hukuk dalı bazlı filtreleme
- **Tarih aralığı**: Karar tarihi seçimi

## Usage Scenarios
- **Yargı türü belirleme**: Hangi mahkemenin yetkili olduğu
- **Çelişkili kararlar**: Farklı mahkeme kararları arasındaki uyuşmazlık
- **Yetki sorunları**: Mahkeme yetkisi tartışmaları

## Best Practices
1. **Net kriterler**: Arama kriterlerini spesifik tutun
2. **Taraf bilgisi**: Uyuşmazlık taraflarını belirtin
3. **Konu odaklı**: İlgili hukuk dalını seçin
"""

@app.resource("docs://tools/kik")
async def get_kik_tools_documentation() -> str:
    """Get document content as Markdown."""
    return """
# KİK (Kamu İhale Kurumu) Tools Documentation

## Kurum Konumu
Kamu ihale uyuşmazlıklarının ilk ve son merci çözüm organı. Kamu İhale Kanunu kapsamındaki tüm ihaleler için yetkili.

## Decision Types
- **Uyuşmazlık**: İhale süreç itirazları
- **Düzenleyici**: Mevzuat ve uygulama kararları  
- **Mahkeme**: Mahkeme kararlarının uygulanması

## Filtreleme Seçenekleri
- **Karar numarası**: 2024/UH.II-1766 formatında
- **Tarih aralığı**: Karar tarihi filtreleme
- **İhaleyi yapan idare**: Bakanlık, belediye, hastane, üniversite
- **Başvuru sahibi**: Şirket, firma adı
- **İhale konusu**: Mal, hizmet, yapım işi

## Sayfalanmış İçerik Özelliği
5.000 karakterlik sayfalar halinde Markdown formatında sunulur.

## Usage Scenarios
- **İhale hukuku**: Kamu alımları, süreç kuralları
- **Başvuru hazırlığı**: Benzer davalar, emsal kararlar
- **Mevzuat yorumu**: Kamu İhale Kanunu uygulaması
- **İtiraz stratejisi**: Başarılı itiraz örnekleri

## İhale Süreç Aşamaları
1. **İhale öncesi**: İlan, şartname hazırlığı
2. **İhale aşaması**: Teklif verme, değerlendirme
3. **İhale sonrası**: Sonuç bildirimi, itirazlar
4. **Sözleşme**: İmza, uygulama

## Parameter Details
### search_kik_decisions  
- **karar_tipi**: Decision type - "rbUyusmazlik" (disputes), "rbDuzenleyici" (regulatory), "rbMahkeme" (court)
- **karar_no**: Decision number (e.g., '2024/UH.II-1766')
- **karar_tarihi_baslangic**: Decision start date (DD.MM.YYYY format)
- **karar_tarihi_bitis**: Decision end date (DD.MM.YYYY format)
- **basvuru_sahibi**: Applicant name/company
- **ihaleyi_yapan_idare**: Procuring entity (ministry, municipality, etc.)
- **basvuru_konusu_ihale**: Tender subject/description
- **karar_metni**: Text search with operators: +word (AND), -word (exclude)
- **yil**: Decision year
- **resmi_gazete_tarihi**: Official Gazette date (DD.MM.YYYY)
- **resmi_gazete_sayisi**: Official Gazette number
- **page**: Results page number

### get_kik_document_markdown
- **karar_id**: Base64 encoded decision identifier from search results
- **page_number**: Page number for paginated content (1-indexed, default: 1)

## Best Practices
1. **İhale türü**: Açık, belli istekliler arası, pazarlık
2. **Süreç aşaması**: Hangi aşamada sorun olduğu
3. **Hukuki dayanak**: İlgili KİK kanun maddesi
4. **Sayfa yönetimi**: Uzun kararları bölümler halinde okuyun
"""

@app.resource("docs://tools/rekabet")
async def get_rekabet_tools_documentation() -> str:
    """Get document content as Markdown."""
    return """
# Rekabet Kurumu (Competition Authority) Tools Documentation

## Kurum Konumu  
Rekabet hukuku ihlallerini inceleyen ve ceza veren idari otorite. Rekabet Kanunu kapsamında yetkili.

## Decision Types
- **Birleşme ve Devralma**: Şirket satın almaları, füzyonlar
- **Rekabet İhlali**: Anlaşma, hakim durum kötüye kullanımı
- **Menfi Tespit ve Muafiyet**: İhlal yok kararları, muafiyetler
- **Özelleştirme**: Kamu şirketleri satışı onayları

## Filtreleme Özellikleri
- **PDF metin arama**: Tam metin içinde kelime arama
- **Karar türü**: Spesifik kategori seçimi
- **Tarih aralığı**: 1997'den günümüze karar arşivi
- **Sektör**: Telekomünikasyon, bankacılık, enerji, perakende

## Rekabet Hukuku Temel Kavramları
- **Hakim durum**: Pazar gücü
- **Kartel**: Fiyat anlaşması
- **Dikey anlaşmalar**: Tedarikci-bayi ilişkileri
- **Konsantrasyon**: Birleşme işlemleri

## Usage Scenarios
- **Antitrust araştırması**: Tekelleşme, kartel soruşturmaları  
- **Birleşme incelemesi**: M&A transaction değerlendirmesi
- **Sektör analizi**: Belirli pazarlardaki rekabet durumu
- **Ceza hesaplama**: İhlal cezası örnekleri

## Sektörel Uzmanlık Alanları
1. **Telekomünikasyon**: Operatör rekabeti
2. **Enerji**: Elektrik, doğalgaz piyasası
3. **Finans**: Bankacılık, sigorta
4. **Perakende**: Zincir mağazalar
5. **İnşaat**: Müteahhitlik sektörü

## Parameter Details
### search_rekabet_kurumu_decisions
- **sayfaAdi**: Search in decision title (Başlık)
- **YayinlanmaTarihi**: Publication date (DD.MM.YYYY format)
- **PdfText**: Search text. For exact phrases use double quotes: "vertical agreement"
- **KararTuru**: Decision type - "Birleşme ve Devralma", "Rekabet İhlali", etc.
- **KararSayisi**: Decision number (Karar Sayısı)
- **KararTarihi**: Decision date (DD.MM.YYYY format)
- **page**: Page number for results list

### get_rekabet_kurumu_document
- **karar_id**: GUID from search results
- **page_number**: Requested page for Markdown content (1-indexed, default: 1)

## Best Practices
1. **Sektör odaklı**: İlgili sektörde arama yapın
2. **Karar türü seçimi**: İhtiyacınıza uygun kategori
3. **Güncel mevzuat**: Mevzuat değişiklikleri takibi
4. **Sayfa yönetimi**: Uzun analizleri bölümler halinde
"""

@app.resource("docs://tools/bedesten_unified")
async def get_bedesten_unified_documentation() -> str:
    """Get document content as Markdown."""
    return """
# Bedesten API Mahkemeleri Tools Documentation

## Bedesten API Sistemi
bedesten.adalet.gov.tr üzerinden Türk adalet sistemi hiyerarşisindeki mahkemelere erişim.

## Mahkeme Hiyerarşisi Kapsamı

### 1. Yerel Hukuk Mahkemeleri (Local Civil Courts)
**Tool**: search_yerel_hukuk_bedesten
- **Konum**: İlk derece mahkemeler
- **Yetki**: Hukuki uyuşmazlıklar (sözleşme, tazminat, mülkiyet)
- **Önem**: Toplumun günlük hukuki sorunları

### 2. İstinaf Hukuk Mahkemeleri (Civil Courts of Appeals)  
**Tool**: search_istinaf_hukuk_bedesten
- **Konum**: Orta derece (Yerel -> İstinaf -> Yargıtay)
- **Yetki**: Yerel mahkeme kararlarına itiraz
- **Önem**: Temyiz öncesi son kontrol

### 3. Kanun Yararına Bozma (KYB)
**Tool**: search_kyb_bedesten  
- **Konum**: Olağanüstü kanun yolu
- **Başvuru sahibi**: Cumhuriyet Başsavcılığı
- **Amaç**: Hukuka aykırı kararları düzeltme
- **Özellik**: Sanık aleyhine olsa bile hukuk yararına

## Ortak Bedesten API Özellikleri

### Tarih Filtreleme (ISO 8601)
```
Başlangıç: kararTarihiStart="2024-01-01T00:00:00.000Z"
Bitiş: kararTarihiEnd="2024-12-31T23:59:59.999Z"
Tek gün: "2024-06-25T00:00:00.000Z" - "2024-06-25T23:59:59.999Z"
```

### Kesin Cümle Arama
```
Normal: phrase="sözleşme ihlali"  (kelimeler ayrı ayrı)
Kesin: phrase="\"sözleşme ihlali\""  (tam cümle)
```

### Sayfalama
- **pageSize**: 1-100 arası sonuç sayısı
- **pageNumber**: Sayfa numarası (1'den başlar)

## Mahkeme Özellikleri

### Yerel Hukuk Mahkemeleri
**Yaygın Dava Türleri**:
- Sözleşme ihlali davaları
- Tazminat talepleri  
- Mülkiyet uyuşmazlıkları
- Aile hukuku (boşanma, nafaka)
- Ticari uyuşmazlıklar (küçük-orta ölçek)

**Kullanım Senaryoları**:
- Günlük hukuki sorunlar
- Vatandaş hakları
- Ticaret hukuku temelleri
- İcra takipleri

### İstinaf Hukuk Mahkemeleri  
**İnceleme Kapsamı**:
- Yerel mahkeme kararlarının kontrolü
- Hukuki ve maddi hata arayışı
- Yeniden yargılama (sınırlı)

**Kullanım Senaryoları**:
- Temyiz stratejisi gelişitirme
- İstinaf mahkemesi içtihatları
- Yerel-üst mahkeme uyumu analizi

### Kanun Yararına Bozma (KYB)
**Başvuru Koşulları**:
- Kesinleşmiş mahkeme kararı
- Hukuka açık aykırılık
- Cumhuriyet Başsavcılığı başvurusu
- Sanık aleyhine sonuç doğurmama

**Kullanım Senaryoları**:
- Sistematik hukuki hatalar
- İçtihat birliğini sağlama
- Hukuk güvenliği
- Nadir ve özel hukuki durumlar

## Arama Stratejileri

### Hiyerarşik Arama
```
1. Yerel mahkeme -> Gündelik sorunlar
2. İstinaf -> Kompleks yorumlar  
3. KYB -> İstisnai hukuki durumlar
```

### Kesin Terim Kullanımı
```
Yerel: "\"sözleşme ihlali\""
İstinaf: "\"temyiz incelemesi\""  
KYB: "\"kanun yararına bozma\""
```

### Tarih Stratejisi
- **Son 2 yıl**: Güncel içtihat
- **5-10 yıl**: Yerleşik görüşler
- **Mevzuat değişikliği sonrası**: Yeni uygulamalar

## Best Practices
1. **Hiyerarşi takibi**: Alt mahkemeden üst mahkemeye
2. **Kesin cümle**: Hukuki terimler için "\"terim\""
3. **Tarih aralığı**: İlgili mevzuat dönemleri
4. **Cross-reference**: Aynı konuyu farklı seviyelerde
5. **Minimal sonuç**: KYB çok nadir, az sonuç beklenir

## Document ID Formatı
Tüm Bedesten mahkemeleri documentId döndürür:
- **Format**: Alfanumerik string
- **Kullanım**: get_*_bedesten_document_markdown fonksiyonları
- **İçerik**: HTML/PDF -> Markdown conversion
"""

@app.resource("docs://tools/sayistay")
async def get_sayistay_tools_documentation() -> str:
    """Get document content as Markdown."""
    return """
# Sayıştay (Court of Accounts) Tools Documentation

## Sayıştay'ın Konumu
Türkiye'nin en üst mali denetim organı. Kamu kaynaklarının kullanımını denetler ve mali disiplini sağlar.

## Üç Tür Karar Sistemi

### 1. Genel Kurul Kararları (Interpretive Rulings)
**Tool**: search_sayistay_genel_kurul
- **İşlev**: Mali mevzuat yorumlama
- **Kapsam**: 2006-2024 yılları arası
- **Özellik**: Bağlayıcı yorumlar

**Filtreleme Seçenekleri**:
- **Karar numarası**: Spesifik karar arama
- **Tarih aralığı**: Başlangıç-bitiş tarihleri
- **Karar tamamı**: Tam metin arama (400 karakter)

### 2. Temyiz Kurulu Kararları (Appeals Board)
**Tool**: search_sayistay_temyiz_kurulu  
- **İşlev**: Daire kararlarına itiraz incelemesi
- **8 Daire Filtreleme**: Uzmanlık alanlarına göre

**Daire Uzmanlaşmaları**:
- **1. Daire**: Genel bütçeli idareler
- **2. Daire**: Mahalli idareler  
- **3. Daire**: Sosyal güvenlik kurumları
- **4. Daire**: KİT ve bağlı ortaklıklar
- **5. Daire**: Düzenleyici kuruluşlar
- **6. Daire**: Vakıflar, dernekler
- **7. Daire**: Üniversiteler, eğitim
- **8. Daire**: Yatırım projeleri

**Filtreleme Seçenekleri**:
- **İdare türü**: Bakanlık, belediye, üniversite, KİT
- **Temyiz karar**: Tam metin arama
- **Konu sınıflandırması**: Harcama, gelir, taşınır-taşınmaz

### 3. Daire Kararları (Chamber Decisions)  
**Tool**: search_sayistay_daire
- **İşlev**: İlk derece denetim bulguları
- **8 Daire**: Aynı uzmanlaşma alanları

**Filtreleme Seçenekleri**:
- **Yargılama dairesi**: 1-8 arası daire seçimi
- **Hesap yılı**: Mali yıl bazlı
- **Web karar metni**: İçerik arama

## Ortak Özellikler

### Sayfalanmış Markdown
Tüm Sayıştay belgeleri sayfalanmış format:
- **5.000 karakter** per sayfa
- **page_number**: Sayfa numarası
- **total_pages**: Toplam sayfa

### Tarih Aralığı Desteği
- **Genel Kurul**: 2006-2024 (18 yıl)
- **Temyiz/Daire**: Mevcut veriler üzerinde

## Usage Scenarios

### Mali Mevzuat Araştırması
```
Genel Kurul -> Hukuki yorum
Temyiz -> Uygulama detayları  
Daire -> Spesifik örnekler
```

### Kamu Mali Yönetimi
- **Bütçe uygulama**: Harcama usulleri
- **İhale süreçleri**: Kamu alımları denetimi
- **Personel giderleri**: Özlük hakları mali boyutu
- **Yatırım projeleri**: Büyük ölçekli projeler

### Kurumsal Denetim
- **KİT yönetimi**: Kamu iktisadi teşebbüsleri
- **Belediye maliyesi**: Yerel yönetim harcamaları  
- **Üniversite bütçesi**: Yükseköğretim mali yönetimi
- **Sosyal güvenlik**: SGK, Bağ-Kur mali işlemleri

## Arama Stratejileri

### Hiyerarşik Yaklaşım
1. **Genel Kurul**: Konunun hukuki çerçevesi
2. **Temyiz**: Tartışmalı uygulamalar
3. **Daire**: Günlük uygulama örnekleri

### Daire Bazlı Strateji
```
Mali konu -> İlgili daire seçimi -> Derinlemesine arama
Örnek: KİT mali sorunları -> 4. Daire
```

### Tarih Odaklı Strateji
- **Son 2 yıl**: Güncel uygulamalar
- **5 yıl**: Yerleşik görüşler  
- **2006-2024**: Tarihsel gelişim

## Best Practices
1. **Daire uzmanlaşması**: İlgili kuruma uygun daire
2. **Hiyerarşik sıralama**: Genel Kurul -> Temyiz -> Daire
3. **Mali dönem**: Bütçe yılları bazında arama
4. **Teknik terimler**: Mali mevzuat terminolojisi
5. **Cross-reference**: Farklı seviyelerden görüş karşılaştırma

## İdare Türü Kodları
- **1**: Genel bütçeli
- **2**: Özel bütçeli  
- **3**: Düzenleyici kuruluşlar
- **4**: Mahalli idareler
- **5**: Sosyal güvenlik
- **6**: KİT
- **7**: Vakıf/dernek
- **8**: Diğer kamu kuruluşları
"""

@app.resource("docs://tools/kvkk")
async def get_kvkk_tools_documentation() -> str:
    """Get document content as Markdown."""
    return """
# KVKK (Personal Data Protection Authority) Tools

## Overview
KVKK (Kişisel Verilerin Korunması Kurulu) - Turkey's GDPR equivalent authority.

## Search Features
- **Brave Search API**: Searches kvkk.gov.tr with Turkish terms
- **Site-targeted**: Auto `site:kvkk.gov.tr "karar özeti"`
- **Pagination**: page and pageSize parameters
- **5,000-char pages**: Paginated Markdown documents

## Common Search Terms
**Violations**: "veri ihlali", "açık rıza", "idari para cezası"
**Compliance**: "GDPR uyum", "veri koruma", "güvenlik tedbirleri"
**Sectors**: "e-ticaret", "bankacılık", "sağlık", "mobil uygulama"

## Key Decision Types
- **Fines**: Data breaches, consent violations
- **Compliance**: GDPR alignment, corporate policies  
- **Breach notifications**: 24-hour rule violations

## Usage Tips
1. Use Turkish legal terms for best results
2. Combine sector + violation type searches
3. Use page_number for long decisions
4. Focus on recent 2-3 years for current practices
"""


# --- API Client Instances ---
yargitay_client_instance = YargitayOfficialApiClient()
danistay_client_instance = DanistayApiClient()
emsal_client_instance = EmsalApiClient()
uyusmazlik_client_instance = UyusmazlikApiClient()
anayasa_norm_client_instance = AnayasaMahkemesiApiClient()
anayasa_bireysel_client_instance = AnayasaBireyselBasvuruApiClient()
anayasa_unified_client_instance = AnayasaUnifiedClient()
kik_client_instance = KikApiClient()
rekabet_client_instance = RekabetKurumuApiClient()
bedesten_client_instance = BedestenApiClient()
sayistay_client_instance = SayistayApiClient()
sayistay_unified_client_instance = SayistayUnifiedClient()
kvkk_client_instance = KvkkApiClient()
bddk_client_instance = BddkApiClient()


KARAR_TURU_ADI_TO_GUID_ENUM_MAP = {
    "": RekabetKararTuruGuidEnum.TUMU,  # Keep for backward compatibility
    "ALL": RekabetKararTuruGuidEnum.TUMU,  # Map "ALL" to TUMU
    "Birleşme ve Devralma": RekabetKararTuruGuidEnum.BIRLESME_DEVRALMA,
    "Diğer": RekabetKararTuruGuidEnum.DIGER,
    "Menfi Tespit ve Muafiyet": RekabetKararTuruGuidEnum.MENFI_TESPIT_MUAFIYET,
    "Özelleştirme": RekabetKararTuruGuidEnum.OZELLESTIRME,
    "Rekabet İhlali": RekabetKararTuruGuidEnum.REKABET_IHLALI,
}

# --- MCP Tools for Yargitay ---
"""
@app.tool(
    description="Search Yargıtay decisions with 52 chamber filtering and advanced operators",
    annotations={
        "readOnlyHint": True,
        "openWorldHint": True,
        "idempotentHint": True
    }
)
async def search_yargitay_detailed(
    arananKelime: str = Field("", description="Turkish search keyword. Supports +required -excluded \"exact phrase\" operators"),
    birimYrgKurulDaire: str = Field("ALL", description="Chamber selection (52 options: Civil/Criminal chambers, General Assemblies)"),
    esasYil: str = Field("", description="Case year for 'Esas No'."),
    esasIlkSiraNo: str = Field("", description="Starting sequence number for 'Esas No'."),
    esasSonSiraNo: str = Field("", description="Ending sequence number for 'Esas No'."),
    kararYil: str = Field("", description="Decision year for 'Karar No'."),
    kararIlkSiraNo: str = Field("", description="Starting sequence number for 'Karar No'."),
    kararSonSiraNo: str = Field("", description="Ending sequence number for 'Karar No'."),
    baslangicTarihi: str = Field("", description="Start date for decision search (DD.MM.YYYY)."),
    bitisTarihi: str = Field("", description="End date for decision search (DD.MM.YYYY)."),
    # pageSize: int = Field(10, ge=1, le=10, description="Number of results per page."),
    pageNumber: int = Field(1, ge=1, description="Page number to retrieve.")
) -> CompactYargitaySearchResult:
    # Search Yargıtay decisions using primary API with 52 chamber filtering and advanced operators.
    
    # Convert "ALL" to empty string for API compatibility
    if birimYrgKurulDaire == "ALL":
        birimYrgKurulDaire = ""
    
    pageSize = 10  # Default value
    
    search_query = YargitayDetailedSearchRequest(
        arananKelime=arananKelime,
        birimYrgKurulDaire=birimYrgKurulDaire,
        esasYil=esasYil,
        esasIlkSiraNo=esasIlkSiraNo,
        esasSonSiraNo=esasSonSiraNo,
        kararYil=kararYil,
        kararIlkSiraNo=kararIlkSiraNo,
        kararSonSiraNo=kararSonSiraNo,
        baslangicTarihi=baslangicTarihi,
        bitisTarihi=bitisTarihi,
        siralama="3",
        siralamaDirection="desc",
        pageSize=pageSize,
        pageNumber=pageNumber
    )
    
    logger.info(f"Tool 'search_yargitay_detailed' called: {search_query.model_dump_json(exclude_none=True, indent=2)}")
    try:
        api_response = await yargitay_client_instance.search_detailed_decisions(search_query)
        if api_response and api_response.data and api_response.data.data:
            # Convert to clean decision entries without arananKelime field
            clean_decisions = [
                CleanYargitayDecisionEntry(
                    id=decision.id,
                    daire=decision.daire,
                    esasNo=decision.esasNo,
                    kararNo=decision.kararNo,
                    kararTarihi=decision.kararTarihi,
                    document_url=decision.document_url
                )
                for decision in api_response.data.data
            ]
            return CompactYargitaySearchResult(
                decisions=clean_decisions,
                total_records=api_response.data.recordsTotal if api_response.data else 0,
                requested_page=search_query.pageNumber,
                page_size=search_query.pageSize)
        logger.warning("API response for Yargitay search did not contain expected data structure.")
        return CompactYargitaySearchResult(decisions=[], total_records=0, requested_page=search_query.pageNumber, page_size=search_query.pageSize)
    except Exception as e:
        logger.exception(f"Error in tool 'search_yargitay_detailed'.")
        raise

@app.tool(
    description="Get Yargıtay decision text in Markdown format",
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True
    }
)
async def get_yargitay_document_markdown(id: str) -> YargitayDocumentMarkdown:
    # Get Yargıtay decision text as Markdown. Use ID from search results.
    logger.info(f"Tool 'get_yargitay_document_markdown' called for ID: {id}")
    if not id or not id.strip(): raise ValueError("Document ID must be a non-empty string.")
    try:
        return await yargitay_client_instance.get_decision_document_as_markdown(id)
    except Exception as e:
        logger.exception(f"Error in tool 'get_yargitay_document_markdown'.")
        raise
"""

# --- MCP Tools for Danistay ---
"""
@app.tool(
    description="Search Danıştay decisions with keyword logic (AND/OR/NOT operators)",
    annotations={
        "readOnlyHint": True,
        "openWorldHint": True,
        "idempotentHint": True
    }
)
async def search_danistay_by_keyword(
    andKelimeler: List[str] = Field(default_factory=list, description="Keywords for AND logic, e.g., ['word1', 'word2']"),
    orKelimeler: List[str] = Field(default_factory=list, description="Keywords for OR logic."),
    notAndKelimeler: List[str] = Field(default_factory=list, description="Keywords for NOT AND logic."),
    notOrKelimeler: List[str] = Field(default_factory=list, description="Keywords for NOT OR logic."),
    pageNumber: int = Field(1, ge=1, description="Page number."),
    # pageSize: int = Field(10, ge=1, le=10, description="Results per page.")
) -> CompactDanistaySearchResult:
    # Search Danıştay decisions with keyword logic.
    
    pageSize = 10  # Default value
    
    search_query = DanistayKeywordSearchRequest(
        andKelimeler=andKelimeler,
        orKelimeler=orKelimeler,
        notAndKelimeler=notAndKelimeler,
        notOrKelimeler=notOrKelimeler,
        pageNumber=pageNumber,
        pageSize=pageSize
    )
    
    logger.info(f"Tool 'search_danistay_by_keyword' called.")
    try:
        api_response = await danistay_client_instance.search_keyword_decisions(search_query)
        if api_response.data:
            return CompactDanistaySearchResult(
                decisions=api_response.data.data,
                total_records=api_response.data.recordsTotal,
                requested_page=search_query.pageNumber,
                page_size=search_query.pageSize)
        logger.warning("API response for Danistay keyword search did not contain expected data structure.")
        return CompactDanistaySearchResult(decisions=[], total_records=0, requested_page=search_query.pageNumber, page_size=search_query.pageSize)
    except Exception as e:
        logger.exception(f"Error in tool 'search_danistay_by_keyword'.")
        raise

@app.tool(
    description="Search Danıştay decisions with detailed criteria (chamber selection, case numbers)",
    annotations={
        "readOnlyHint": True,
        "openWorldHint": True,
        "idempotentHint": True
    }
)
async def search_danistay_detailed(
    daire: str = Field("", description="Chamber/Department name (e.g., '1. Daire')."),
    esasYil: str = Field("", description="Case year for 'Esas No'."),
    esasIlkSiraNo: str = Field("", description="Starting sequence for 'Esas No'."),
    esasSonSiraNo: str = Field("", description="Ending sequence for 'Esas No'."),
    kararYil: str = Field("", description="Decision year for 'Karar No'."),
    kararIlkSiraNo: str = Field("", description="Starting sequence for 'Karar No'."),
    kararSonSiraNo: str = Field("", description="Ending sequence for 'Karar No'."),
    baslangicTarihi: str = Field("", description="Start date for decision (DD.MM.YYYY)."),
    bitisTarihi: str = Field("", description="End date for decision (DD.MM.YYYY)."),
    mevzuatNumarasi: str = Field("", description="Legislation number."),
    mevzuatAdi: str = Field("", description="Legislation name."),
    madde: str = Field("", description="Article number."),
    pageNumber: int = Field(1, ge=1, description="Page number."),
    # pageSize: int = Field(10, ge=1, le=10, description="Results per page.")
) -> CompactDanistaySearchResult:
    # Search Danıştay decisions with detailed filtering.
    
    pageSize = 10  # Default value
    
    search_query = DanistayDetailedSearchRequest(
        daire=daire,
        esasYil=esasYil,
        esasIlkSiraNo=esasIlkSiraNo,
        esasSonSiraNo=esasSonSiraNo,
        kararYil=kararYil,
        kararIlkSiraNo=kararIlkSiraNo,
        kararSonSiraNo=kararSonSiraNo,
        baslangicTarihi=baslangicTarihi,
        bitisTarihi=bitisTarihi,
        mevzuatNumarasi=mevzuatNumarasi,
        mevzuatAdi=mevzuatAdi,
        madde=madde,
        siralama="3",
        siralamaDirection="desc",
        pageNumber=pageNumber,
        pageSize=pageSize
    )
    
    logger.info(f"Tool 'search_danistay_detailed' called.")
    try:
        api_response = await danistay_client_instance.search_detailed_decisions(search_query)
        if api_response.data:
            return CompactDanistaySearchResult(
                decisions=api_response.data.data,
                total_records=api_response.data.recordsTotal,
                requested_page=search_query.pageNumber,
                page_size=search_query.pageSize)
        logger.warning("API response for Danistay detailed search did not contain expected data structure.")
        return CompactDanistaySearchResult(decisions=[], total_records=0, requested_page=search_query.pageNumber, page_size=search_query.pageSize)
    except Exception as e:
        logger.exception(f"Error in tool 'search_danistay_detailed'.")
        raise

@app.tool(
    description="Get Danıştay decision text in Markdown format",
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True
    }
)
async def get_danistay_document_markdown(id: str) -> DanistayDocumentMarkdown:
    # Get Danıştay decision text as Markdown. Use ID from search results.
    logger.info(f"Tool 'get_danistay_document_markdown' called for ID: {id}")
    if not id or not id.strip(): raise ValueError("Document ID must be a non-empty string for Danıştay.")
    try:
        return await danistay_client_instance.get_decision_document_as_markdown(id)
    except Exception as e:
        logger.exception(f"Error in tool 'get_danistay_document_markdown'.")
        raise
"""

# --- MCP Tools for Emsal ---
@app.tool(
    description="Search Emsal precedent decisions with detailed criteria",
    annotations={
        "readOnlyHint": True,
        "openWorldHint": True,
        "idempotentHint": True
    }
)
async def search_emsal_detailed_decisions(
    keyword: str = Field("", description="Keyword to search."),
    selected_bam_civil_court: str = Field("", description="Selected BAM Civil Court."),
    selected_civil_court: str = Field("", description="Selected Civil Court."),
    selected_regional_civil_chambers: List[str] = Field(default_factory=list, description="Selected Regional Civil Chambers."),
    case_year_esas: str = Field("", description="Case year for 'Esas No'."),
    case_start_seq_esas: str = Field("", description="Starting sequence for 'Esas No'."),
    case_end_seq_esas: str = Field("", description="Ending sequence for 'Esas No'."),
    decision_year_karar: str = Field("", description="Decision year for 'Karar No'."),
    decision_start_seq_karar: str = Field("", description="Starting sequence for 'Karar No'."),
    decision_end_seq_karar: str = Field("", description="Ending sequence for 'Karar No'."),
    start_date: str = Field("", description="Start date for decision (DD.MM.YYYY)."),
    end_date: str = Field("", description="End date for decision (DD.MM.YYYY)."),
    sort_criteria: str = Field("1", description="Sorting criteria (e.g., 1: Esas No)."),
    sort_direction: str = Field("desc", description="Sorting direction ('asc' or 'desc')."),
    page_number: int = Field(1, ge=1, description="Page number (accepts int)."),
    # page_size: int = Field(10, ge=1, le=10, description="Results per page.")
) -> CompactEmsalSearchResult:
    """Search Emsal precedent decisions with detailed criteria."""
    
    page_size = 10  # Default value
    
    search_query = EmsalSearchRequest(
        keyword=keyword,
        selected_bam_civil_court=selected_bam_civil_court,
        selected_civil_court=selected_civil_court,
        selected_regional_civil_chambers=selected_regional_civil_chambers,
        case_year_esas=case_year_esas,
        case_start_seq_esas=case_start_seq_esas,
        case_end_seq_esas=case_end_seq_esas,
        decision_year_karar=decision_year_karar,
        decision_start_seq_karar=decision_start_seq_karar,
        decision_end_seq_karar=decision_end_seq_karar,
        start_date=start_date,
        end_date=end_date,
        sort_criteria=sort_criteria,
        sort_direction=sort_direction,
        page_number=page_number,
        page_size=page_size
    )
    
    logger.info(f"Tool 'search_emsal_detailed_decisions' called.")
    try:
        api_response = await emsal_client_instance.search_detailed_decisions(search_query)
        if api_response.data:
            return CompactEmsalSearchResult(
                decisions=api_response.data.data,
                total_records=api_response.data.recordsTotal if api_response.data.recordsTotal is not None else 0,
                requested_page=search_query.page_number,
                page_size=search_query.page_size
            )
        logger.warning("API response for Emsal search did not contain expected data structure.")
        return CompactEmsalSearchResult(decisions=[], total_records=0, requested_page=search_query.page_number, page_size=search_query.page_size)
    except Exception as e:
        logger.exception(f"Error in tool 'search_emsal_detailed_decisions'.")
        raise

@app.tool(
    description="Get Emsal precedent decision text in Markdown format",
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True
    }
)
async def get_emsal_document_markdown(id: str) -> EmsalDocumentMarkdown:
    """Get document as Markdown."""
    logger.info(f"Tool 'get_emsal_document_markdown' called for ID: {id}")
    if not id or not id.strip(): raise ValueError("Document ID required for Emsal.")
    try:
        return await emsal_client_instance.get_decision_document_as_markdown(id)
    except Exception as e:
        logger.exception(f"Error in tool 'get_emsal_document_markdown'.")
        raise

# --- MCP Tools for Uyusmazlik ---
@app.tool(
    description="Search Uyuşmazlık Mahkemesi decisions for jurisdictional disputes",
    annotations={
        "readOnlyHint": True,
        "openWorldHint": True,
        "idempotentHint": True
    }
)
async def search_uyusmazlik_decisions(
    icerik: str = Field("", description="Keyword or content for main text search."),
    bolum: Literal["ALL", "Ceza Bölümü", "Genel Kurul Kararları", "Hukuk Bölümü"] = Field("ALL", description="Select the department (Bölüm). Use 'ALL' for all departments."),
    uyusmazlik_turu: Literal["ALL", "Görev Uyuşmazlığı", "Hüküm Uyuşmazlığı"] = Field("ALL", description="Select the type of dispute. Use 'ALL' for all types."),
    karar_sonuclari: List[Literal["Hüküm Uyuşmazlığı Olmadığına Dair", "Hüküm Uyuşmazlığı Olduğuna Dair"]] = Field(default_factory=list, description="List of desired 'Karar Sonucu' types."),
    esas_yil: str = Field("", description="Case year ('Esas Yılı')."),
    esas_sayisi: str = Field("", description="Case number ('Esas Sayısı')."),
    karar_yil: str = Field("", description="Decision year ('Karar Yılı')."),
    karar_sayisi: str = Field("", description="Decision number ('Karar Sayısı')."),
    kanun_no: str = Field("", description="Relevant Law Number."),
    karar_date_begin: str = Field("", description="Decision start date (DD.MM.YYYY)."),
    karar_date_end: str = Field("", description="Decision end date (DD.MM.YYYY)."),
    resmi_gazete_sayi: str = Field("", description="Official Gazette number."),
    resmi_gazete_date: str = Field("", description="Official Gazette date (DD.MM.YYYY)."),
    tumce: str = Field("", description="Exact phrase search."),
    wild_card: str = Field("", description="Search for phrase and its inflections."),
    hepsi: str = Field("", description="Search for texts containing all specified words."),
    herhangi_birisi: str = Field("", description="Search for texts containing any of the specified words."),
    not_hepsi: str = Field("", description="Exclude texts containing these specified words.")
) -> UyusmazlikSearchResponse:
    """Search Court of Jurisdictional Disputes decisions."""
    
    # Convert string literals to enums
    # Map "ALL" to TUMU for backward compatibility
    if bolum == "ALL":
        bolum_enum = UyusmazlikBolumEnum.TUMU
    else:
        bolum_enum = UyusmazlikBolumEnum(bolum) if bolum else UyusmazlikBolumEnum.TUMU
    
    if uyusmazlik_turu == "ALL":
        uyusmazlik_turu_enum = UyusmazlikTuruEnum.TUMU
    else:
        uyusmazlik_turu_enum = UyusmazlikTuruEnum(uyusmazlik_turu) if uyusmazlik_turu else UyusmazlikTuruEnum.TUMU
    karar_sonuclari_enums = [UyusmazlikKararSonucuEnum(ks) for ks in karar_sonuclari]
    
    search_params = UyusmazlikSearchRequest(
        icerik=icerik,
        bolum=bolum_enum,
        uyusmazlik_turu=uyusmazlik_turu_enum,
        karar_sonuclari=karar_sonuclari_enums,
        esas_yil=esas_yil,
        esas_sayisi=esas_sayisi,
        karar_yil=karar_yil,
        karar_sayisi=karar_sayisi,
        kanun_no=kanun_no,
        karar_date_begin=karar_date_begin,
        karar_date_end=karar_date_end,
        resmi_gazete_sayi=resmi_gazete_sayi,
        resmi_gazete_date=resmi_gazete_date,
        tumce=tumce,
        wild_card=wild_card,
        hepsi=hepsi,
        herhangi_birisi=herhangi_birisi,
        not_hepsi=not_hepsi
    )
    
    logger.info(f"Tool 'search_uyusmazlik_decisions' called.")
    try:
        return await uyusmazlik_client_instance.search_decisions(search_params)
    except Exception as e:
        logger.exception(f"Error in tool 'search_uyusmazlik_decisions'.")
        raise

@app.tool(
    description="Get Uyuşmazlık Mahkemesi decision text from URL in Markdown format",
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True
    }
)
async def get_uyusmazlik_document_markdown_from_url(
    document_url: str = Field(..., description="Full URL to the Uyuşmazlık Mahkemesi decision document from search results")
) -> UyusmazlikDocumentMarkdown:
    """Get Uyuşmazlık Mahkemesi decision as Markdown."""
    logger.info(f"Tool 'get_uyusmazlik_document_markdown_from_url' called for URL: {str(document_url)}")
    if not document_url:
        raise ValueError("Document URL (document_url) is required for Uyuşmazlık document retrieval.")
    try:
        return await uyusmazlik_client_instance.get_decision_document_as_markdown(str(document_url))
    except Exception as e:
        logger.exception(f"Error in tool 'get_uyusmazlik_document_markdown_from_url'.")
        raise

# --- DEACTIVATED: MCP Tools for Anayasa Mahkemesi (Individual Tools) ---
# Use search_anayasa_unified and get_anayasa_document_unified instead

"""
@app.tool(
    description="Search Constitutional Court norm control decisions with comprehensive filtering",
    annotations={
        "readOnlyHint": True,
        "openWorldHint": True,
        "idempotentHint": True
    }
)
# DEACTIVATED TOOL - Use search_anayasa_unified instead
# @app.tool(
#     description="DEACTIVATED - Use search_anayasa_unified instead",
#     annotations={"readOnlyHint": True, "openWorldHint": False, "idempotentHint": True}
# )
# async def search_anayasa_norm_denetimi_decisions(...) -> AnayasaSearchResult:
#     raise ValueError("This tool is deactivated. Use search_anayasa_unified instead.")

# DEACTIVATED TOOL - Use get_anayasa_document_unified instead
# @app.tool(...)
# async def get_anayasa_norm_denetimi_document_markdown(...) -> AnayasaDocumentMarkdown:
#     raise ValueError("This tool is deactivated. Use get_anayasa_document_unified instead.")

# DEACTIVATED TOOL - Use search_anayasa_unified instead
# @app.tool(...)
# async def search_anayasa_bireysel_basvuru_report(...) -> AnayasaBireyselReportSearchResult:
#     raise ValueError("This tool is deactivated. Use search_anayasa_unified instead.")

# DEACTIVATED TOOL - Use get_anayasa_document_unified instead
# @app.tool(...)
# async def get_anayasa_bireysel_basvuru_document_markdown(...) -> AnayasaBireyselBasvuruDocumentMarkdown:
#     raise ValueError("This tool is deactivated. Use get_anayasa_document_unified instead.")
"""

# --- Unified MCP Tools for Anayasa Mahkemesi ---
@app.tool(
    description="Unified search for Constitutional Court decisions: both norm control (normkararlarbilgibankasi) and individual applications (kararlarbilgibankasi) in one tool",
    annotations={
        "readOnlyHint": True,
        "openWorldHint": True,
        "idempotentHint": True
    }
)
async def search_anayasa_unified(
    decision_type: Literal["norm_denetimi", "bireysel_basvuru"] = Field(..., description="Decision type: norm_denetimi (norm control) or bireysel_basvuru (individual applications)"),
    keywords: List[str] = Field(default_factory=list, description="Keywords to search for (common parameter)"),
    page_to_fetch: int = Field(1, ge=1, le=100, description="Page number to fetch (1-100)"),
    # results_per_page: int = Field(10, ge=1, le=100, description="Results per page (1-100)"),
    
    # Norm Denetimi specific parameters (ignored for bireysel_basvuru)
    keywords_all: List[str] = Field(default_factory=list, description="All keywords must be present (norm_denetimi only)"),
    keywords_any: List[str] = Field(default_factory=list, description="Any of these keywords (norm_denetimi only)"),
    decision_type_norm: Literal["ALL", "1", "2", "3"] = Field("ALL", description="Decision type for norm denetimi"),
    application_date_start: str = Field("", description="Application start date (norm_denetimi only)"),
    application_date_end: str = Field("", description="Application end date (norm_denetimi only)"),
    
    # Bireysel Başvuru specific parameters (ignored for norm_denetimi)
    decision_start_date: str = Field("", description="Decision start date (bireysel_basvuru only)"),
    decision_end_date: str = Field("", description="Decision end date (bireysel_basvuru only)"),
    norm_type: Literal["ALL", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "0"] = Field("ALL", description="Norm type (bireysel_basvuru only)"),
    subject_category: str = Field("", description="Subject category (bireysel_basvuru only)")
) -> str:
    logger.info(f"Tool 'search_anayasa_unified' called for decision_type: {decision_type}")
    
    results_per_page = 10  # Default value
    
    try:
        request = AnayasaUnifiedSearchRequest(
            decision_type=decision_type,
            keywords=keywords,
            page_to_fetch=page_to_fetch,
            results_per_page=results_per_page,
            keywords_all=keywords_all,
            keywords_any=keywords_any,
            decision_type_norm=decision_type_norm,
            application_date_start=application_date_start,
            application_date_end=application_date_end,
            decision_start_date=decision_start_date,
            decision_end_date=decision_end_date,
            norm_type=norm_type,
            subject_category=subject_category
        )
        
        result = await anayasa_unified_client_instance.search_unified(request)
        return json.dumps(result.model_dump(), ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.exception(f"Error in tool 'search_anayasa_unified'.")
        raise

@app.tool(
    description="Unified document retrieval for Constitutional Court decisions: auto-detects norm control vs individual applications based on URL",
    annotations={
        "readOnlyHint": True,
        "openWorldHint": False,
        "idempotentHint": True
    }
)
async def get_anayasa_document_unified(
    document_url: str = Field(..., description="Document URL from search results"),
    page_number: int = Field(1, ge=1, description="Page number for paginated content (1-indexed)")
) -> str:
    logger.info(f"Tool 'get_anayasa_document_unified' called for URL: {document_url}, Page: {page_number}")
    
    try:
        result = await anayasa_unified_client_instance.get_document_unified(document_url, page_number)
        return json.dumps(result.model_dump(mode='json'), ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.exception(f"Error in tool 'get_anayasa_document_unified'.")
        raise

# --- MCP Tools for KIK (Kamu İhale Kurulu) ---
@app.tool(
    description="Search Public Procurement Authority (KİK) decisions for procurement law disputes",
    annotations={
        "readOnlyHint": True,
        "openWorldHint": True,
        "idempotentHint": True
    }
)
async def search_kik_decisions(
    karar_tipi: Literal["rbUyusmazlik", "rbDuzenleyici", "rbMahkeme"] = Field("rbUyusmazlik", description="Type of KIK Decision."),
    karar_no: str = Field("", description="Decision Number (e.g., '2024/UH.II-1766')."),
    karar_tarihi_baslangic: str = Field("", description="Decision Date Start (DD.MM.YYYY)."),
    karar_tarihi_bitis: str = Field("", description="Decision Date End (DD.MM.YYYY)."),
    basvuru_sahibi: str = Field("", description="Applicant."),
    ihaleyi_yapan_idare: str = Field("", description="Procuring Entity."),
    basvuru_konusu_ihale: str = Field("", description="Tender subject of the application."),
    karar_metni: str = Field("", description="Decision text search. Supports: +word, -word, \"exact phrase\", OR/AND"),
    yil: str = Field("", description="Year of the decision."),
    resmi_gazete_tarihi: str = Field("", description="Official Gazette Date (DD.MM.YYYY)."),
    resmi_gazete_sayisi: str = Field("", description="Official Gazette Number."),
    page: int = Field(1, ge=1, description="Results page number.")
) -> KikSearchResult:
    """Search Public Procurement Authority (KIK) decisions."""
    
    # Convert string literal to enum
    karar_tipi_enum = KikKararTipi(karar_tipi)
    
    search_query = KikSearchRequest(
        karar_tipi=karar_tipi_enum,
        karar_no=karar_no,
        karar_tarihi_baslangic=karar_tarihi_baslangic,
        karar_tarihi_bitis=karar_tarihi_bitis,
        basvuru_sahibi=basvuru_sahibi,
        ihaleyi_yapan_idare=ihaleyi_yapan_idare,
        basvuru_konusu_ihale=basvuru_konusu_ihale,
        karar_metni=karar_metni,
        yil=yil,
        resmi_gazete_tarihi=resmi_gazete_tarihi,
        resmi_gazete_sayisi=resmi_gazete_sayisi,
        page=page
    )
    
    logger.info(f"Tool 'search_kik_decisions' called.")
    try:
        api_response = await kik_client_instance.search_decisions(search_query)
        page_param_for_log = search_query.page if hasattr(search_query, 'page') else 1
        if not api_response.decisions and api_response.total_records == 0 and page_param_for_log == 1:
             logger.warning(f"KIK search returned no decisions for query.")
        return api_response
    except Exception as e:
        logger.exception(f"Error in KIK search tool 'search_kik_decisions'.")
        current_page_val = search_query.page if hasattr(search_query, 'page') else 1
        return KikSearchResult(decisions=[], total_records=0, current_page=current_page_val)

@app.tool(
    description="Get Public Procurement Authority (KİK) decision text in paginated Markdown format",
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True
    }
)
async def get_kik_document_markdown(
    karar_id: str = Field(..., description="The Base64 encoded KIK decision identifier."),
    page_number: int = Field(1, ge=1, description="Page number for paginated Markdown content (1-indexed). Default is 1.")
) -> KikDocumentMarkdown:
    """Get KIK decision as paginated Markdown."""
    logger.info(f"Tool 'get_kik_document_markdown' called for KIK karar_id: {karar_id}, Markdown Page: {page_number}")
    
    if not karar_id or not karar_id.strip():
        logger.error("KIK Document retrieval: karar_id cannot be empty.")
        return KikDocumentMarkdown( 
            retrieved_with_karar_id=karar_id,
            error_message="karar_id is required and must be a non-empty string.",
            current_page=page_number or 1,
            total_pages=1,
            is_paginated=False
            )

    current_page_to_fetch = page_number if page_number is not None and page_number >= 1 else 1

    try:
        return await kik_client_instance.get_decision_document_as_markdown(
            karar_id_b64=karar_id, 
            page_number=current_page_to_fetch
        )
    except Exception as e:
        logger.exception(f"Error in KIK document retrieval tool 'get_kik_document_markdown' for karar_id: {karar_id}")
        return KikDocumentMarkdown(
            retrieved_with_karar_id=karar_id,
            error_message=f"Tool-level error during KIK document retrieval: {str(e)}",
            current_page=current_page_to_fetch, 
            total_pages=1, 
            is_paginated=False
        )
@app.tool(
    description="Search Competition Authority (Rekabet Kurumu) decisions for competition law and antitrust",
    annotations={
        "readOnlyHint": True,
        "openWorldHint": True,
        "idempotentHint": True
    }
)
async def search_rekabet_kurumu_decisions(
    sayfaAdi: str = Field("", description="Search in decision title (Başlık)."),
    YayinlanmaTarihi: str = Field("", description="Publication date (Yayım Tarihi), e.g., DD.MM.YYYY."),
    PdfText: str = Field(
        "",
        description='Search in decision text. Use "\\"kesin cümle\\"" for precise matching.'
    ),
    KararTuru: Literal[ 
        "ALL", 
        "Birleşme ve Devralma",
        "Diğer",
        "Menfi Tespit ve Muafiyet",
        "Özelleştirme",
        "Rekabet İhlali"
    ] = Field("ALL", description="Parameter description"),
    KararSayisi: str = Field("", description="Decision number (Karar Sayısı)."),
    KararTarihi: str = Field("", description="Decision date (Karar Tarihi), e.g., DD.MM.YYYY."),
    page: int = Field(1, ge=1, description="Page number to fetch for the results list.")
) -> RekabetSearchResult:
    """Search Competition Authority decisions."""
    
    karar_turu_guid_enum = KARAR_TURU_ADI_TO_GUID_ENUM_MAP.get(KararTuru)

    try:
        if karar_turu_guid_enum is None: 
            logger.warning(f"Invalid user-provided KararTuru: '{KararTuru}'. Defaulting to TUMU (all).")
            karar_turu_guid_enum = RekabetKararTuruGuidEnum.TUMU
    except Exception as e_map: 
        logger.error(f"Error mapping KararTuru '{KararTuru}': {e_map}. Defaulting to TUMU.")
        karar_turu_guid_enum = RekabetKararTuruGuidEnum.TUMU

    search_query = RekabetKurumuSearchRequest(
        sayfaAdi=sayfaAdi,
        YayinlanmaTarihi=YayinlanmaTarihi,
        PdfText=PdfText,
        KararTuruID=karar_turu_guid_enum, 
        KararSayisi=KararSayisi,
        KararTarihi=KararTarihi,
        page=page
    )
    logger.info(f"Tool 'search_rekabet_kurumu_decisions' called. Query: {search_query.model_dump_json(exclude_none=True, indent=2)}")
    try:
       
        return await rekabet_client_instance.search_decisions(search_query)
    except Exception as e:
        logger.exception("Error in tool 'search_rekabet_kurumu_decisions'.")
        return RekabetSearchResult(decisions=[], retrieved_page_number=page, total_records_found=0, total_pages=0)

@app.tool(
    description="Get Competition Authority decision text in paginated Markdown format",
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True
    }
)
async def get_rekabet_kurumu_document(
    karar_id: str = Field(..., description="GUID (kararId) of the Rekabet Kurumu decision. This ID is obtained from search results."),
    page_number: int = Field(1, ge=1, description="Requested page number for the Markdown content converted from PDF (1-indexed, accepts int). Default is 1.")
) -> RekabetDocument:
    """Get Competition Authority decision as paginated Markdown."""
    logger.info(f"Tool 'get_rekabet_kurumu_document' called. Karar ID: {karar_id}, Markdown Page: {page_number}")
    
    current_page_to_fetch = page_number if page_number >= 1 else 1
    
    try:
      
        return await rekabet_client_instance.get_decision_document(karar_id, page_number=current_page_to_fetch)
    except Exception as e:
        logger.exception(f"Error in tool 'get_rekabet_kurumu_document'. Karar ID: {karar_id}")
        raise 

# --- MCP Tools for Bedesten (Unified Search Across All Courts) ---
@app.tool(
    description="Search multiple Turkish courts (Yargıtay, Danıştay, Local Courts, Appeals Courts, KYB)",
    annotations={
        "readOnlyHint": True,
        "openWorldHint": True,
        "idempotentHint": True
    }
)
async def search_bedesten_unified(
    ctx: Context,
    phrase: str = Field(..., description="""Search query in Turkish. SUPPORTED OPERATORS:
• Simple: "mülkiyet hakkı" (finds both words)
• Exact phrase: "\"mülkiyet hakkı\"" (finds exact phrase)  
• Required term: "+mülkiyet hakkı" (must contain mülkiyet)
• Exclude term: "mülkiyet -kira" (contains mülkiyet but not kira)
• Boolean AND: "mülkiyet AND hak" (both terms required)
• Boolean OR: "mülkiyet OR tapu" (either term acceptable)
• Boolean NOT: "mülkiyet NOT satış" (contains mülkiyet but not satış)
NOTE: Wildcards (*,?), regex patterns (/regex/), fuzzy search (~), and proximity search are NOT supported.
For best results, use exact phrases with quotes for legal terms."""),
    court_types: List[BedestenCourtTypeEnum] = Field(
        default=["YARGITAYKARARI", "DANISTAYKARAR"], 
        description="Court types: YARGITAYKARARI, DANISTAYKARAR, YERELHUKUK, ISTINAFHUKUK, KYB"
    ),
    # pageSize: int = Field(10, ge=1, le=10, description="Results per page (1-10)"),
    pageNumber: int = Field(1, ge=1, description="Page number"),
    birimAdi: BirimAdiEnum = Field("ALL", description="""
        Chamber filter (optional). Abbreviated values with Turkish names:
        • Yargıtay: H1-H23 (1-23. Hukuk Dairesi), C1-C23 (1-23. Ceza Dairesi), HGK (Hukuk Genel Kurulu), CGK (Ceza Genel Kurulu), BGK (Büyük Genel Kurulu), HBK (Hukuk Daireleri Başkanlar Kurulu), CBK (Ceza Daireleri Başkanlar Kurulu)
        • Danıştay: D1-D17 (1-17. Daire), DBGK (Büyük Gen.Kur.), IDDK (İdare Dava Daireleri Kurulu), VDDK (Vergi Dava Daireleri Kurulu), IBK (İçtihatları Birleştirme Kurulu), IIK (İdari İşler Kurulu), DBK (Başkanlar Kurulu), AYIM (Askeri Yüksek İdare Mahkemesi), AYIM1-3 (Askeri Yüksek İdare Mahkemesi 1-3. Daire)
        """),
    kararTarihiStart: str = Field("", description="Start date (ISO 8601 format)"),
    kararTarihiEnd: str = Field("", description="End date (ISO 8601 format)")
) -> dict:
    """Search Turkish legal databases via unified Bedesten API."""
    
    # Get Bearer token information for access control and logging
    try:
        access_token: AccessToken = get_access_token()
        user_id = access_token.client_id
        user_scopes = access_token.scopes
        
        # Check for required scopes
        if "yargi.read" not in user_scopes and "yargi.search" not in user_scopes:
            raise ToolError(f"Insufficient permissions: 'yargi.read' or 'yargi.search' scope required. Current scopes: {user_scopes}")
        
        logger.info(f"Tool 'search_bedesten_unified' called by user '{user_id}' with scopes {user_scopes}")
        
    except Exception as e:
        # Development mode fallback - allow access without strict token validation
        logger.warning(f"Bearer token validation failed, using development mode: {str(e)}")
        user_id = "dev-user"
        user_scopes = ["yargi.read", "yargi.search"]
    
    pageSize = 10  # Default value
    
    search_data = BedestenSearchData(
        pageSize=pageSize,
        pageNumber=pageNumber,
        itemTypeList=court_types,
        phrase=phrase,
        birimAdi=birimAdi,
        kararTarihiStart=kararTarihiStart,
        kararTarihiEnd=kararTarihiEnd
    )
    
    search_request = BedestenSearchRequest(data=search_data)
    
    logger.info(f"User '{user_id}' searching bedesten: phrase='{phrase}', court_types={court_types}, birimAdi='{birimAdi}', page={pageNumber}")
    
    try:
        response = await bedesten_client_instance.search_documents(search_request)
        
        if response.data is None:
            return {
                "decisions": [],
                "total_records": 0,
                "requested_page": pageNumber,
                "page_size": pageSize,
                "searched_courts": court_types,
                "error": "No data returned from Bedesten API"
            }
        
        return {
            "decisions": [d.model_dump() for d in response.data.emsalKararList],
            "total_records": response.data.total,
            "requested_page": pageNumber,
            "page_size": pageSize,
            "searched_courts": court_types
        }
    except Exception as e:
        logger.exception("Error in tool 'search_bedesten_unified'")
        raise

@app.tool(
    description="Get legal decision document from Bedesten API in Markdown format",
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True
    }
)
async def get_bedesten_document_markdown(
    documentId: str = Field(..., description="Document ID from Bedesten search results")
) -> BedestenDocumentMarkdown:
    """Get legal decision document as Markdown from Bedesten API."""
    logger.info(f"Tool 'get_bedesten_document_markdown' called for ID: {documentId}")
    
    if not documentId or not documentId.strip():
        raise ValueError("Document ID must be a non-empty string.")
    
    try:
        return await bedesten_client_instance.get_document_as_markdown(documentId)
    except Exception as e:
        logger.exception("Error in tool 'get_kyb_bedesten_document_markdown'")
        raise

# --- MCP Tools for Sayıştay (Turkish Court of Accounts) ---

# DEACTIVATED TOOL - Use search_sayistay_unified instead
# @app.tool(
#     description="Search Sayıştay Genel Kurul decisions for audit and accountability regulations",
#     annotations={
#         "readOnlyHint": True,
#         "openWorldHint": True,
#         "idempotentHint": True
#     }
# )
# async def search_sayistay_genel_kurul(
#     karar_no: str = Field("", description="Decision number to search for (e.g., '5415')"),
#     karar_ek: str = Field("", description="Decision appendix number (max 99, e.g., '1')"),
#     karar_tarih_baslangic: str = Field("", description="Start date (DD.MM.YYYY)"),
#     karar_tarih_bitis: str = Field("", description="End date (DD.MM.YYYY)"),
#     karar_tamami: str = Field("", description="Full text search"),
#     start: int = Field(0, description="Starting record for pagination (0-based)"),
#     length: int = Field(10, description="Number of records per page (1-100)")
# ) -> GenelKurulSearchResponse:
#     """Search Sayıştay General Assembly decisions."""
#     raise ValueError("This tool is deactivated. Use search_sayistay_unified instead.")

# DEACTIVATED TOOL - Use search_sayistay_unified instead
# @app.tool(
#     description="Search Sayıştay Temyiz Kurulu decisions with chamber filtering and comprehensive criteria",
#     annotations={
#         "readOnlyHint": True,
#         "openWorldHint": True,
#         "idempotentHint": True
#     }
# )
# async def search_sayistay_temyiz_kurulu(
#     ilam_dairesi: DaireEnum = Field("ALL", description="Audit chamber selection"),
#     yili: str = Field("", description="Year (YYYY)"),
#     karar_tarih_baslangic: str = Field("", description="Start date (DD.MM.YYYY)"),
#     karar_tarih_bitis: str = Field("", description="End date (DD.MM.YYYY)"),
#     kamu_idaresi_turu: KamuIdaresiTuruEnum = Field("ALL", description="Public admin type"),
#     ilam_no: str = Field("", description="Audit report number (İlam No, max 50 chars)"),
#     dosya_no: str = Field("", description="File number for the case"),
#     temyiz_tutanak_no: str = Field("", description="Appeals board meeting minutes number"),
#     temyiz_karar: str = Field("", description="Appeals decision text"),
#     web_karar_konusu: WebKararKonusuEnum = Field("ALL", description="Decision subject"),
#     start: int = Field(0, description="Starting record for pagination (0-based)"),
#     length: int = Field(10, description="Number of records per page (1-100)")
# ) -> TemyizKuruluSearchResponse:
#     """Search Sayıştay Appeals Board decisions."""
#     raise ValueError("This tool is deactivated. Use search_sayistay_unified instead.")

# DEACTIVATED TOOL - Use search_sayistay_unified instead
# @app.tool(
#     description="Search Sayıştay Daire decisions with chamber filtering and subject categorization",
#     annotations={
#         "readOnlyHint": True,
#         "openWorldHint": True,
#         "idempotentHint": True
#     }
# )
# async def search_sayistay_daire(
#     yargilama_dairesi: DaireEnum = Field("ALL", description="Chamber selection"),
#     karar_tarih_baslangic: str = Field("", description="Start date (DD.MM.YYYY)"),
#     karar_tarih_bitis: str = Field("", description="End date (DD.MM.YYYY)"),
#     ilam_no: str = Field("", description="Audit report number (İlam No, max 50 chars)"),
#     kamu_idaresi_turu: KamuIdaresiTuruEnum = Field("ALL", description="Public admin type"),
#     hesap_yili: str = Field("", description="Fiscal year"),
#     web_karar_konusu: WebKararKonusuEnum = Field("ALL", description="Decision subject"),
#     web_karar_metni: str = Field("", description="Decision text search"),
#     start: int = Field(0, description="Starting record for pagination (0-based)"),
#     length: int = Field(10, description="Number of records per page (1-100)")
# ) -> DaireSearchResponse:
#     """Search Sayıştay Chamber decisions."""
#     raise ValueError("This tool is deactivated. Use search_sayistay_unified instead.")

# DEACTIVATED TOOL - Use get_sayistay_document_unified instead
# @app.tool(
#     description="Get Sayıştay Genel Kurul decision document in Markdown format",
#     annotations={
#         "readOnlyHint": True,
#         "openWorldHint": False,
#         "idempotentHint": True
#     }
# )
# async def get_sayistay_genel_kurul_document_markdown(
#     decision_id: str = Field(..., description="Decision ID from search_sayistay_genel_kurul results")
# ) -> SayistayDocumentMarkdown:
#     """Get Sayıştay General Assembly decision as Markdown."""
#     raise ValueError("This tool is deactivated. Use get_sayistay_document_unified instead.")

# DEACTIVATED TOOL - Use get_sayistay_document_unified instead
# @app.tool(
#     description="Get Sayıştay Temyiz Kurulu decision document in Markdown format",
#     annotations={
#         "readOnlyHint": True,
#         "openWorldHint": False,
#         "idempotentHint": True
#     }
# )
# async def get_sayistay_temyiz_kurulu_document_markdown(
#     decision_id: str = Field(..., description="Decision ID from search_sayistay_temyiz_kurulu results")
# ) -> SayistayDocumentMarkdown:
#     """Get Sayıştay Appeals Board decision as Markdown."""
#     raise ValueError("This tool is deactivated. Use get_sayistay_document_unified instead.")

# DEACTIVATED TOOL - Use get_sayistay_document_unified instead
# @app.tool(
#     description="Get Sayıştay Daire decision document in Markdown format",
#     annotations={
#         "readOnlyHint": True,
#         "openWorldHint": False,
#         "idempotentHint": True
#     }
# )
# async def get_sayistay_daire_document_markdown(
#     decision_id: str = Field(..., description="Decision ID from search_sayistay_daire results")
# ) -> SayistayDocumentMarkdown:
#     """Get Sayıştay Chamber decision as Markdown."""
#     raise ValueError("This tool is deactivated. Use get_sayistay_document_unified instead.")

# --- UNIFIED MCP Tools for Sayıştay (Turkish Court of Accounts) ---

@app.tool(
    description="Search Sayıştay decisions unified across all three decision types (Genel Kurul, Temyiz Kurulu, Daire) with comprehensive filtering",
    annotations={
        "readOnlyHint": True,
        "openWorldHint": True,
        "idempotentHint": True
    }
)
async def search_sayistay_unified(
    decision_type: Literal["genel_kurul", "temyiz_kurulu", "daire"] = Field(..., description="Decision type: genel_kurul, temyiz_kurulu, or daire"),
    
    # Common pagination parameters
    start: int = Field(0, ge=0, description="Starting record for pagination (0-based)"),
    length: int = Field(10, ge=1, le=100, description="Number of records per page (1-100)"),
    
    # Common search parameters
    karar_tarih_baslangic: str = Field("", description="Start date (DD.MM.YYYY format)"),
    karar_tarih_bitis: str = Field("", description="End date (DD.MM.YYYY format)"),
    kamu_idaresi_turu: Literal["ALL", "Genel Bütçe Kapsamındaki İdareler", "Yüksek Öğretim Kurumları", "Diğer Özel Bütçeli İdareler", "Düzenleyici ve Denetleyici Kurumlar", "Sosyal Güvenlik Kurumları", "Özel İdareler", "Belediyeler ve Bağlı İdareler", "Diğer"] = Field("ALL", description="Public administration type filter"),
    ilam_no: str = Field("", description="Audit report number (İlam No, max 50 chars)"),
    web_karar_konusu: Literal["ALL", "Harcırah Mevzuatı", "İhale Mevzuatı", "İş Mevzuatı", "Personel Mevzuatı", "Sorumluluk ve Yargılama Usulleri", "Vergi Resmi Harç ve Diğer Gelirler", "Çeşitli Konular"] = Field("ALL", description="Decision subject category filter"),
    
    # Genel Kurul specific parameters (ignored for other types)
    karar_no: str = Field("", description="Decision number (genel_kurul only)"),
    karar_ek: str = Field("", description="Decision appendix number (genel_kurul only)"),
    karar_tamami: str = Field("", description="Full text search (genel_kurul only)"),
    
    # Temyiz Kurulu specific parameters (ignored for other types)
    ilam_dairesi: Literal["ALL", "1", "2", "3", "4", "5", "6", "7", "8"] = Field("ALL", description="Audit chamber selection (temyiz_kurulu only)"),
    yili: str = Field("", description="Year (YYYY format, temyiz_kurulu only)"),
    dosya_no: str = Field("", description="File number (temyiz_kurulu only)"),
    temyiz_tutanak_no: str = Field("", description="Appeals board meeting minutes number (temyiz_kurulu only)"),
    temyiz_karar: str = Field("", description="Appeals decision text search (temyiz_kurulu only)"),
    
    # Daire specific parameters (ignored for other types)
    yargilama_dairesi: Literal["ALL", "1", "2", "3", "4", "5", "6", "7", "8"] = Field("ALL", description="Chamber selection (daire only)"),
    hesap_yili: str = Field("", description="Account year (daire only)"),
    web_karar_metni: str = Field("", description="Decision text search (daire only)")
) -> SayistayUnifiedSearchResult:
    """Search Sayıştay decisions across all three decision types with unified interface."""
    logger.info(f"Tool 'search_sayistay_unified' called with decision_type={decision_type}")
    
    try:
        search_request = SayistayUnifiedSearchRequest(
            decision_type=decision_type,
            start=start,
            length=length,
            karar_tarih_baslangic=karar_tarih_baslangic,
            karar_tarih_bitis=karar_tarih_bitis,
            kamu_idaresi_turu=kamu_idaresi_turu,
            ilam_no=ilam_no,
            web_karar_konusu=web_karar_konusu,
            karar_no=karar_no,
            karar_ek=karar_ek,
            karar_tamami=karar_tamami,
            ilam_dairesi=ilam_dairesi,
            yili=yili,
            dosya_no=dosya_no,
            temyiz_tutanak_no=temyiz_tutanak_no,
            temyiz_karar=temyiz_karar,
            yargilama_dairesi=yargilama_dairesi,
            hesap_yili=hesap_yili,
            web_karar_metni=web_karar_metni
        )
        return await sayistay_unified_client_instance.search_unified(search_request)
    except Exception as e:
        logger.exception("Error in tool 'search_sayistay_unified'")
        raise

@app.tool(
    description="Get Sayıştay decision document in Markdown format for any decision type",
    annotations={
        "readOnlyHint": True,
        "openWorldHint": False,
        "idempotentHint": True
    }
)
async def get_sayistay_document_unified(
    decision_id: str = Field(..., description="Decision ID from search_sayistay_unified results"),
    decision_type: Literal["genel_kurul", "temyiz_kurulu", "daire"] = Field(..., description="Decision type: genel_kurul, temyiz_kurulu, or daire")
) -> SayistayUnifiedDocumentMarkdown:
    """Get Sayıştay decision document as Markdown for any decision type."""
    logger.info(f"Tool 'get_sayistay_document_unified' called for ID: {decision_id}, type: {decision_type}")
    
    if not decision_id or not decision_id.strip():
        raise ValueError("Decision ID must be a non-empty string.")
    
    try:
        return await sayistay_unified_client_instance.get_document_unified(decision_id, decision_type)
    except Exception as e:
        logger.exception("Error in tool 'get_sayistay_document_unified'")
        raise

# --- Application Shutdown Handling ---
def perform_cleanup():
    logger.info("MCP Server performing cleanup...")
    try:
        loop = asyncio.get_event_loop_policy().get_event_loop()
        if loop.is_closed(): 
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError: 
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    clients_to_close = [
        globals().get('yargitay_client_instance'),
        globals().get('danistay_client_instance'),
        globals().get('emsal_client_instance'),
        globals().get('uyusmazlik_client_instance'),
        globals().get('anayasa_norm_client_instance'),
        globals().get('anayasa_bireysel_client_instance'),
        globals().get('anayasa_unified_client_instance'),
        globals().get('kik_client_instance'),
        globals().get('rekabet_client_instance'),
        globals().get('bedesten_client_instance'),
        globals().get('sayistay_client_instance'),
        globals().get('sayistay_unified_client_instance'),
        globals().get('kvkk_client_instance'),
        globals().get('bddk_client_instance')
    ]
    async def close_all_clients_async():
        tasks = []
        for client_instance in clients_to_close:
            if client_instance and hasattr(client_instance, 'close_client_session') and callable(client_instance.close_client_session):
                logger.info(f"Scheduling close for client session: {client_instance.__class__.__name__}")
                tasks.append(client_instance.close_client_session())
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    client_name = "Unknown Client"
                    if i < len(clients_to_close) and clients_to_close[i] is not None:
                        client_name = clients_to_close[i].__class__.__name__
                    logger.error(f"Error closing client {client_name}: {result}")
    try:
        if loop.is_running(): 
            asyncio.ensure_future(close_all_clients_async(), loop=loop)
            logger.info("Client cleanup tasks scheduled on running event loop.")
        else:
            loop.run_until_complete(close_all_clients_async())
            logger.info("Client cleanup tasks completed via run_until_complete.")
    except Exception as e: 
        logger.error(f"Error during atexit cleanup execution: {e}", exc_info=True)
    logger.info("MCP Server atexit cleanup process finished.")

atexit.register(perform_cleanup)

# --- Health Check Tools ---
@app.tool(
    description="Check if Turkish government legal database servers are operational",
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True
    }
)
async def check_government_servers_health() -> Dict[str, Any]:
    """Check health status of Turkish government legal database servers."""
    logger.info("Health check tool called for government servers")
    
    health_results = {}
    
    # Check Yargıtay server
    try:
        yargitay_payload = {
            "data": {
                "aranan": "karar",
                "arananKelime": "karar", 
                "pageSize": 10,
                "pageNumber": 1
            }
        }
        
        async with httpx.AsyncClient(
            headers={
                "Accept": "*/*",
                "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Connection": "keep-alive",
                "Content-Type": "application/json; charset=UTF-8",
                "Origin": "https://karararama.yargitay.gov.tr",
                "Referer": "https://karararama.yargitay.gov.tr/",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors", 
                "Sec-Fetch-Site": "same-origin",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
                "X-Requested-With": "XMLHttpRequest"
            },
            timeout=30.0,
            verify=False
        ) as client:
            response = await client.post(
                "https://karararama.yargitay.gov.tr/aramalist",
                json=yargitay_payload
            )
            
            if response.status_code == 200:
                response_data = response.json()
                records_total = response_data.get("data", {}).get("recordsTotal", 0)
                
                if records_total > 0:
                    health_results["yargitay"] = {
                        "status": "healthy",
                        "response_time_ms": response.elapsed.total_seconds() * 1000
                    }
                else:
                    health_results["yargitay"] = {
                        "status": "unhealthy",
                        "reason": "recordsTotal is 0 or missing",
                        "response_time_ms": response.elapsed.total_seconds() * 1000
                    }
            else:
                health_results["yargitay"] = {
                    "status": "unhealthy", 
                    "reason": f"HTTP {response.status_code}",
                    "response_time_ms": response.elapsed.total_seconds() * 1000
                }
                
    except Exception as e:
        health_results["yargitay"] = {
            "status": "unhealthy",
            "reason": f"Connection error: {str(e)}"
        }
    
    # Check Bedesten API server
    try:
        bedesten_payload = {
            "data": {
                "pageSize": 5,
                "pageNumber": 1,
                "itemTypeList": ["YARGITAYKARARI"], 
                "phrase": "karar",
                "sortFields": ["KARAR_TARIHI"],
                "sortDirection": "desc"
            },
            "applicationName": "UyapMevzuat",
            "paging": True
        }
        
        async with httpx.AsyncClient(
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 Health Check"
            },
            timeout=30.0,
            verify=False
        ) as client:
            response = await client.post(
                "https://bedesten.adalet.gov.tr/emsal-karar/searchDocuments",
                json=bedesten_payload
            )
            
            if response.status_code == 200:
                response_data = response.json()
                logger.debug(f"Bedesten API response: {response_data}")
                if response_data and isinstance(response_data, dict):
                    data_section = response_data.get("data")
                    if data_section and isinstance(data_section, dict):
                        total_found = data_section.get("total", 0)
                    else:
                        total_found = 0
                else:
                    total_found = 0
                
                if total_found > 0:
                    health_results["bedesten"] = {
                        "status": "healthy", 
                        "response_time_ms": response.elapsed.total_seconds() * 1000
                    }
                else:
                    health_results["bedesten"] = {
                        "status": "unhealthy",
                        "reason": "total is 0 or missing in data field",
                        "response_time_ms": response.elapsed.total_seconds() * 1000
                    }
            else:
                health_results["bedesten"] = {
                    "status": "unhealthy",
                    "reason": f"HTTP {response.status_code}",
                    "response_time_ms": response.elapsed.total_seconds() * 1000
                }
                
    except Exception as e:
        health_results["bedesten"] = {
            "status": "unhealthy", 
            "reason": f"Connection error: {str(e)}"
        }
    
    # Overall health assessment
    healthy_servers = sum(1 for server in health_results.values() if server["status"] == "healthy")
    total_servers = len(health_results)
    
    overall_status = "healthy" if healthy_servers == total_servers else "degraded" if healthy_servers > 0 else "unhealthy"
    
    return {
        "overall_status": overall_status,
        "healthy_servers": healthy_servers,
        "total_servers": total_servers,
        "servers": health_results,
        "check_timestamp": f"{__import__('datetime').datetime.now().isoformat()}"
    }

# --- MCP Tools for KVKK ---
@app.tool(
    description="Search KVKK data protection authority decisions",
    annotations={
        "readOnlyHint": True,
        "openWorldHint": True,
        "idempotentHint": True
    }
)
async def search_kvkk_decisions(
    keywords: str = Field(..., description="Turkish keywords. Supports +required -excluded \"exact phrase\" operators"),
    page: int = Field(1, ge=1, le=50, description="Page number for results (1-50)."),
    # pageSize: int = Field(10, ge=1, le=20, description="Number of results per page (1-20).")
) -> KvkkSearchResult:
    """Search function for legal decisions."""
    logger.info(f"KVKK search tool called with keywords: {keywords}")
    
    pageSize = 10  # Default value
    
    search_request = KvkkSearchRequest(
        keywords=keywords,
        page=page,
        pageSize=pageSize
    )
    
    try:
        result = await kvkk_client_instance.search_decisions(search_request)
        logger.info(f"KVKK search completed. Found {len(result.decisions)} decisions on page {page}")
        return result
    except Exception as e:
        logger.exception(f"Error in KVKK search: {e}")
        # Return empty result on error
        return KvkkSearchResult(
            decisions=[],
            total_results=0,
            page=page,
            pageSize=pageSize,
            query=keywords
        )

@app.tool(
    description="Get KVKK decision document in Markdown format with metadata extraction",
    annotations={
        "readOnlyHint": True,
        "openWorldHint": False,
        "idempotentHint": True
    }
)
async def get_kvkk_document_markdown(
    decision_url: str = Field(..., description="KVKK decision URL from search results"),
    page_number: int = Field(1, ge=1, description="Page number for paginated Markdown content (1-indexed, accepts int). Default is 1 (first 5,000 characters).")
) -> KvkkDocumentMarkdown:
    """Get KVKK decision as paginated Markdown."""
    logger.info(f"KVKK document retrieval tool called for URL: {decision_url}")
    
    if not decision_url or not decision_url.strip():
        return KvkkDocumentMarkdown(
            source_url=HttpUrl("https://www.kvkk.gov.tr"),
            title=None,
            decision_date=None,
            decision_number=None,
            subject_summary=None,
            markdown_chunk=None,
            current_page=page_number or 1,
            total_pages=0,
            is_paginated=False,
            error_message="Decision URL is required and cannot be empty."
        )
    
    try:
        # Validate URL format
        if not decision_url.startswith("https://www.kvkk.gov.tr/"):
            return KvkkDocumentMarkdown(
                source_url=HttpUrl(decision_url),
                title=None,
                decision_date=None,
                decision_number=None,
                subject_summary=None,
                markdown_chunk=None,
                current_page=page_number or 1,
                total_pages=0,
                is_paginated=False,
                error_message="Invalid KVKK decision URL format. URL must start with https://www.kvkk.gov.tr/"
            )
        
        result = await kvkk_client_instance.get_decision_document(decision_url, page_number or 1)
        logger.info(f"KVKK document retrieved successfully. Page {result.current_page}/{result.total_pages}, Content length: {len(result.markdown_chunk) if result.markdown_chunk else 0}")
        return result
        
    except Exception as e:
        logger.exception(f"Error retrieving KVKK document: {e}")
        return KvkkDocumentMarkdown(
            source_url=HttpUrl(decision_url),
            title=None,
            decision_date=None,
            decision_number=None,
            subject_summary=None,
            markdown_chunk=None,
            current_page=page_number or 1,
            total_pages=0,
            is_paginated=False,
            error_message=f"Error retrieving KVKK document: {str(e)}"
        )

# --- MCP Tools for BDDK (Banking Regulation Authority) ---
@app.tool(
    description="Search BDDK banking regulation decisions",
    annotations={
        "readOnlyHint": True,
        "openWorldHint": True,
        "idempotentHint": True
    }
)
async def search_bddk_decisions(
    keywords: str = Field(..., description="Search keywords in Turkish"),
    page: int = Field(1, ge=1, description="Page number")
    # pageSize: int = Field(10, ge=1, le=50, description="Results per page")
) -> dict:
    """Search BDDK banking regulation and supervision decisions."""
    logger.info(f"BDDK search tool called with keywords: {keywords}, page: {page}")
    
    pageSize = 10  # Default value
    
    try:
        search_request = BddkSearchRequest(
            keywords=keywords,
            page=page,
            pageSize=pageSize
        )
        
        result = await bddk_client_instance.search_decisions(search_request)
        logger.info(f"BDDK search completed. Found {len(result.decisions)} decisions on page {page}")
        
        return {
            "decisions": [
                {
                    "title": dec.title,
                    "document_id": dec.document_id,
                    "content": dec.content
                }
                for dec in result.decisions
            ],
            "total_results": result.total_results,
            "page": result.page,
            "pageSize": result.pageSize
        }
    
    except Exception as e:
        logger.exception(f"Error searching BDDK decisions: {e}")
        return {
            "decisions": [],
            "total_results": 0,
            "page": page,
            "pageSize": pageSize,
            "error": str(e)
        }

@app.tool(
    description="Get BDDK decision document as Markdown",
    annotations={
        "readOnlyHint": True,
        "openWorldHint": False,
        "idempotentHint": True
    }
)
async def get_bddk_document_markdown(
    document_id: str = Field(..., description="BDDK document ID (e.g., '310')"),
    page_number: int = Field(1, ge=1, description="Page number")
) -> dict:
    """Retrieve BDDK decision document in Markdown format."""
    logger.info(f"BDDK document retrieval tool called for ID: {document_id}, page: {page_number}")
    
    if not document_id or not document_id.strip():
        return {
            "document_id": document_id,
            "markdown_content": "",
            "page_number": page_number,
            "total_pages": 0,
            "error": "Document ID is required"
        }
    
    try:
        result = await bddk_client_instance.get_document_markdown(document_id, page_number)
        logger.info(f"BDDK document retrieved successfully. Page {result.page_number}/{result.total_pages}")
        
        return {
            "document_id": result.document_id,
            "markdown_content": result.markdown_content,
            "page_number": result.page_number,
            "total_pages": result.total_pages
        }
        
    except Exception as e:
        logger.exception(f"Error retrieving BDDK document: {e}")
        return {
            "document_id": document_id,
            "markdown_content": "",
            "page_number": page_number,
            "total_pages": 0,
            "error": str(e)
        }

# --- ChatGPT Deep Research Compatible Tools ---

def get_preview_text(markdown_content: str, skip_chars: int = 100, preview_chars: int = 200) -> str:
    """
    Extract a preview of document text by skipping headers and showing meaningful content.
    
    Args:
        markdown_content: Full document content in markdown format
        skip_chars: Number of characters to skip from the beginning (default: 100)
        preview_chars: Number of characters to show in preview (default: 200)
    
    Returns:
        Preview text suitable for ChatGPT Deep Research
    """
    if not markdown_content:
        return ""
    
    # Remove common markdown artifacts and clean up
    cleaned_content = markdown_content.strip()
    
    # Skip the first N characters (usually headers, metadata)
    if len(cleaned_content) > skip_chars:
        content_start = cleaned_content[skip_chars:]
    else:
        content_start = cleaned_content
    
    # Get the next N characters for preview
    if len(content_start) > preview_chars:
        preview = content_start[:preview_chars]
    else:
        preview = content_start
    
    # Clean up the preview - remove incomplete sentences at the end
    preview = preview.strip()
    
    # If preview ends mid-sentence, try to end at last complete sentence
    if preview and not preview.endswith('.'):
        last_period = preview.rfind('.')
        if last_period > 50:  # Only if there's a reasonable sentence
            preview = preview[:last_period + 1]
    
    # Add ellipsis if content was truncated
    if len(content_start) > preview_chars:
        preview += "..."
    
    return preview.strip()

@app.tool(
    description="DO NOT USE unless you are ChatGPT Deep Research. Search Turkish courts (Turkish keywords only). Supports: +term (must have), -term (exclude), \"exact phrase\", term1 OR term2",
    annotations={
        "readOnlyHint": True,
        "openWorldHint": True,
        "idempotentHint": True
    }
)
async def search(
    query: str = Field(..., description="Turkish search query")
) -> Dict[str, List[Dict[str, str]]]:
    """
    Bedesten API search tool for ChatGPT Deep Research compatibility.
    
    This tool searches Turkish legal databases via the unified Bedesten API.
    It supports advanced search operators and covers all major court types.
    
    USAGE RESTRICTION: Only for ChatGPT Deep Research workflows.
    For regular legal research, use search_bedesten_unified with specific court types.
    
    Returns:
    Object with "results" field containing a list of documents with id, title, text preview, and url
    as required by ChatGPT Deep Research specification.
    """
    logger.info(f"ChatGPT Deep Research search tool called with query: {query}")
    
    results = []
    
    try:
        # Search all court types via unified Bedesten API
        court_types = [
            ("YARGITAYKARARI", "Yargıtay", "yargitay_bedesten"),
            ("DANISTAYKARAR", "Danıştay", "danistay_bedesten"), 
            ("YERELHUKUK", "Yerel Hukuk Mahkemesi", "yerel_hukuk_bedesten"),
            ("ISTINAFHUKUK", "İstinaf Hukuk Mahkemesi", "istinaf_hukuk_bedesten"),
            ("KYB", "Kanun Yararına Bozma", "kyb_bedesten")
        ]
        
        for item_type, court_name, id_prefix in court_types:
            try:
                search_results = await bedesten_client_instance.search_documents(
                    BedestenSearchRequest(
                        data=BedestenSearchData(
                            phrase=query,  # Use query as-is to support both regular and exact phrase searches
                            itemTypeList=[item_type],
                            pageSize=10,
                            pageNumber=1
                        )
                    )
                )
                
                # Handle potential None data
                if search_results.data is None:
                    logger.warning(f"No data returned from Bedesten API for {court_name}")
                    continue
                
                # Add results from this court type (limit to top 5 per court)
                for decision in search_results.data.emsalKararList[:5]:
                    # For ChatGPT Deep Research, fetch document content for preview
                    try:
                        # Fetch document content for preview
                        doc = await bedesten_client_instance.get_document_as_markdown(decision.documentId)
                        
                        # Generate preview text (skip first 100 chars, show next 200)
                        preview_text = get_preview_text(doc.markdown_content, skip_chars=100, preview_chars=200)
                        
                        # Build title from metadata
                        title_parts = []
                        if decision.birimAdi:
                            title_parts.append(decision.birimAdi)
                        if decision.esasNo:
                            title_parts.append(f"Esas: {decision.esasNo}")
                        if decision.kararNo:
                            title_parts.append(f"Karar: {decision.kararNo}")
                        if decision.kararTarihiStr:
                            title_parts.append(f"Tarih: {decision.kararTarihiStr}")
                        
                        if title_parts:
                            title = " - ".join(title_parts)
                        else:
                            title = f"{court_name} - Document {decision.documentId}"
                        
                        # Add to results in OpenAI format
                        results.append({
                            "id": decision.documentId,
                            "title": title,
                            "text": preview_text,
                            "url": f"https://mevzuat.adalet.gov.tr/ictihat/{decision.documentId}"
                        })
                        
                    except Exception as e:
                        logger.warning(f"Could not fetch preview for document {decision.documentId}: {e}")
                        # Add minimal result without preview
                        results.append({
                            "id": decision.documentId,
                            "title": f"{court_name} - Document {decision.documentId}",
                            "text": "Document preview not available",
                            "url": f"https://mevzuat.adalet.gov.tr/ictihat/{decision.documentId}"
                        })
                    
                if search_results.data:
                    logger.info(f"Found {len(search_results.data.emsalKararList)} results from {court_name}")
                else:
                    logger.info(f"Found 0 results from {court_name} (no data returned)")
                
            except Exception as e:
                logger.warning(f"Bedesten API search error for {court_name}: {e}")
        
        # Comment out other API implementations for ChatGPT Deep Research
        """
        # Other API implementations disabled for ChatGPT Deep Research
        # These are available through specific court tools:
        
        # Yargıtay Official API - use search_yargitay_detailed instead
        # Danıştay Official API - use search_danistay_by_keyword instead  
        # Constitutional Court - use search_anayasa_norm_denetimi_decisions instead
        # Competition Authority - use search_rekabet_kurumu_decisions instead
        # Public Procurement Authority - use search_kik_decisions instead
        # Court of Accounts - use search_sayistay_* tools instead
        # UYAP Emsal - use search_emsal_detailed_decisions instead
        # Jurisdictional Disputes Court - use search_uyusmazlik_decisions instead
        """
        
        logger.info(f"ChatGPT Deep Research search completed. Found {len(results)} results via Bedesten API.")
        return {"results": results}
        
    except Exception as e:
        logger.exception("Error in ChatGPT Deep Research search tool")
        # Return partial results if any were found
        if results:
            return {"results": results}
        raise

@app.tool(
    description="DO NOT USE unless you are ChatGPT Deep Research. Fetch document by ID. See docs for details",
    annotations={
        "readOnlyHint": True,
        "openWorldHint": False,  # Retrieves specific documents, not exploring
        "idempotentHint": True
    }
)
async def fetch(
    id: str = Field(..., description="Document identifier from search results (numeric only)")
) -> Dict[str, Any]:
    """
    Bedesten API fetch tool for ChatGPT Deep Research compatibility.
    
    Retrieves the full text content of Turkish legal documents via unified Bedesten API.
    Converts documents from HTML/PDF to clean Markdown format.
    
    USAGE RESTRICTION: Only for ChatGPT Deep Research workflows.
    For regular legal research, use specific court document tools.
    
    Input Format:
    - id: Numeric document identifier from search results (e.g., "730113500", "71370900")
    
    Returns:
    Single object with numeric id, title, text (full Markdown content), mevzuat.adalet.gov.tr url, and metadata fields
    as required by ChatGPT Deep Research specification.
    """
    logger.info(f"ChatGPT Deep Research fetch tool called for document ID: {id}")
    
    if not id or not id.strip():
        raise ValueError("Document ID must be a non-empty string")
    
    try:
        # Use the numeric ID directly with Bedesten API
        doc = await bedesten_client_instance.get_document_as_markdown(id)
        
        # Try to get additional metadata by searching for this specific document
        title = f"Turkish Legal Document {id}"
        try:
            # Quick search to get metadata for better title
            search_results = await bedesten_client_instance.search_documents(
                BedestenSearchRequest(
                    data=BedestenSearchData(
                        phrase=id,  # Search by document ID
                        pageSize=1,
                        pageNumber=1
                    )
                )
            )
            
            if search_results.data and search_results.data.emsalKararList:
                decision = search_results.data.emsalKararList[0]
                if decision.documentId == id:
                    # Build a proper title from metadata
                    title_parts = []
                    if decision.birimAdi:
                        title_parts.append(decision.birimAdi)
                    if decision.esasNo:
                        title_parts.append(f"Esas: {decision.esasNo}")
                    if decision.kararNo:
                        title_parts.append(f"Karar: {decision.kararNo}")
                    if decision.kararTarihiStr:
                        title_parts.append(f"Tarih: {decision.kararTarihiStr}")
                    
                    if title_parts:
                        title = " - ".join(title_parts)
                    else:
                        title = f"Turkish Legal Decision {id}"
        except Exception as e:
            logger.warning(f"Could not fetch metadata for document {id}: {e}")
        
        return {
            "id": id,
            "title": title,
            "text": doc.markdown_content,
            "url": f"https://mevzuat.adalet.gov.tr/ictihat/{id}",
            "metadata": {
                "database": "Turkish Legal Database via Bedesten API",
                "document_id": id,
                "source_url": doc.source_url,
                "mime_type": doc.mime_type,
                "api_source": "Bedesten Unified API",
                "chatgpt_deep_research": True
            }
        }
        
        # Comment out other API implementations for ChatGPT Deep Research
        """
        # Other API implementations disabled for ChatGPT Deep Research
        # These are available through specific court document tools:
        
        elif id.startswith("yargitay_"):
            # Yargıtay Official API - use get_yargitay_document_markdown instead
            doc_id = id.replace("yargitay_", "")
            doc = await yargitay_client_instance.get_decision_document_as_markdown(doc_id)
            
        elif id.startswith("danistay_"):
            # Danıştay Official API - use get_danistay_document_markdown instead
            doc_id = id.replace("danistay_", "")
            doc = await danistay_client_instance.get_decision_document_as_markdown(doc_id)
            
        elif id.startswith("anayasa_"):
            # Constitutional Court - use get_anayasa_norm_denetimi_document_markdown instead
            doc_id = id.replace("anayasa_", "")
            doc = await anayasa_norm_client_instance.get_decision_document_as_markdown(...)
            
        elif id.startswith("rekabet_"):
            # Competition Authority - use get_rekabet_kurumu_document instead
            doc_id = id.replace("rekabet_", "")
            doc = await rekabet_client_instance.get_decision_document(...)
            
        elif id.startswith("kik_"):
            # Public Procurement Authority - use get_kik_decision_document_as_markdown instead
            doc_id = id.replace("kik_", "")
            doc = await kik_client_instance.get_decision_document_as_markdown(doc_id)
            
        elif id.startswith("local_"):
            # This was already using Bedesten API, but deprecated for ChatGPT Deep Research
            doc_id = id.replace("local_", "")
            doc = await bedesten_client_instance.get_document_as_markdown(doc_id)
        """
        
    except Exception as e:
        logger.exception(f"Error fetching ChatGPT Deep Research document {id}")
        raise

# --- Token Metrics Tool Removed for Optimization ---

def ensure_playwright_browsers():
    """Ensure Playwright browsers are installed for KIK tool functionality."""
    try:
        import subprocess
        import os
        
        # Check if chromium is already installed
        chromium_path = os.path.expanduser("~/Library/Caches/ms-playwright/chromium-1179")
        if os.path.exists(chromium_path):
            logger.info("Playwright Chromium browser already installed.")
            return
        
        logger.info("Installing Playwright Chromium browser for KIK tool...")
        result = subprocess.run(
            ["python", "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes timeout
        )
        
        if result.returncode == 0:
            logger.info("Playwright Chromium browser installed successfully.")
        else:
            logger.warning(f"Failed to install Playwright browser: {result.stderr}")
            logger.warning("KIK tool may not work properly without Playwright browsers.")
            
    except Exception as e:
        logger.warning(f"Could not auto-install Playwright browsers: {e}")
        logger.warning("KIK tool may not work properly. Manual installation: 'playwright install chromium'")

def main():
    logger.info(f"Starting {app.name} server via main() function...")
    logger.info(f"Logs will be written to: {LOG_FILE_PATH}")
    
    # Ensure Playwright browsers are installed
    ensure_playwright_browsers()
    
    try:
        app.run()
    except KeyboardInterrupt: 
        logger.info("Server shut down by user (KeyboardInterrupt).")
    except Exception as e: 
        logger.exception("Server failed to start or crashed.")
    finally:
        logger.info(f"{app.name} server has shut down.")

if __name__ == "__main__": 
    main()