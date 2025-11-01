# Codex Destekli Geliştirme Adımları

Aşağıdaki adımlar, Codex tabanlı otomasyon desteği ile ACF-RAG projesinin v1 sürümünü kademeli şekilde inşa etmek için planlanmıştır. Her adım, önceki çıktıların doğrulandığı varsayımıyla ilerler.

Toplam **18 adım** öngörülmüştür.

1. **Proje İskeletinin Oluşturulması**  
   - Monorepo klasör yapısının (`apps/`, `packages/`, `infra/`, `docs/`) hazırlanması.  
   - Temel `pyproject.toml` ve ortak bağımlılıkların tanımlanması.
2. **Ortak Konfigürasyon Modülü**  
   - `pydantic-settings` tabanlı yapılandırma katmanı, `.env` şablonlarının oluşturulması.  
   - Ortak logger ve OpenTelemetry başlatma fonksiyonları.
3. **FastAPI Uygulama İskeleti**  
   - `apps/api` altında FastAPI app, health check ve RBAC middleware’inin yerleştirilmesi.  
   - OAuth2/JWT şeması için temel yapı.
4. **Veri Tabanı Şemaları (PostgreSQL)**  
   - SQLModel veya SQLAlchemy modelleri (tickets, ticket_messages, allowed_domains, confidence_stats, users).  
   - Alembic migration başlangıcı.
5. **Qdrant İstemci Modülü**  
   - `packages/retrieval` altında Qdrant bağlantısı, koleksiyon setup fonksiyonu.  
   - Embedding vektörlerinin schema validasyonu.
6. **Embedding Pipeline**  
   - `sentence-transformers` ile embedding üretimi, ince ayar pipeline betiği.  
   - `Makefile` veya `invoke` komutlarıyla otomasyon.
7. **LangGraph Orkestratör Temeli**  
   - Graf yapısının iskeleti, düğüm tanımları için arayüzler.  
   - Durum modeli (`state` dataclass) ve event kayıtları.
8. **Sorgu Genişletme ve RAG-Fusion**  
   - `expand_query`, `kb_retrieve` düğümleri.  
   - Reciprocal Rank Fusion implementasyonu ve testleri.
9. **CRAG Değerlendirici Entegrasyonu**  
   - İnce ayarlı T5 modeli için inference sarmalayıcı.  
   - `confidence_stats` tablosu ile dinamik eşik okuma/güncelleme.
10. **Temporal Doğrulama Modülü**  
    - Tarih çıkarımı yardımcıları, 90 gün kontrol fonksiyonları.  
    - Metadata çatışması durumunda raporlama.
11. **Agent Araç Katmanı**  
    - `restricted_search` ve `fetch_page` fonksiyonları.  
    - Whitelist filtreleme ve kalite skorlayıcı.
12. **ReAct Workflow Entegrasyonu**  
    - LangChain/LangGraph ile Thought→Action→Observation döngüsü.  
    - Adım sınırı, hata yönetimi ve loglama.
13. **Yanıt Derleyici ve Citation Yönetimi**  
    - En iyi 3 kaynağın seçimi, route etiketleme.  
    - Streaming çıkışı için FastAPI websocket/Server-Sent Events hazırlığı.
14. **Ticket Servisi**  
    - CRUD uç noktaları, normalize & embed pipeline’ı.  
    - Ticket durum makinesi ve audit logları.
15. **Streamlit Arayüzü**  
    - Öğrenci, idari ve ticket yönetimi sekmeleri.  
    - API entegrasyonları, rol bazlı görünürlük.
16. **Observability Katmanı**  
    - Structlog JSON konfigürasyonu, trace-id üretimi.  
    - Prometheus metric exporter ve dashboard taslağı.
17. **Test ve Doğrulama Otomasyonu**  
    - Pytest senaryoları (retrieval, agent, ticket akışları).  
    - Smoke ve yük testleri için `locust` veya `k6` betiği hazırlığı.
18. **CI/CD Pipeline**  
    - GitHub Actions iş akışları: lint, test, tip kontrol, docker-compose servisleri.  
    - Ortam değişkeni yönetimi ve sürüm paketlemesi.

Her adım tamamlandığında, ilgili kod ve dokümantasyon güncellemeleri `main` dalına PR süreciyle entegre edilmelidir.
