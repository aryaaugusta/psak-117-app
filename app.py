import streamlit as st
from src.data_loader import load_psak117_data
from src.calculator import calculate_bel, calculate_ra_csm, generate_movement, generate_cashflow_projection, generate_cashflow_projection2
from src.utils import format_idr, format_date_columns

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

st.sidebar.subheader("Parameter Inflasi & PAD")
pad_mortality_input = st.sidebar.number_input("PAD Mortality (%)", min_value=0.0, max_value=100.0, value=0.0) / 100
pad_lapse_input = st.sidebar.number_input("PAD Lapse (%)", min_value=0.0, max_value=100.0, value=0.0) / 100
pad_expense_input = st.sidebar.number_input("PAD Expense (%)", min_value=0.0, max_value=100.0, value=0.0) / 100
monthly_inflation_input = st.sidebar.number_input("Inflasi Bulanan (%)", value=0.21) / 100 # Default 0.2% sesuai contoh 1.002

if uploaded_file is not None:
    with st.spinner("Memotong dan memisahkan sheet secara vertikal & blok..."):
        data_bundle = load_psak117_data(uploaded_file)
        
    if not data_bundle["status"]:
        st.error(data_bundle["message"])
    else:
        st.success(data_bundle["message"])
        
        df_header = data_bundle["header"]
        df_gmm = data_bundle["template_gmm"]
        df_detail = data_bundle["detail"]
        
        tab_input, tab_bel, tab_ra_csm, tab_movement = st.tabs([
            "📁 Data Input", 
            "📈 Hasil Kalkulasi BEL", 
            "🛡️ Saldo RA & CSM", 
            "🔄 Liability Movement"
        ])
        
        with tab_input:
            st.subheader("1. Data Input - Header (Bagian Atas)")
            st.dataframe(df_header, use_container_width=True)
            # st.markdown("---")
            
            # col_gmm, col_asumsi = st.columns([1.5, 1])
            # with col_gmm:
            st.subheader("2. Template GMM (Bagian Bawah)")
            st.dataframe(df_gmm, use_container_width=True)
            # st.markdown("---")

            st.subheader("3. Data Input - Detail")
            st.dataframe(df_detail, use_container_width=True)       
                
            # with col_asumsi:
            st.subheader("4. Asumsi Aktuaria")
                
            # Memecah tampilan menjadi beberapa kotak drop-down
            with st.expander("Tabel Mortalita (TMI)", expanded=True):
                st.dataframe(data_bundle["asumsi_tmi"], use_container_width=True)
                    
            with st.expander("Rate IBPA"):
                st.dataframe(data_bundle["asumsi_ibpa"], use_container_width=True)

            with st.expander("Rate Inflasi"):
                df_inflasi_clean = format_date_columns(data_bundle["asumsi_inflasi"].copy())
                st.dataframe(df_inflasi_clean, use_container_width=True)
                    
            with st.expander("Lapse Rate - Monthly"):
                st.dataframe(data_bundle["asumsi_lapse_m"], use_container_width=True)

            with st.expander("Lapse Rate - Yearly"):
                st.dataframe(data_bundle["asumsi_lapse_y"], use_container_width=True)

            with st.expander("Lapse Rate - Monthly 2"):
                st.dataframe(data_bundle["asumsi_lapse_m2"], use_container_width=True)        
                
        # Hitung menggunakan tabel Rate IBPA spesifik
        df_bel_result = calculate_bel(df_gmm, data_bundle["asumsi_ibpa"]) 
        total_bel_val = df_bel_result["PV_Net_Cash_Flow"].sum()
        
        summary_metrics = calculate_ra_csm(df_header, total_bel_val, data_bundle["asumsi_ibpa"])
        df_movement_result = generate_movement(
            summary_metrics["Total_CSM"], 
            summary_metrics["Total_RA"], 
            summary_metrics["Total_BEL"]
        )
                
        # --- TAB BEL ---
        with tab_bel:

            def highlight_lapse_column(df):
                """
                Memberikan highlight kuning pada kolom Lapse dan mengatur format desimal
                hanya untuk kolom tertentu, sementara kolom lain tetap bersih.
                """
                # 1. Tentukan daftar kolom mata uang / nominal yang ingin ditampilkan tanpa desimal (.000000)
                # Sesuaikan dengan nama kolom yang ada di dataframe Anda
                cols_to_format_int = ['% Premi (PAD)', 'Fixed Cost', 'Fixed Cost (Dihitung CARE)', 
                                      'Monthly qx (ND)', 'Monthly qx (Term Life Joint)', 'Monthly qx (ND Joint)', 'Monthly qx (PA)',
                                      'Monthly qx (CI)', 'Monthly qx (TPD)', 'Monthly qx (CP)']

                # Kolom berformat 0 atau 1 (seperti Mature)
                cols_to_format_zero_one = ['Monthly qx (Mature)']

                # Kolom berformat 6 desimal (Rate & Decrement)
                cols_to_format_decimal = ['Survive beginning', 'Term Life', 'Lapse', 'Mature', 'Survive ending']
                
                styler = df.style.set_properties(
                    subset=['Monthly qx (Lapse)'], 
                    **{'background-color': '#FFF2CC', 'color': 'black', 'font-weight': 'bold'}
                ).format(
                    # Format 6 desimal khusus untuk kolom Lapse
                    "{:.6f}", subset=['Monthly qx (Lapse)']
                ).format(
                    # Format tanpa desimal (integer) untuk kolom nominal uang
                    "{:.0f}", subset=[c for c in cols_to_format_int if c in df.columns]
                ).format(
                    # Format integer biasa untuk kolom Mature (0 atau 1)
                    "{:.0f}", subset=[c for c in cols_to_format_zero_one if c in df.columns]
                ).format(
                    "{:.6f}", subset=[c for c in cols_to_format_decimal if c in df.columns]
                )
                
                return styler

            # df_bel_projection_styled = highlight_lapse_column(df_bel_result)
            st.subheader("Perhitungan Proyeksi Best Estimate Liability (BEL) - Mata Uang IDR")
            # st.metric("Total BEL Terdiskonto (Global)", format_idr(total_bel_val))
            st.dataframe(df_bel_result, use_container_width=True)

            # st.subheader("📋 Proyeksi Arus Kas Bulanan (Cash Flow)")
            st.markdown("---")

            df_proyeksi = generate_cashflow_projection2(
                df_header=df_header,
                df_detail=df_detail, 
                pad_expense=pad_expense_input,
                monthly_inflation=monthly_inflation_input,
                asumsi_inflasi=data_bundle["asumsi_inflasi"],
                df_tmi=data_bundle["asumsi_tmi"],
                asumsi_lapse_monthly=data_bundle["asumsi_lapse_m2"],
                pad_mortality=pad_mortality_input,
                pad_lapse=pad_lapse_input
            )

            # Menampilkan tabel
            df_proyeksi.index += 1
            df_proyeksi_styled = highlight_lapse_column(df_proyeksi)
            st.dataframe(df_proyeksi_styled, use_container_width=True)
            
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