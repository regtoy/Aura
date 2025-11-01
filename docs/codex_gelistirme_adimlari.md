# Codex Destekli Geliştirme Adımları

## Sürüm Geçmişi

| Tarih | Sürüm | Açıklama |
| --- | --- | --- |
| 2025-02-14 | 1.0.1 | Fazlara referans bağlantıları ve çapraz navigasyon eklendi. |
| 2025-02-13 | 1.0.0 | İlk yayınlanan sürüm. |

Aşağıdaki adımlar, Codex tabanlı otomasyon desteği ile ACF-RAG projesinin v1 sürümünü kademeli şekilde inşa etmek için planlanmıştır. Her adım, önceki çıktıların doğrulandığı varsayımıyla ilerler.

Toplam **18 adım** öngörülmüştür.

### Faz Haritası

| Faz | Adımlar | Referans |
| --- | --- | --- |
| F1 | 1-4 | [Geliştirme yol haritasındaki faz özeti](./gelistirme_dokumani_v1.md#4-geli%C5%9Ftirme-yol-haritas%C4%B1) |
| F2 | 5-8 | [F2 açıklaması](./gelistirme_dokumani_v1.md#4-geli%C5%9Ftirme-yol-haritas%C4%B1) |
| F3 | 9-10 | [F3 açıklaması](./gelistirme_dokumani_v1.md#4-geli%C5%9Ftirme-yol-haritas%C4%B1) |
| F4 | 11-12 | [F4 açıklaması](./gelistirme_dokumani_v1.md#4-geli%C5%9Ftirme-yol-haritas%C4%B1) |
| F5 | 13 | [F5 açıklaması](./gelistirme_dokumani_v1.md#4-geli%C5%9Ftirme-yol-haritas%C4%B1) |
| F6 | 14-15 | [F6 açıklaması](./gelistirme_dokumani_v1.md#4-geli%C5%9Ftirme-yol-haritas%C4%B1) |
| F7 | 16-18 | [F7 açıklaması](./gelistirme_dokumani_v1.md#4-geli%C5%9Ftirme-yol-haritas%C4%B1) |

---

<a id="adim-1-proje-iskeletinin-olusturulmasi"></a>
### Adım 1 – Proje İskeletinin Oluşturulması
- Monorepo klasör yapısının (`apps/`, `packages/`, `infra/`, `docs/`) hazırlanması.
- Temel `pyproject.toml` ve ortak bağımlılıkların tanımlanması.

<a id="adim-2-ortak-konfigurasyon-modulu"></a>
### Adım 2 – Ortak Konfigürasyon Modülü
- `pydantic-settings` tabanlı yapılandırma katmanı, `.env` şablonlarının oluşturulması.
- Ortak logger ve OpenTelemetry başlatma fonksiyonları.

<a id="adim-3-fastapi-uygulama-iskeleti"></a>
### Adım 3 – FastAPI Uygulama İskeleti
- `apps/api` altında FastAPI app, health check ve RBAC middleware’inin yerleştirilmesi.
- OAuth2/JWT şeması için temel yapı.

<a id="adim-4-veri-tabani-semalari-postgresql"></a>
### Adım 4 – Veri Tabanı Şemaları (PostgreSQL)
- SQLModel veya SQLAlchemy modelleri (tickets, `ticket_messages`, `allowed_domains`, `confidence_stats`, `users`).
- Alembic migration başlangıcı.

<a id="adim-5-qdrant-istemci-modulu"></a>
### Adım 5 – Qdrant İstemci Modülü
- `packages/retrieval` altında Qdrant bağlantısı, koleksiyon setup fonksiyonu.
- Embedding vektörlerinin şema validasyonu.

<a id="adim-6-embedding-pipeline"></a>
### Adım 6 – Embedding Pipeline
- `sentence-transformers` ile embedding üretimi, ince ayar pipeline betiği.
- `Makefile` veya `invoke` komutlarıyla otomasyon.

<a id="adim-7-langgraph-orkestrator-temeli"></a>
### Adım 7 – LangGraph Orkestratör Temeli
- Graf yapısının iskeleti, düğüm tanımları için arayüzler.
- Durum modeli (`state` dataclass) ve event kayıtları.

<a id="adim-8-sorgu-genisletme-ve-rag-fusion"></a>
### Adım 8 – Sorgu Genişletme ve RAG-Fusion
- `expand_query`, `kb_retrieve` düğümleri.
- Reciprocal Rank Fusion implementasyonu ve testleri.

<a id="adim-9-crag-degerlendirici-entegrasyonu"></a>
### Adım 9 – CRAG Değerlendirici Entegrasyonu
- İnce ayarlı T5 modeli için inference sarmalayıcı.
- `confidence_stats` tablosu ile dinamik eşik okuma/güncelleme.

<a id="adim-10-temporal-dogrulama-modulu"></a>
### Adım 10 – Temporal Doğrulama Modülü
- Tarih çıkarımı yardımcıları, 90 gün kontrol fonksiyonları.
- Metadata çatışması durumunda raporlama.

<a id="adim-11-agent-arac-katmani"></a>
### Adım 11 – Agent Araç Katmanı
- `restricted_search` ve `fetch_page` fonksiyonları.
- Whitelist filtreleme ve kalite skorlayıcı.

<a id="adim-12-react-workflow-entegrasyonu"></a>
### Adım 12 – ReAct Workflow Entegrasyonu
- LangChain/LangGraph ile Thought→Action→Observation döngüsü.
- Adım sınırı, hata yönetimi ve loglama.

<a id="adim-13-yanit-derleyici-ve-citation-yonetimi"></a>
### Adım 13 – Yanıt Derleyici ve Citation Yönetimi
- En iyi 3 kaynağın seçimi, route etiketleme.
- Streaming çıkışı için FastAPI websocket/Server-Sent Events hazırlığı.

<a id="adim-14-ticket-servisi"></a>
### Adım 14 – Ticket Servisi
- CRUD uç noktaları, normalize & embed pipeline’ı.
- Ticket durum makinesi ve audit logları.

<a id="adim-15-streamlit-arayuzu"></a>
### Adım 15 – Streamlit Arayüzü
- Öğrenci, idari ve ticket yönetimi sekmeleri.
- API entegrasyonları, rol bazlı görünürlük.

<a id="adim-16-observability-katmani"></a>
### Adım 16 – Observability Katmanı
- Structlog JSON konfigürasyonu, trace-id üretimi.
- Prometheus metric exporter ve dashboard taslağı.

<a id="adim-17-test-ve-dogrulama-otomasyonu"></a>
### Adım 17 – Test ve Doğrulama Otomasyonu
- Pytest senaryoları (retrieval, agent, ticket akışları).
- Smoke ve yük testleri için `locust` veya `k6` betiği hazırlığı.

<a id="adim-18-cicd-pipeline"></a>
### Adım 18 – CI/CD Pipeline
- GitHub Actions iş akışları: lint, test, tip kontrol, docker-compose servisleri.
- Ortam değişkeni yönetimi ve sürüm paketlemesi.

---

Her adım tamamlandığında, ilgili kod ve dokümantasyon güncellemeleri `main` dalına PR süreciyle entegre edilmelidir.
