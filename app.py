"""Streamlit-приложение для интерактивного запуска протоколов КРК."""
import streamlit as st
import io
import contextlib
import os
from core.runner import run_unified, print_unified_report

st.set_page_config(page_title="Симулятор КРК", layout="wide")

# --- УМНАЯ ПРОВЕРКА НАЛИЧИЯ ФАЙЛОВ (ЧАСТЬ 2) ---
# Проверяем, лежат ли в папке protocols файлы модуля расширения
has_extension = all(
    os.path.exists(f"protocols/{f}") 
    for f in ["e91_alt.py", "bbm92.py", "hybrid.py"]
)

st.title("Симулятор протоколов квантового распределения ключей")
if has_extension:
    st.markdown("Режим: **Полная версия** (Базовая среда + Модуль расширения)")
else:
    st.markdown("Режим: **Базовая версия** (Базовая среда и протокол E91)")

with st.sidebar:
    st.header("Параметры запуска")
    
    # Формируем список доступных протоколов
    available_protocols = ["e91_basic"]
    protocol_names = {"e91_basic": "E91 (базовый, Экерт 1991)"}
    
    if has_extension:
        available_protocols.extend(["e91_alt", "bbm92_plain", "bbm92_chsh", "hybrid"])
        protocol_names.update({
            "e91_alt": "E91 (альтернативный, Φ+)",
            "bbm92_plain": "BBM92 (plain)",
            "bbm92_chsh": "BBM92 (CHSH + ловушки)",
            "hybrid": "Гибридный двухпроходный"
        })

    protocol = st.selectbox(
        "Протокол",
        available_protocols,
        format_func=lambda x: protocol_names[x]
    )
    
    num_runs = st.slider("Итераций (для усреднения)", 1, 20, 5)
    num_pairs = st.slider("Пар на итерацию", 1000, 20000, 5000, step=1000)

    st.subheader("Среда и Атака")
    
    noise_p, eve_q = 0.0, 0.0
    noise_p1, noise_p2, eve_p1, eve_p2 = 0.0, 0.0, 0.0, 0.0
    
    if protocol == "hybrid":
        noise_p1 = st.slider("Шум: Фаза 1 (E91)", 0.0, 0.30, 0.0, 0.01)
        noise_p2 = st.slider("Шум: Фаза 2 (BBM92)", 0.0, 0.30, 0.0, 0.01)
        eve_p1 = st.slider("Ева: Фаза 1 (доля)", 0.0, 1.0, 0.0, 0.05)
        eve_p2 = st.slider("Ева: Фаза 2 (доля)", 0.0, 1.0, 0.0, 0.05)
    else:
        noise_p = st.slider("Шум на CX", 0.0, 0.30, 0.0, 0.01)
        eve_q = st.slider("Перехват Евы", 0.0, 1.0, 0.0, 0.05)

    # ---- Скрытые параметры ----
    with st.expander("🛠 Дополнительные параметры", expanded=False):
        phase1_ratio, bob_mismatch, eve_k1, eve_ber = 0.4, 0.0, False, 0.0
        s_thresh = 2.0
        p_verify, qber_thresh = 0.15, 0.11
        k_val, z_u, z_gamma = 1.5, 5.0, 5.0
        
        if protocol == "hybrid":
            st.markdown("**Гибридный протокол**")
            phase1_ratio = st.slider("Доля фазы 1", 0.1, 0.9, 0.4, 0.05)
            bob_mismatch = st.slider("Рассогласование у Боба", 0.0, 0.2, 0.0, 0.01)
            eve_k1 = st.checkbox("Ева знает K1 для фазы 2", value=False)
            if eve_k1:
                eve_ber = st.slider("BER знания K1 у Евы", 0.0, 0.5, 0.0, 0.05)
            
        if protocol in ["e91_basic", "e91_alt"]:
            st.markdown("**E91**")
            s_thresh = st.slider("Порог S (безопасность)", 1.5, 2.5, 2.0, 0.05)

        if protocol.startswith("bbm92"):
            st.markdown("**BBM92**")
            if protocol == "bbm92_plain":
                qber_thresh = st.slider("Порог QBER", 0.05, 0.20, 0.11, 0.01)
            else:
                p_verify = st.slider("Доля верификационных базисов (p)", 0.01, 0.5, 0.15, 0.01)
                qber_thresh = st.slider("Порог QBER", 0.05, 0.20, 0.11, 0.01)
                k_val = st.slider("Коэффициент k (для de)", 1.0, 3.0, 1.5, 0.1)
                z_u = st.slider("Порог z_u (для |E|)", 1.0, 10.0, 5.0, 0.5)
                z_gamma = st.slider("Порог z_gamma", 1.0, 10.0, 5.0, 0.5)

        st.markdown("**Согласование**")
        frame_size = st.select_slider("Размер кадра итогового согласования", [16, 32, 64, 128, 256, 512, 1024, 2048], value=1024)
        if protocol == "hybrid":
            frame_size_p1 = st.select_slider("Размер кадра Фаза 1", [8, 16, 32, 64, 128, 256, 512], value=16)
        success_prob = st.slider("Вероятность успеха кадра", 0.5, 1.0, 0.9, 0.05)
        efficiency = st.slider("Эффективность утечки", 1.0, 1.5, 1.1, 0.05)
        pa_loss = st.slider("Потеря при усилении секретности", 0.0, 0.5, 0.1, 0.05)

    st.divider()
    force_continue = st.checkbox("force_continue", value=True)
    run = st.button("🚀 Запустить", type="primary", use_container_width=True)

# ---- Основная область ----
if run:
    with st.spinner("Выполняем симуляцию..."):
        kwargs = {
            "phase1_ratio": phase1_ratio,
            "bob_mismatch_prob": bob_mismatch,
            "eve_uses_k1_phase2": eve_k1,
            "eve_k1_ber": eve_ber,
            "p": p_verify,
            "qber_threshold": qber_thresh,
            "k": k_val,
            "z_u": z_u,
            "z_gamma": z_gamma,
            "frame_size": frame_size,
            "frame_size_p1": frame_size_p1,
            "success_prob": success_prob,
            "efficiency": efficiency,
            "pa_entropy_loss": pa_loss,
        }
        
        if protocol == "hybrid":
            kwargs["noise_p1"] = noise_p1
            kwargs["noise_p2"] = noise_p2
            kwargs["eve_p1"] = eve_p1
            kwargs["eve_p2"] = eve_p2
        
        r = run_unified(
            protocol, 
            num_runs=num_runs, 
            num_pairs=num_pairs,
            noise_p=noise_p, 
            eve_q=eve_q, 
            s_threshold=s_thresh,
            force_continue=force_continue,
            **kwargs
        )

    st.subheader("Результаты симуляции")
    col1, col2, col3, col4 = st.columns(4)
    
    if protocol == "bbm92_plain":
        col1.metric("Параметр S", "N/A")
    elif r['S_mean'] < 0:
        col1.metric("Параметр S", f"{r['S_mean']:.3f}", f"|S| = {abs(r['S_mean']):.3f}", delta_color="off")
    else:
        col1.metric("Параметр S", f"{r['S_mean']:.3f} ± {r['S_std']:.3f}")
        
    col2.metric("QBER", f"{r['qber_mean']*100:.2f}%")
    col3.metric("Ключ (PA)", f"{r['key_after_pa_mean']:.0f} бит")
    col4.metric("Успешных", f"{r['success_count']}/{r['num_runs']}")

    with st.expander("📄 Полный текстовый отчёт", expanded=True):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            print_unified_report(protocol, r)
        st.text(buf.getvalue())