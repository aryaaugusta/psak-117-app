import streamlit as st
import io
from src.data_loader import load_psak117_data
from src.calculator import calculate_bel, generate_movement, generate_racsm_projection, get_discount_rate_ibpa, generate_bel_projection
from src.utils import format_idr, format_date_columns
import pandas as pd

# 1. Konfigurasi Halaman Streamlit
st.set_page_config(
    page_title="Kalkulator Engine PSAK 117",
    page_icon="📊",
    layout="wide"
)

st.title("📊 PSAK 117 Actuarial Valuation Engine (GMM)")
# st.caption("Aplikasi Perhitungan Best Estimate Liability, Risk Adjustment, dan CSM menggunakan Streamlit & Python")

# 2. Sidebar untuk Unggah Berkas
st.sidebar.header("Unduh & Unggah Data")
uploaded_file = st.sidebar.file_uploader("Unggah File Sampel Perhitungan (.xlsx / .xlsm)", type=["xlsx", "xlsm"])

st.sidebar.subheader("Parameter Inflasi & PAD")
pad_mortality_input = st.sidebar.number_input("PAD Mortality (%)", min_value=0.0, max_value=100.0, value=0.0) / 100
pad_lapse_input = st.sidebar.number_input("PAD Lapse (%)", min_value=0.0, max_value=100.0, value=0.0) / 100
pad_expense_input = st.sidebar.number_input("PAD Expense (%)", min_value=0.0, max_value=100.0, value=0.0) / 100
monthly_inflation_input = st.sidebar.number_input("Inflasi Bulanan (%)", value=0.21) / 100 # Default 0.2% sesuai contoh 1.002

st.sidebar.subheader("Parameter Asumsi RA CSM")
# Input PAD BEL dalam bentuk persen (misal: diisi 5 artinya 5%)
pad_lapse_percent = st.sidebar.number_input("PAD Lapse RA CSM (%)", min_value=-100.0, max_value=100.0, value=-15.0, step=0.1, format="%.2f")
pad_lapse_racsm = pad_lapse_percent / 100.0

# Input PAD RA CSM dalam bentuk persen
pad_racsm_percent = st.sidebar.number_input("PAD Expense RA CSM (%)", min_value=-100.0, max_value=100.0, value=5.0, step=0.1, format="%.2f")
pad_expense_racsm = pad_racsm_percent / 100.0

# Input Inflasi RA CSM
inflation_racsm_percent = st.sidebar.number_input("Monthly Inflation RA CSM (%)", min_value=-100.0, max_value=100.0, value=0.21, step=0.01, format="%.2f")
monthly_inflation_racsm = inflation_racsm_percent / 100.0

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

        # 1. Hitung Discount Rate berdasarkan baris pertama data input (asumsi untuk seluruh polis)
        # Kita ambil baris pertama dari df_detail sebagai referensi untuk input global
        first_row = df_header.iloc[0]
        discount_rate_year = get_discount_rate_ibpa(first_row, data_bundle["asumsi_ibpa"])
        discount_rate_monthly = (1 + discount_rate_year) ** (1 / 12) - 1
        # print(f"FIRST ROW: {first_row}")
        # print(f"DISCOUNT RATE YEAR: {discount_rate_year}")
        # print(f"DISCOUNT RATE PER MONTH: {discount_rate_monthly}")

        # 2. Perhitungan Suku Bunga Bonus (80% dari discount rate)
        bonus_rate_year = discount_rate_year * 0.80
        bonus_rate_monthly = (1 + bonus_rate_year) ** (1 / 12) - 1

        st.sidebar.subheader("Discount Rate (Tingkat Diskonto)")

        # 2. Tampilkan sebagai read-only input
        col1, col2 = st.columns(2)
        with col1:
            st.sidebar.text_input(
                "Discount Rate (Year)", 
                value=f"{discount_rate_year:.2%}", 
                disabled=True, 
                help="Diambil otomatis dari Rate IBPA"
            )
        with col2:
            st.sidebar.text_input(
                "Discount Rate (Monthly)", 
                value=f"{discount_rate_monthly:.4%}", 
                disabled=True, 
                help="Dihitung dari Discount Rate Year"
        )

        # st.sidebar.markdown("---")
        st.sidebar.subheader("Bonus Discount Rate (Tingkat Diskonto Bonus)")

        # 2. Tampilkan sebagai read-only input
        col3, col4 = st.sidebar.columns(2)
        with col3:
            st.sidebar.text_input(
                "Discount Rate Bonus (Year)", 
                value=f"{bonus_rate_year:.2%}", 
                disabled=True, 
                help=f"Dihitung 80% dari Current Discount Rate"
            )
        with col4:
            st.sidebar.text_input(
                "Discount Rate Bonus(Monthly)", 
                value=f"{bonus_rate_monthly:.4%}", 
                disabled=True, 
                help="Dihitung dari Suku Bunga Bonus Tahunan"
        )
        
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

            def format_ibpa_table(df_ibpa):
                """
                Memformat tabel Rate IBPA:
                - Kolom pertama (Tenor) dibiarkan tampil normal (misal: 0.08, 1, 2, dst.)
                - Kolom rate di sebelah kanannya diformat menjadi persentase (%)
                """
                # 1. Identifikasi nama kolom pertama (biasanya 'Tenor' atau kolom pertama dataframe)
                col_tenor = df_ibpa.columns[0]
                
                # 2. Ambil sisa kolom rate di sebelah kanan
                cols_to_percentage = [col for col in df_ibpa.columns if col != col_tenor]
                
                # 3. Buat fungsi khusus untuk menampilkan kolom tenor apa adanya (agar nilai 0.08 tidak berubah)
                def format_tenor(val):
                    return str(val) if pd.notnotl(val) else ""

                styler = df_ibpa.style.format(
                    # Format persentase hanya untuk kolom-kolom rate
                    "{:.2%}", subset=cols_to_percentage
                ).format(
                    # Pastikan kolom tenor mempertahankan nilai aslinya tanpa format pengali persen
                    lambda x: f"{x:g}" if isinstance(x, (int, float)) else str(x), 
                    subset=[col_tenor]
                )
                return styler

            ibpa_styled = format_ibpa_table(data_bundle["asumsi_ibpa"])
                    
            with st.expander("Rate IBPA"):
                st.dataframe(ibpa_styled, use_container_width=True)

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
        
        # summary_metrics = calculate_ra_csm(df_header, total_bel_val, data_bundle["asumsi_ibpa"])
        # df_movement_result = generate_movement(
        #     summary_metrics["Total_CSM"], 
        #     summary_metrics["Total_RA"], 
        #     summary_metrics["Total_BEL"]
        # )
                
        # --- TAB BEL ---
        with tab_bel:

            def highlight_lapse_column(df):
                """
                Memberikan highlight kuning pada kolom Lapse dan mengatur format desimal
                hanya untuk kolom tertentu, sementara kolom lain tetap bersih.
                """
                # 1. Tentukan daftar kolom mata uang / nominal yang ingin ditampilkan tanpa desimal (.000000)
                # Sesuaikan dengan nama kolom yang ada di dataframe Anda
                cols_to_format_int = ['Premi', 'Komisi', 'Biaya Akuisisi', '% Premi (PAD)', 'Fixed Cost', 'Fixed Cost (Dihitung CARE)', 
                                      'Monthly qx (ND)', 'Monthly qx (Term Life Joint)', 'Monthly qx (ND Joint)', 'Monthly qx (PA)',
                                      'Monthly qx (CI)', 'Monthly qx (TPD)', 'Monthly qx (CP)','Term Life (BD - Benefit)', 'ND (Benefit)', 
                                      'Akumulasi Bonus (BD - Benefit)',"Term Life (After)", "ND (After)", "Joint Term Life (After)", "Joint ND (After)",
                                      'PA (After)', 'PV Death (After)', 'CI (After)', 'TPD (After)', 'CP (After)', 'Surrender (SB - Benefit)',
                                      "Surrender (After)", "Tahapan (After)", "Maturity (After)", "Total Future Benefits (Claim)", "Surrender (Refund)",
                                      "Komisi (After)", "Biaya Akuisisi (After)", "% Premi (After)", "Fixed Cost (After)", "Total Future Expenses 1", "Total Future Expenses 2", "Future Premiums",
                                      "PV Future Benefits (Claim)","PV Surrender (Refund)", "PV Future Komisi", "PV Future Biaya Akuisisi (Other Expense)", "PV Future % Premi", 
                                      "PV Future Fixed Cost", "PV Future Expenses 1", "PV Future Expenses 2", "PV Future Premiums",
                                      "BEL", "BEL Per Unit", "BEL Beginning", "BEL Premium", "BEL Commission", "BEL Expense", "BEL Other Expense", "BEL Claim", 
                                      "BEL Surrender", "Unwind", "Inc (Dec) of BEL", "BEL Ending", "Selisih"]

                # Kolom berformat 0 atau 1 (seperti Mature)
                cols_to_format_zero_one = ['Monthly qx (Mature)']

                # Kolom berformat 6 desimal (Rate & Decrement)
                cols_to_format_decimal = ['Survive beginning', 'Term Life', 'Lapse', 'Mature', 'Survive ending', 'ND', 
                                          'Term Life Joint', 'ND Joint', 'PA', 'CI', 'TPD', 'CP',]

                # Fungsi kustom untuk format angka ribuan dengan titik (.) ala Indonesia
                def format_idr_thousand(val):
                    if pd.isna(val):
                        return "-"
                    try:
                        return f"{int(val):,}".replace(",", ".")
                    except:
                        return val
                
                styler = df.style.set_properties(
                    subset=['Monthly qx (Lapse)'], 
                    **{'background-color': '#FFF2CC', 'color': 'black', 'font-weight': 'bold'}
                ).format(
                    # Format 6 desimal khusus untuk kolom Lapse
                    "{:.6f}", subset=['Monthly qx (Lapse)']
                ).format(
                    # Format tanpa desimal (integer) untuk kolom nominal uang
                    format_idr_thousand, subset=[c for c in cols_to_format_int if c in df.columns]
                ).format(
                    # Format integer biasa untuk kolom Mature (0 atau 1)
                    "{:.0f}", subset=[c for c in cols_to_format_zero_one if c in df.columns]
                ).format(
                    "{:.6f}", subset=[c for c in cols_to_format_decimal if c in df.columns]
                )
                
                return styler

            # df_bel_projection_styled = highlight_lapse_column(df_bel_result)
            st.subheader("Perhitungan Proyeksi Best Estimate Liability (BEL) - Mata Uang IDR")
            
            # st.subheader("📋 Proyeksi Arus Kas Bulanan (Cash Flow)")
            

            df_proyeksi = generate_bel_projection(
                df_header=df_header,
                df_detail=df_detail, 
                pad_expense=pad_expense_input,
                monthly_inflation=monthly_inflation_input,
                asumsi_inflasi=data_bundle["asumsi_inflasi"],
                df_tmi=data_bundle["asumsi_tmi"],
                asumsi_lapse_monthly=data_bundle["asumsi_lapse_m2"],
                pad_mortality=pad_mortality_input,
                pad_lapse=pad_lapse_input,
                bonus_rate_monthly=bonus_rate_monthly,
                discount_rate_monthly=discount_rate_monthly
            )

            # Ambil nilai BEL awal (bulan ke-1) dari df_proyeksi
            initial_bel_val = df_proyeksi["BEL"].iloc[0] if not df_proyeksi.empty else 0.0
            
            st.metric("Total BEL Terdiskonto", format_idr(initial_bel_val))
            st.dataframe(df_bel_result, use_container_width=True)
            st.markdown("---")
            # Menampilkan tabel
            df_proyeksi.index += 1
            df_proyeksi_styled = highlight_lapse_column(df_proyeksi)
            st.dataframe(df_proyeksi_styled, use_container_width=True)
            
        # --- TAB RA & CSM ---
        with tab_ra_csm:
            # st.subheader("Valuasi Saldo Awal Pemenuhan Kewajiban Kontrak (Insepsi)")
            st.subheader("Valuasi Saldo Awal")

            def highlight_lapse_column_racsm(df):
                """
                Memberikan highlight kuning pada kolom Lapse dan mengatur format desimal
                hanya untuk kolom tertentu, sementara kolom lain tetap bersih.
                """
                # 1. Tentukan daftar kolom mata uang / nominal yang ingin ditampilkan tanpa desimal (.000000)
                # Sesuaikan dengan nama kolom yang ada di dataframe Anda
                cols_to_format_int = ['Premi', 'Komisi', 'Biaya Akuisisi', '% Premi', 'Fixed Cost', 'Fixed Cost (Dihitung Care)', 
                                      'Monthly qx (ND)', 'Monthly qx (Term Life Joint)', 'Monthly qx (ND Joint)', 'Monthly qx (PA)',
                                      'Monthly qx (CI)', 'Monthly qx (TPD)', 'Monthly qx (CP)','Term Life (BD - Benefit)', 'ND (Benefit)', 
                                      'Akumulasi Bonus (BD - Benefit)',"Term Life (After)", "ND (After)", "Joint Term Life (After)", "Joint ND (After)",
                                      'PA (After)', 'PV Death (After)', 'CI (After)', 'TPD (After)', 'CP (After)', 'Surrender (SB - Benefit)',
                                      "Surrender (After)", "Tahapan (After)", "Maturity (After)", "Total Future Benefits (Claim)", "Surrender (Refund)",
                                      "Komisi (After)", "Biaya Akuisisi (After)", "% Premi (After)", "Fixed Cost (After)", "Total Future Expenses 1", "Total Future Expenses 2", "Future Premiums",
                                      "PV Future Benefits (Claim)","PV Surrender (Refund)", "PV Future Komisi", "PV Future Biaya Akuisisi (Other Expense)", "PV Future % Premi", 
                                      "PV Future Fixed Cost", "PV Future Expenses 1", "PV Future Expenses 2", "PV Future Premiums",
                                      "BEL", "BEL Per Unit", "BEL Beginning", "BEL Premium", "BEL Commission", "BEL Expense", "BEL Other Expense", "BEL Claim", 
                                      "BEL Surrender", "Unwind", "Inc (Dec) of BEL", "BEL Ending", "Selisih", "BEL+PAD", "RA", "RA Per Unit",
                                      "RA Beginning", "RA Interest Accrete", "RA Release", "RA Ending", "CSM Beginning", "CSM Unwind", "CSM Released", "CSM Ending"]

                # Kolom berformat 0 atau 1 (seperti Mature)
                cols_to_format_zero_one = ['Monthly qx (Mature)']

                # Kolom berformat 6 desimal (Rate & Decrement)
                cols_to_format_decimal = ['Survive beginning', 'Term Life', 'Lapse', 'Mature', 'Survive ending', 'ND', 
                                          'Term Life Joint', 'ND Joint', 'PA', 'CI', 'TPD', 'CP',]

                # Kolom berformat 0 atau 1 (seperti Mature)
                cols_to_format_percentage = ["%RA Release","% CSM Release"]

                # Fungsi kustom untuk format angka ribuan dengan titik (.) ala Indonesia
                def format_idr_thousand(val):
                    if pd.isna(val):
                        return "-"
                    try:
                        return f"{int(val):,}".replace(",", ".")
                    except:
                        return val
                
                styler = df.style.set_properties(
                    subset=['Monthly qx (Lapse)'], 
                    **{'background-color': '#FFF2CC', 'color': 'black', 'font-weight': 'bold'}
                ).format(
                    # Format 6 desimal khusus untuk kolom Lapse
                    "{:.6f}", subset=['Monthly qx (Lapse)']
                ).format(
                    # Format tanpa desimal (integer) untuk kolom nominal uang
                    format_idr_thousand, subset=[c for c in cols_to_format_int if c in df.columns]
                ).format(
                    # Format integer biasa untuk kolom Mature (0 atau 1)
                    "{:.0f}", subset=[c for c in cols_to_format_zero_one if c in df.columns]
                ).format(
                    "{:.6f}", subset=[c for c in cols_to_format_decimal if c in df.columns]
                ).format(
                    "{:.2%}", subset=[c for c in cols_to_format_percentage if c in df.columns]
                )
                
                return styler            

            df_racsm = generate_racsm_projection(
                df_header=df_header,
                df_detail=df_detail,
                pad_expense_racsm=pad_expense_racsm,
                monthly_inflation_racsm=monthly_inflation_racsm,
                asumsi_inflasi=data_bundle.get("asumsi_inflasi"),
                df_tmi=data_bundle.get("asumsi_tmi"),
                discount_rate_monthly=discount_rate_monthly,
                pad_lapse_racsm=pad_lapse_racsm,
                bonus_rate_monthly=bonus_rate_monthly,
                asumsi_lapse_monthly=data_bundle["asumsi_lapse_m2"],
                bel_master=df_proyeksi["BEL"]
            )

            # Ambil nilai saldo awal (bulan ke-1) dari df_racsm
            initial_bel = df_racsm["BEL+PAD"].iloc[0] if not df_racsm.empty else 0.0
            initial_ra = df_racsm["RA Beginning"].iloc[0] if not df_racsm.empty else 0.0
            initial_csm = df_racsm["CSM Beginning"].iloc[0] if not df_racsm.empty else 0.0

            # --- LOGIKA PENGECEKAN ONEROOUS YANG DISESUAIKAN ---
            # Kontrak disebut onerous jika nilai awal sebelum dibatasi 0 bernilai negatif
            raw_initial_csm = -initial_bel - initial_ra
            is_onerous = raw_initial_csm < 0

            if is_onerous:
                st.error("⚠️ Portofolio Kontrak berstatus Onerous (Rugi). Saldo awal CSM diatur menjadi Rp 0,00 dan rugi langsung diakui di P&L.")
            else:
                st.success("✨ Portofolio Kontrak Profitable. Keuntungan ditangguhkan ke dalam saldo CSM awal.")

            m1, m2, m3 = st.columns(3)
            m1.metric("BEL (Best Estimate Liability)", format_idr(initial_bel))
            m2.metric("RA (Risk Adjustment)", format_idr(initial_ra))
            m3.metric("CSM (Contractual Service Margin)", format_idr(initial_csm))

            # Menampilkan tabel
            df_racsm.index += 1
            df_proyeksi_styled = highlight_lapse_column_racsm(df_racsm)
            st.dataframe(df_proyeksi_styled, use_container_width=True)

        # --- TAB MOVEMENT ---
        with tab_movement:
            st.subheader("Tabel Pergerakan Saldo PSAK 117 (GMM)")

            # Ambil total nilai dari df_racsm yang sudah dikalkulasi
            total_bel_val = df_racsm["BEL+PAD"].iloc[0] if not df_racsm.empty else 0.0
            total_ra_val = df_racsm["RA Beginning"].iloc[0] if not df_racsm.empty else 0.0
            total_csm_val = df_racsm["CSM Beginning"].iloc[0] if not df_racsm.empty else 0.0

            df_movement_result = generate_movement(
                total_csm_val, 
                total_ra_val, 
                total_bel_val
            )

            # Siapkan data mentah yang sudah dibulatkan untuk file Excel
            df_export = df_movement_result.copy()
            for col in ["BEL (IDR)", "Risk Adjustment (IDR)", "CSM (IDR)"]:
                df_export[col] = df_export[col].apply(format_idr)

            st.table(df_export)

            # Buat buffer memori virtual untuk menyimpan file Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_export.to_excel(writer, index=False, sheet_name='Liability Movement')

                # Mengatur otomatis lebar kolom agar pas dan rapi sesuai isi teks
                worksheet = writer.sheets['Liability Movement']
                for i, col in enumerate(df_export.columns):
                    # Hitung panjang maksimum teks pada kolom tersebut
                    max_len = max(
                        df_export[col].astype(str).map(len).max(),
                        len(str(col))
                    )
                    # Tambahkan sedikit ruang ekstra agar tidak terlalu mepet
                    worksheet.set_column(i, i, max_len + 4)
            
            excel_data = output.getvalue()

            st.sidebar.markdown("---")
            st.sidebar.subheader("Ekspor Hasil Perhitungan")
            st.sidebar.download_button(
                label="📥 Unduh Data Pergerakan (Excel)",
                data=excel_data,
                file_name="PSAK117_GMM_Movement_Output.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

else:
    st.info("💡 Silakan unggah file template Excel kalkulasi aktuaria Anda pada panel sebelah kiri untuk memulai pemisahan tabel dan kalkulasi.")