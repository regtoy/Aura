# ACF-RAG Projesi Geliştirme Dokümanı (v1)

## 1. Giriş
Bu doküman, Amasya Üniversitesi için planlanan Agentic Corrective-Fusion RAG (ACF-RAG) platformunun "v1" sürümü için izlenecek geliştirme yaklaşımını, bileşenleri ve beklenen çıktılarını detaylandırır. Önceki planlama çıktılarında tanımlanan mimariyi gerçek bir ürün haline getirmek üzere yazılım geliştirme, veri hazırlama ve operasyon adımlarını sistematik hale getirir.

## 2. Genel Hedefler
- Üniversitenin kurumsal içeriğini çok katmanlı şekilde sorgulayabilen, kaynak gösteren ve güncelliği doğrulayan bir sohbet yapay zekâsı sunmak.
- Yerel bilgi tabanı, whitelist kontrollü web agent ve HITL ticket döngüsünü tek bir orkestrasyon altında birleştirmek.
- Dinamik güven eşiği, temporal doğrulama, citation yönetimi ve loglama altyapısını kapsayan üretim kalitesinde bir çözüm hazırlamak.

## 3. Mimari Genel Bakış
### 3.1. Bileşenler
1. **FastAPI API Katmanı** – REST/WS uç noktaları, kimlik/rol doğrulama.
2. **LangGraph Orkestratörü** – RAG-fusion, CRAG, temporal kontrol, agent ve ticket yönlendirme.
3. **RAG Katmanı** – Qdrant tabanlı vektör arama + opsiyonel BM25 füzyonu.
4. **ReAct Tabanlı Web Agent** – whitelist ile sınırlı, ScrapeGraphAI destekli içerik toplama.
5. **Ticket/HITL Servisi** – PostgreSQL tabanlı bilet yönetimi, normalize & embed akışı.
6. **Streamlit Arayüzü** – Öğrenci, idari ve ticket yönetimi sekmeleri.
7. **Gözlemlenebilirlik** – Structlog, Prometheus/Grafana ve OpenTelemetry izleme.

### 3.2. Veri ve Model Katmanı
- **Vektör DB:** Qdrant `amasya_kb` koleksiyonu.
- **Embeddings:** `multilingual-e5-large` (PEFT-LoRA ile alan ince ayarı).
- **LLM:** LM Studio üzerinden servis edilen `qwen2.5-14b-instruct` (tool-calling yetenekli).
- **Ticket ve istatistikler:** PostgreSQL tabloları (`tickets`, `ticket_messages`, `confidence_stats`, `allowed_domains`, `users`).

## 4. Geliştirme Yol Haritası
| Faz | Hedef | Açıklama |
| --- | --- | --- |
| F1 | API Temelleri | FastAPI iskeleti, RBAC, Qdrant/PostgreSQL bağlantı testleri.
| F2 | RAG-Fusion | Sorgu genişletme, RRF füzyonu, ince ayarlı embedding pipeline.
| F3 | CRAG + Dinamik Eşik | Değerlendirici modeli, `confidence_stats` tablosu ve adaptif eşikler.
| F4 | Agent Katmanı | ReAct workflow, whitelist kontrolü, kalite metrikleri.
| F5 | Yanıt Derleyici | Citation yönetimi, temporal doğrulama ve streaming kurgusu.
| F6 | Ticket Döngüsü | Ticket CRUD, normalize/embed işlemleri, Streamlit yönetim paneli.
| F7 | Observability | Log şeması, Prometheus metrikleri, uyarı politikaları.

## 5. Test ve Doğrulama Stratejisi
- **Retrieval Doğrulaması:** Türkçe MTEB alt setleri + alan içi manuel değerlendirme.
- **Pipeline Senaryoları:** KB yeterli / eksik / eski; agent tetiklenmesi ve ticket oluşturma.
- **Temporal Kontroller:** 90 gün kuralı, tarih çakışmalarında karar mekanizması.
- **RBAC ve UI Akışları:** Öğrenci vs idari yetkileri, ticket yönetimi.
- **Güvenlik:** Whitelist bypass, rate limit, PII maskeleme testleri.

## 6. Operasyonel Hazırlık
- **Sürümleme:** Semantic Versioning, `models.yaml` ile model takip.
- **CI/CD:** GitHub Actions – lint, tip kontrol, pytest, docker-compose servisleri.
- **Konfigürasyon:** `.env` şablonları, `pydantic-settings` veya `dynaconf` yönetimi.
- **Günlük/Log Yönetimi:** JSON formatlı structlog, trace-id, span-id içeren kayıt yapısı.
- **Metrik Gösterge Paneli:** Prometheus exporter’ları ve Grafana panelleri (agent tetikleme, ticket kuyruğu, latency).

## 7. Çıktı Beklentileri
- Her faz sonunda versiyonlanabilir kod ve güncellenmiş dokümantasyon.
- Ticket ve agent kullanım oranlarını izleyen rapor seti.
- HITL döngüsü sonucunda bilgi tabanına geri beslenen kayıtlar.

Bu doküman, kod üretimi ve sprint planlaması sırasında referans olarak kullanılacak ana geliştirme rehberidir.
