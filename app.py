import streamlit as st
import pandas as pd
from src.data_loader import load_psak117_data
from src.calculator import calculate_bel, calculate_ra_csm, generate_movement
from src.utils import format_idr

# 1. Konfigurasi Halaman Streamlit
st.set_page_config(
    page_title="Kalkulator Engine PSAK 117",
    page_icon="📊",
    layout="wide"
)

st.title("📊 PSAK 117 Actuarial Valuation Engine (GMM)")
st.caption("Aplikasi Perhitungan Best Estimate Liability, Risk Adjustment, dan CSM menggunakan Streamlit & Python")

# 2. Sidebar untuk Unggah Berkas
st.sidebar.header("Unduh & Unggah Data")
uploaded_file = st.sidebar.file_uploader("Unggah File Sampel Perhitungan (.xlsx / .xlsm)", type=["xlsx", "xlsm"])

if uploaded_file is not None:
    # Menggunakan modul pemotongan vertikal dari data_loader.py
    with st.spinner("Memotong dan memisahkan sheet secara vertikal..."):
        data_bundle = load_psak117_data(uploaded_file)
        
    if not data_bundle["status"]:
        st.error(data_bundle["message"])
    else:
        st.success(data_bundle["message"])
        
        # Ekstrak seluruh tabel yang telah dipisah bersih oleh data_loader
        df_header = data_bundle["header"]
        df_gmm = data_bundle["template_gmm"]
        df_detail = data_bundle["detail"]
        df_asumsi = data_bundle["asumsi"]
        
        # Navigasi Tab Utama User Interface
        tab_input, tab_bel, tab_ra_csm, tab_movement = st.tabs([
            "📁 Data Input (Terpisah)", 
            "📈 Hasil Kalkulasi BEL", 
            "🛡️ Saldo RA & CSM", 
            "🔄 Liability Movement"
        ])
        
        # --- TAB INPUT: MENAMPILKAN TABEL YANG SUDAH DIPISAH ---
        with tab_input:
            st.subheader("1. Data Input - Header (Bagian Atas)")
            st.caption(f"Terstatus Bersih: Terdeteksi {df_header.shape[0]} baris data dan {df_header.shape[1]} kolom.")
            st.dataframe(df_header, use_container_width=True)
            
            st.markdown("---")
            
            col_gmm, col_asumsi = st.columns([2, 1])
            with col_gmm:
                st.subheader("2. Template GMM (Bagian Bawah)")
                if not df_gmm.empty:
                    st.caption(f"Terstatus Bersih: Terdeteksi {df_gmm.shape[0]} baris data dan {df_gmm.shape[1]} kolom.")
                    st.dataframe(df_gmm, use_container_width=True)
                else:
                    st.warning("Penanda 'TEMPLATE GMM' tidak ditemukan di dalam sheet.")
                    
            with col_asumsi:
                st.subheader("3. Asumsi Suku Bunga")
                st.dataframe(df_asumsi, use_container_width=True)
                
        # --- LOGIKA ENGINE KALKULATOR AKTUARTA (src/calculator.py) ---
        # Sesuai arahan Anda, perhitungan menggunakan data dari tabel TEMPLATE GMM (df_gmm)
        # dan dikalibrasi dalam mata uang IDR
        df_bel_result = calculate_bel(df_gmm, df_asumsi) 
        total_bel_val = df_bel_result["PV_Net_Cash_Flow"].sum()
        
        summary_metrics = calculate_ra_csm(df_header, total_bel_val, df_asumsi)
        df_movement_result = generate_movement(
            summary_metrics["Total_CSM"], 
            summary_metrics["Total_RA"], 
            summary_metrics["Total_BEL"]
        )
        
        # --- TAB BEL ---
        with tab_bel:
            st.subheader("Perhitungan Proyeksi Best Estimate Liability (BEL) - Mata Uang IDR")
            st.metric("Total BEL Terdiskonto (Global)", format_idr(total_bel_val))
            st.dataframe(df_bel_result, use_container_width=True)
            
        # --- TAB RA & CSM ---
        with tab_ra_csm:
            st.subheader("Valuasi Saldo Awal Pemenuhan Kewajiban Kontrak (Insepsi)")
            m1, m2, m3 = st.columns(3)
            m1.metric("BEL (Best Estimate Liability)", format_idr(summary_metrics["Total_BEL"]))
            m2.metric("RA (Risk Adjustment)", format_idr(summary_metrics["Total_RA"]))
            m3.metric("CSM (Contractual Service Margin)", format_idr(summary_metrics["Total_CSM"]))
            
            if summary_metrics["Is_Onerous"]:
                st.error("⚠️ Portofolio Kontrak berstatus Onerous (Rugi). Saldo awal CSM diatur menjadi Rp 0,00 dan rugi langsung diakui di P&L.")
            else:
                st.success("✨ Portofolio Kontrak Profitable. Keuntungan ditangguhkan ke dalam saldo CSM awal.")
                
        # --- TAB MOVEMENT ---
        with tab_movement:
            st.subheader("Tabel Pergerakan Saldo PSAK 117 (GMM Roll-Forward)")
            
            # Memformat angka pada dataframe movement agar memunculkan satuan IDR yang rapi
            df_move_formatted = df_movement_result.copy()
            for col in ["BEL (IDR)", "Risk Adjustment (IDR)", "CSM (IDR)"]:
                df_move_formatted[col] = df_move_formatted[col].apply(format_idr)
                
            st.table(df_move_formatted)
            
            # Tombol unduh untuk keperluan laporan aktuaria lanjutan
            st.sidebar.markdown("---")
            st.sidebar.subheader("Ekspor Hasil Perhitungan")
            st.sidebar.download_button(
                label="📥 Unduh Data Pergerakan (CSV)",
                data=df_movement_result.to_csv(index=False),
                file_name="PSAK117_GMM_Movement_Output.csv",
                mime="text/csv"
            )

else:
    st.info("💡 Silakan unggah file template Excel kalkulasi aktuaria Anda pada panel sebelah kiri untuk memulai pemisahan tabel dan kalkulasi.")