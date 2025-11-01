# Aura API

Bu depo, FastAPI tabanlı Aura servisinin ilk fazı için temel iskeleti içerir. Proje aşağıdaki bileşenleri sağlar:

- FastAPI uygulama iskeleti
- Rollere dayalı basit bir RBAC kontrolü
- PostgreSQL ve Qdrant servislerine bağlantı testi yardımcıları
- Birim testleri

## Geliştirme

Bağımlılıkları yüklemek için `pip install -e .[dev]` komutunu çalıştırın. Ardından testleri `pytest` ile çalıştırabilirsiniz.

## Streamlit Arayüzü

Adım 15 kapsamında hazırlanan Streamlit tabanlı arayüzü çalıştırmak için `ui` ek paketini kurun ve uygulamayı başlatın:

```bash
pip install -e .[ui]
streamlit run app/ui/streamlit_app.py
```

Arayüz, öğrenci (viewer), idari (editor) ve yönetici (admin) rollerine göre sekmeleri otomatik olarak gösterir. Yan menüdeki hazır profillerden birini seçebilir veya örnek token değerlerini (`viewer-token`, `editor-token`, `admin-token`) kullanarak manuel giriş yapabilirsiniz.
