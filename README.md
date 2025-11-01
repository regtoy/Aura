# Aura API

Bu depo, FastAPI tabanlı Aura servisinin ilk fazı için temel iskeleti içerir. Proje aşağıdaki bileşenleri sağlar:

- FastAPI uygulama iskeleti
- Rollere dayalı basit bir RBAC kontrolü
- PostgreSQL ve Qdrant servislerine bağlantı testi yardımcıları
- Birim testleri

## Geliştirme

Bağımlılıkları yüklemek için `pip install -e .[dev]` komutunu çalıştırın. Ardından testleri `pytest` ile çalıştırabilirsiniz.

## Veritabanı Migrasyonları

Projede SQLModel tabanlı tablolar Alembic ile yönetilmektedir. Migrasyonları uygulamak için aşağıdaki adımları izleyin:

1. Gerekli bağımlılıkları yükleyin: `pip install -e .[dev]`
2. Hedef veritabanını işaret eden `DATABASE_URL` ortam değişkenini (ör. `postgresql+asyncpg://kullanici:sifre@localhost:5432/aura`) tanımlayın.
3. Migrasyonları uygulayın: `alembic -c infra/alembic/alembic.ini upgrade head`

Yeni bir şema değişikliği için otomatik bir revizyon oluşturmak isterseniz `alembic -c infra/alembic/alembic.ini revision --autogenerate -m "açıklama"` komutunu kullanabilirsiniz. Alembic komutları varsayılan olarak `infra/alembic` dizinindeki konfigürasyonu kullanır.

## Gözlemlenebilirlik

Uygulama, başlangıçta yapılandırılabilir bir logger ve isteğe bağlı OpenTelemetry tracer'ı devreye alır. Aşağıdaki ortam değişkenleri `env.example` dosyasında belgelenmiştir ve `.env` dosyanızda düzenlenerek kullanılabilir:

```bash
LOG_LEVEL=INFO
LOG_FORMAT="%(levelname)s %(name)s %(message)s"
OTEL_ENABLED=true
OTEL_SERVICE_NAME=aura-api
OTEL_EXPORTER_OTLP_ENDPOINT=https://otel-collector.example.com/v1/traces
OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer your-token"
```

`OTEL_ENABLED` değişkeni `true` yapıldığında uygulama, belirtilen uç noktaya OTLP protokolüyle iz verilerini göndermeye başlar. Logger varsayılan olarak standart çıkışa yazar ve FastAPI yaşam döngüsü içinde hazır hale getirilir.

## Streamlit Arayüzü

Adım 15 kapsamında hazırlanan Streamlit tabanlı arayüzü çalıştırmak için `ui` ek paketini kurun ve uygulamayı başlatın:

```bash
pip install -e .[ui]
streamlit run app/ui/streamlit_app.py
```

Arayüz, öğrenci (viewer), idari (editor) ve yönetici (admin) rollerine göre sekmeleri otomatik olarak gösterir. Yan menüdeki hazır profillerden birini seçebilir veya örnek token değerlerini (`viewer-token`, `editor-token`, `admin-token`) kullanarak manuel giriş yapabilirsiniz.
