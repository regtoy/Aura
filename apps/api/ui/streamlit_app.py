from __future__ import annotations

import os
from typing import Callable, Sequence

import streamlit as st

from apps.api.dependencies.auth import Role
from apps.api.services.tickets import TicketStatus
from apps.api.ui.api import APIError, AuraAPIClient
from apps.api.ui.auth import AuthProfile, preset_profiles, resolve_token
from apps.api.ui.utils import parse_document_lines, parse_metadata

DEFAULT_BASE_URL = os.getenv("AURA_API_BASE_URL", "http://localhost:8000")


def _get_auth_profile() -> AuthProfile:
    profile = st.session_state.get("auth_profile")
    if isinstance(profile, AuthProfile):
        return profile
    fallback = resolve_token(None)
    if fallback is None:  # pragma: no cover - yapılandırma hatası
        raise RuntimeError("Varsayılan profil bulunamadı")
    st.session_state["auth_profile"] = fallback
    return fallback


def _set_auth_profile(profile: AuthProfile) -> None:
    st.session_state["auth_profile"] = profile
    st.session_state["manual_token"] = profile.token or ""


def _get_base_url() -> str:
    base_url = st.session_state.get("base_url")
    if not base_url:
        base_url = DEFAULT_BASE_URL
        st.session_state["base_url"] = base_url
    return str(base_url)


def _build_client() -> AuraAPIClient:
    profile = _get_auth_profile()
    base_url = _get_base_url()
    return AuraAPIClient(base_url=base_url, token=profile.token)


def _render_sidebar() -> None:
    st.sidebar.header("Bağlantı")
    base_url = st.sidebar.text_input("API Base URL", value=_get_base_url(), key="base_url")
    st.session_state["base_url"] = base_url

    st.sidebar.header("Kimlik Doğrulama")
    options = list(preset_profiles())
    labels = [profile.label for profile in options]
    selected_label = st.sidebar.selectbox("Hazır profiller", options=labels, index=labels.index(_get_auth_profile().label))
    selected_profile = next(profile for profile in options if profile.label == selected_label)
    if st.sidebar.button("Profili Kullan"):
        _set_auth_profile(selected_profile)
        st.sidebar.success(f"{selected_profile.username} profili seçildi")

    manual_token = st.sidebar.text_input("Manuel token", value=st.session_state.get("manual_token", ""), key="manual_token")
    if st.sidebar.button("Token ile giriş"):
        profile = resolve_token(manual_token)
        if profile is None:
            st.sidebar.error("Token doğrulanamadı")
        else:
            _set_auth_profile(profile)
            st.sidebar.success(f"{profile.username} olarak giriş yapıldı")

    if st.sidebar.button("Çıkış yap"):
        _set_auth_profile(resolve_token(None))
        st.sidebar.info("Anonim moda geçildi")

    active_profile = _get_auth_profile()
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**Aktif Kullanıcı:** {active_profile.username}")
    st.sidebar.caption(
        "Roller: " + ", ".join(role.value for role in active_profile.roles)
    )
    if active_profile.token:
        st.sidebar.code(active_profile.token, language="text")
    else:
        st.sidebar.caption("Token kullanılmıyor (anonim erişim)")


def _handle_api_call(
    callback: Callable[[], object], success_message: str | None = None
) -> tuple[bool, object | None]:
    try:
        result = callback()
    except APIError as exc:
        st.error(str(exc))
        return False, None
    else:
        if success_message:
            st.success(success_message)
        return True, result


def _render_student_tab(client: AuraAPIClient) -> None:
    st.subheader("Öğrenci Portalı")
    st.write(
        "Yanıt derleyici servisine bağlanarak metninizi citation bilgileriyle derleyebilirsiniz. "
        "Her satıra `belge_id, skor` formatında kaynak ekleyin."
    )

    with st.form("answer_form"):
        answer_text = st.text_area("Yanıt Metni", height=180)
        docs_raw = st.text_area(
            "Kaynaklar",
            height=120,
            placeholder="makale-1,0.92\nmakale-2,0.75",
        )
        submitted = st.form_submit_button("Yanıtı Derle")

    if submitted:
        if not answer_text.strip():
            st.warning("Yanıt metni boş olamaz")
            return
        try:
            documents = parse_document_lines(docs_raw)
        except ValueError as exc:
            st.error(str(exc))
            return

        success, result = _handle_api_call(
            lambda: client.compile_answer(answer=answer_text, documents=documents),
            "Yanıt başarıyla derlendi",
        )
        if not success or not isinstance(result, dict):
            return

        answer = result.get("answer")
        citations = result.get("citations")
        if answer:
            st.markdown("### Derlenmiş Yanıt")
            st.write(answer)
        if citations:
            st.markdown("### Citation Listesi")
            for citation in citations:
                st.write(
                    f"• {citation.get('document_id', '')} – skor: {citation.get('score', 0):.2f} (rota: {citation.get('route', '-')})"
                )
                metadata = citation.get("metadata")
                if metadata:
                    st.json(metadata)
        elif citations == []:
            st.info("Dönen citation bulunamadı")


def _render_admin_tab(client: AuraAPIClient) -> None:
    st.subheader("İdari Kontroller")
    st.write("Servisin durumunu izlemek ve RBAC kısıtlarını doğrulamak için yardımcı araçlar.")

    col_ping, col_secure = st.columns(2)
    if col_ping.button("/ping çağrısı"):
        success, result = _handle_api_call(client.ping, "Genel sağlık kontrolü başarılı")
        if success and isinstance(result, dict):
            col_ping.json(result)

    if col_secure.button("/ping/secure çağrısı"):
        success, result = _handle_api_call(client.secure_ping, "Yetkili sağlık kontrolü başarılı")
        if success and isinstance(result, dict):
            col_secure.json(result)


def _render_ticket_tab(client: AuraAPIClient) -> None:
    st.subheader("Ticket Yönetimi")
    st.write("Ticket servisi üzerinden kayıtları listeleyebilir, oluşturabilir ve güncelleyebilirsiniz.")

    st.markdown("### Ticket Listesi")
    if st.button("Ticketları Yenile"):
        success, tickets = _handle_api_call(client.list_tickets)
        if success:
            st.session_state["ticket_list"] = tickets
    ticket_list = st.session_state.get("ticket_list")
    if ticket_list:
        st.table(ticket_list)
    else:
        st.caption("Henüz ticket verisi yok")

    st.markdown("### Yeni Ticket Oluştur")
    with st.form("create_ticket_form"):
        title = st.text_input("Başlık")
        content = st.text_area("Açıklama")
        priority = st.selectbox("Öncelik", options=["low", "medium", "high"], index=1)
        metadata_raw = st.text_area("Metadata (JSON)", value="{}")
        create_submitted = st.form_submit_button("Ticket Oluştur")

    if create_submitted:
        if not title.strip() or not content.strip():
            st.error("Başlık ve açıklama zorunludur")
        else:
            try:
                metadata = parse_metadata(metadata_raw)
            except ValueError as exc:
                st.error(str(exc))
            else:
                success, ticket = _handle_api_call(
                    lambda: client.create_ticket(title=title, content=content, priority=priority, metadata=metadata),
                    "Ticket oluşturuldu",
                )
                if success and isinstance(ticket, dict):
                    st.session_state["selected_ticket"] = ticket

    st.markdown("### Ticket Detayları")
    detail_col, delete_col = st.columns([3, 1])
    ticket_id = detail_col.text_input("Ticket ID", key="ticket_lookup")
    if detail_col.button("Getir"):
        success, detail = _handle_api_call(lambda: client.get_ticket(ticket_id))
        if success and isinstance(detail, dict):
            st.session_state["selected_ticket"] = detail
    if delete_col.button("Sil"):
        if not ticket_id:
            st.error("Silme işlemi için Ticket ID gerekli")
        else:
            success, _ = _handle_api_call(lambda: client.delete_ticket(ticket_id), "Ticket silindi")
            if success:
                st.session_state.pop("selected_ticket", None)
                st.session_state.pop("ticket_list", None)

    detail = st.session_state.get("selected_ticket")
    if isinstance(detail, dict):
        st.markdown(f"#### {detail.get('title', 'Ticket')} ({detail.get('status')})")
        meta_cols = st.columns(3)
        meta_cols[0].metric("Öncelik", detail.get("priority"))
        meta_cols[1].metric("Talep Sahibi", detail.get("requester"))
        meta_cols[2].metric("Güncel Durum", detail.get("status"))

        st.markdown("#### Mesajlar")
        for message in detail.get("messages", []):
            st.markdown(
                f"**{message.get('author')}** ({message.get('created_at')}): {message.get('content')}"
            )

        st.markdown("#### Audit Logları")
        if detail.get("audit_logs"):
            for log in detail["audit_logs"]:
                st.write(
                    f"{log.get('created_at')} — {log.get('actor')} {log.get('action')}"
                    f" ({log.get('from_status')} → {log.get('to_status')})"
                )
        else:
            st.caption("Henüz audit kaydı yok")

        st.markdown("#### Mesaj Ekle")
        with st.form("add_message_form"):
            new_message = st.text_area("Mesaj", height=120)
            submit_message = st.form_submit_button("Mesaj Gönder")
        if submit_message:
            if not new_message.strip():
                st.error("Mesaj içeriği boş olamaz")
            else:
                success, updated = _handle_api_call(
                    lambda: client.add_ticket_message(detail["id"], content=new_message),
                    "Mesaj eklendi",
                )
                if success and isinstance(updated, dict):
                    st.session_state["selected_ticket"] = updated

        st.markdown("#### Durum Güncelle")
        with st.form("status_form"):
            status_options: Sequence[str] = [status.value for status in TicketStatus]
            current_status = str(detail.get("status", status_options[0]))
            try:
                default_index = status_options.index(current_status)
            except ValueError:
                default_index = 0
            new_status = st.selectbox("Yeni Durum", options=status_options, index=default_index)
            status_metadata_raw = st.text_area("Ek Metadata (JSON)", value="{}")
            status_submit = st.form_submit_button("Durumu Güncelle")
        if status_submit:
            try:
                status_metadata = parse_metadata(status_metadata_raw)
            except ValueError as exc:
                st.error(str(exc))
            else:
                success, updated_detail = _handle_api_call(
                    lambda: client.change_ticket_status(
                        detail["id"],
                        status=new_status,
                        metadata=status_metadata,
                    ),
                    "Durum güncellendi",
                )
                if success and isinstance(updated_detail, dict):
                    st.session_state["selected_ticket"] = updated_detail
    else:
        st.caption("Ticket detayı için bir kayıt seçin")


def main() -> None:
    st.set_page_config(page_title="Aura Yönetim Paneli", layout="wide")
    _render_sidebar()

    client = _build_client()
    profile = _get_auth_profile()

    tabs: list[tuple[str, Callable[[AuraAPIClient], None], Role]] = [
        ("Öğrenci", _render_student_tab, Role.VIEWER),
        ("İdari", _render_admin_tab, Role.EDITOR),
        ("Ticket Yönetimi", _render_ticket_tab, Role.ADMIN),
    ]

    available = [(label, renderer) for label, renderer, role in tabs if profile.has_role(role)]
    if not available:
        st.info("Bu kullanıcı için yetkili sekme bulunmuyor")
        return

    tab_labels = [item[0] for item in available]
    tab_renderers = [item[1] for item in available]
    tab_objects = st.tabs(tab_labels)

    for tab_object, renderer in zip(tab_objects, tab_renderers):
        with tab_object:
            renderer(client)


if __name__ == "__main__":
    main()
