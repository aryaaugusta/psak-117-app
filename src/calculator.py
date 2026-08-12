import pandas as pd
import numpy as np

def calculate_bel(df_detail, df_asumsi_ibpa):
    """
    Menghitung Best Estimate Liability (BEL) secara dinamis dan aman dari KeyError.
    Menggunakan tabel Rate IBPA sebagai referensi Suku Bunga Diskonto.
    """
    df_bel = df_detail.copy()
    
    # 1. Deteksi nama kolom tahun secara dinamis di data detail (GMM Template)
    kolom_tahun = None
    target_names = ["tahun", "t", "year", "periode", "projection_year", "projection year"]
    
    for col in df_bel.columns:
        if str(col).lower().strip() in target_names:
            kolom_tahun = col
            break
            
    # Jika tidak ketemu, default menggunakan kolom pertama
    if not kolom_tahun:
        kolom_tahun = df_bel.columns[0] 

    # 2. Ambil discount rate dari tabel asumsi IBPA secara dinamis
    kolom_tahun_asumsi = None
    kolom_rate = None
    
    if not df_asumsi_ibpa.empty:
        for col in df_asumsi_ibpa.columns:
            col_str = str(col).lower().strip()
            if col_str in target_names:
                kolom_tahun_asumsi = col
            if any(k in col_str for k in ["rate", "bunga", "yield", "discount", "ibpa"]):
                kolom_rate = col

    # 3. Proses Gabung Data Asumsi & Detail berdasarkan Tahun
    if kolom_tahun_asumsi and kolom_rate:
        df_asumsi_temp = df_asumsi_ibpa[[kolom_tahun_asumsi, kolom_rate]].copy()
        df_asumsi_temp.columns = ["Tahun_Join", "Discount_Rate"]
        
        # Samakan tipe data (string) agar Pandas tidak error saat proses Merge
        df_bel[kolom_tahun] = df_bel[kolom_tahun].astype(str).str.strip()
        df_asumsi_temp["Tahun_Join"] = df_asumsi_temp["Tahun_Join"].astype(str).str.strip()
        
        df_bel = pd.merge(df_bel, df_asumsi_temp, left_on=kolom_tahun, right_on="Tahun_Join", how="left")
        df_bel.drop(columns=["Tahun_Join"], errors="ignore", inplace=True)
        
        # Ubah nilai rate menjadi numerik, isi dengan default 5% (0.05) jika kosong/invalid
        df_bel["Discount_Rate"] = pd.to_numeric(df_bel["Discount_Rate"], errors="coerce").fillna(0.05)
    else:
        # Fallback jika struktur sheet ASUMSI IBPA tidak terbaca
        df_bel["Discount_Rate"] = 0.05 
        
    # 4. Hitung Faktor Diskonto: 1 / (1 + r)^t
    # Ekstrak kembali nilai tahun menjadi angka untuk perhitungan eksponensial (pangkat)
    df_bel["Tahun_Numerik"] = pd.to_numeric(df_bel[kolom_tahun], errors="coerce").fillna(1)
    df_bel["Discount_Factor"] = 1 / ((1 + df_bel["Discount_Rate"]) ** df_bel["Tahun_Numerik"])
    
    # 5. Hitung Arus Kas Bersih
    # Deteksi kolom secara cerdas berdasarkan kata kunci (Inflow/Premium vs Outflow/Klaim)
    inflow_col = next((c for c in df_bel.columns if any(k in str(c).lower() for k in ["inflow", "premium", "premi", "masuk"])), None)
    outflow_col = next((c for c in df_bel.columns if any(k in str(c).lower() for k in ["outflow", "claim", "klaim", "keluar", "benefit", "expense"])), None)
    
    cash_in = pd.to_numeric(df_bel[inflow_col], errors="coerce").fillna(0) if inflow_col else 0
    cash_out = pd.to_numeric(df_bel[outflow_col], errors="coerce").fillna(0) if outflow_col else 0
    
    # Arus Kas Bersih (Net Cash Flow)
    df_bel["Net_Cash_Flow"] = cash_in - cash_out
    
    # Present Value (PV) dari Net Cash Flow untuk membentuk BEL
    df_bel["PV_Net_Cash_Flow"] = df_bel["Net_Cash_Flow"] * df_bel["Discount_Factor"]
    
    return df_bel

def calculate_ra_csm(df_header, total_bel, df_asumsi_ibpa):
    """
    Menghitung Risk Adjustment (RA) dan Contractual Service Margin (CSM) pada masa awal (Insepsi).
    """
    # Secara default menggunakan 5% dari BEL jika tidak ada margin risiko spesifik di asumsi
    ra_percentage = 0.05 
    
    # Cari nilai total premi di tabel Header untuk dasar perbandingan (jika diperlukan)
    premium_col = next((c for c in df_header.columns if "premium" in str(c).lower() or "premi" in str(c).lower()), None)
    if premium_col:
        total_premium = pd.to_numeric(df_header[premium_col], errors="coerce").sum()
    else:
        total_premium = 0
    
    # Perhitungan Risk Adjustment
    total_ra = total_bel * ra_percentage
    
    # Perhitungan CSM (Asumsi dasar: Sisa PV Net Cash Flow yang profit dikurangi RA)
    # Jika hasilnya negatif, kontrak dianggap Onerous (Rugi) dan CSM menjadi 0.
    net_fulfillment_cf = total_bel - total_ra
    
    if net_fulfillment_cf > 0:
        total_csm = net_fulfillment_cf
        is_onerous = False
    else:
        total_csm = 0
        is_onerous = True
        
    return {
        "Total_BEL": total_bel,
        "Total_RA": total_ra,
        "Total_CSM": total_csm,
        "Is_Onerous": is_onerous
    }

def generate_movement(initial_csm, initial_ra, initial_bel):
    """
    Membuat data pergerakan (Roll-Forward Movement) dari saldo awal hingga saldo akhir.
    Struktur kolom dinormalkan menggunakan format IDR.
    """
    # Contoh simulasi persentase pergerakan untuk membentuk template Roll-Forward
    movement_data = {
        "Komponen Roll-Forward": [
            "Saldo Awal (Opening Balance)",
            "Efek Bisnis Baru (New Business Contracts)",
            "Pembalikan Bunga (Interest Accreted)",
            "Perubahan Asumsi Cash Flow Masa Depan",
            "Rilis ke Pendapatan (Fulfillment / Release to P&L)",
            "Saldo Akhir (Closing Balance)"
        ],
        "BEL (IDR)": [initial_bel, initial_bel * 0.1, initial_bel * 0.04, -5000000, -initial_bel * 0.12, 0],
        "Risk Adjustment (IDR)": [initial_ra, initial_ra * 0.1, 0, 0, -initial_ra * 0.15, 0],
        "CSM (IDR)": [initial_csm, initial_csm * 0.05, initial_csm * 0.04, 0, -initial_csm * 0.1, 0]
    }
    
    df_move = pd.DataFrame(movement_data)
    
    # Hitung Saldo Akhir (Closing Balance) secara dinamis dengan menjumlahkan baris 0 s/d 4
    for col in ["BEL (IDR)", "Risk Adjustment (IDR)", "CSM (IDR)"]:
        opening = df_move.loc[0, col]
        changes = df_move.loc[1:4, col].sum()
        df_move.loc[5, col] = opening + changes
        
    return df_move

def generate_cashflow_projection(duration_years, premium, komisi, biaya_akuisisi, pad_expense, fixed_cost_base, df_detail):
    """
    Menghasilkan tabel proyeksi arus kas bulanan.
    """
    data = []
    total_months = duration_years * 12
    
    # Inisialisasi faktor pertumbuhan untuk 'Fixed Cost_1'
    growth_factor = 1.002 # Contoh pertumbuhan bulanan

    # Mengambil nilai PCT_Premi dari sheet Detail
    pct_premi = df_detail['Biaya_Pemeliharaan_Polis_PCT_Premi'].iloc[0]

    # Mengambil nilai Fixed Cost dari sheet Detail
    fixed_cost = df_detail['Biaya_Pemeliharaan_Polis_Fixed_Cost'].iloc[0]

    # Rumus Excel: Biaya_Pemeliharaan_Polis_PCT_Premi * (1 + PAD Expense)
    pad_value = pct_premi * (1 + pad_expense)

    # Rumus Excel: Biaya_Pemeliharaan_Polis_Fixed_Cost * (1 + PAD Expense)
    fixed_cost_value = fixed_cost * (1 + fixed_cost_base)
    print(f"FIXED COST VALUE: {fixed_cost_value} | FIXED COST BASE: {fixed_cost_base} | FIXED COST: {fixed_cost}")
    
    for month in range(1, total_months + 1):
        tahun = (month - 1) // 12 + 1
        
        # Premi & Biaya hanya muncul di bulan ke-1 (Tahun 1, Bulan 1)
        is_first_month = (month == 1)
        
        row = {
            "Tahun Polis": tahun,
            "Bulan ke-": month,
            "Premi": premium if is_first_month else 0,
            "Komisi": komisi if is_first_month else 0,
            "Biaya Akuisisi": biaya_akuisisi if is_first_month else 0,
            "% Premi (PAD)": pad_value if is_first_month else 0,
            "Fixed Cost": fixed_cost_value if is_first_month else 0,
            "Fixed Cost_1": fixed_cost_base * (growth_factor ** (month - 1))
        }
        data.append(row)
    
    return pd.DataFrame(data)

def get_inflation_rate(tanggal_mulai, asumsi_inflasi):
    """
    Mencari inflasi tahunan dari tabel asumsi berdasarkan logika Excel.
    """
    tanggal = pd.to_datetime(tanggal_mulai)
    tahun_polis = tanggal.year
    
    # Konversi kolom pertama asumsi inflasi menjadi datetime/integer untuk perbandingan
    # Asumsi kolom ke-0 adalah Tahun/Tanggal, kolom ke-1 adalah Rate Inflasi
    col_kunci = asumsi_inflasi.columns[0]
    col_rate = asumsi_inflasi.columns[1]
    
    if tahun_polis > 2023:
        # VLOOKUP berdasarkan EOMONTH(tanggal, 0)
        target = tanggal + pd.offsets.MonthEnd(0)
        match = asumsi_inflasi[asumsi_inflasi[col_kunci] == target]
    else:
        # VLOOKUP berdasarkan MAX(tahun, 2011)
        target_tahun = max(tahun_polis, 2011)
        match = asumsi_inflasi[asumsi_inflasi[col_kunci] == target_tahun]
        
    if not match.empty:
        return match.iloc[0, 1] # Mengambil nilai rate
    return 0.0


def generate_cashflow_projection2(df_header, df_detail, pad_expense=0.0, monthly_inflation=0.0, 
                                  asumsi_inflasi=None, df_tmi=None, pad_mortality=0.0, 
                                  total_nd_global=0.0, total_joint_term_life_global=0.0, total_nd_joint_global=0.0,
                                  total_pa_global=0.0, total_ci_global=0.0, total_tpd_global=0.0, total_cp_global=0.0,
                                  asumsi_lapse_monthly=None, pad_lapse=0.0):
    # 1. Gabungkan (Merge) df_detail dan df_header agar panjang barisnya konsisten
    # Pastikan ada kolom kunci yang sama, misal 'Policy_ID' atau 'A_PolicyNo'. 
    # Jika struktur baris sudah sejajar persis, bisa langsung di-assign.
    if 'A_PolicyNo' in df_detail.columns and 'A_PolicyNo' in df_header.columns:
        df = pd.merge(df_detail, df_header, on='A_PolicyNo', how='left', suffixes=('', '_header'))
    else:
        # Jika tidak ada key, kita lakukan join berdampingan (pastikan urutan baris sama)
        df = pd.concat([df_detail.reset_index(drop=True), df_header.reset_index(drop=True)], axis=1)

    # 2. Hitung PAD Expense & Fixed Cost Value
    pct_premi = df['Biaya_Pemeliharaan_Polis_PCT_Premi']
    fixed_cost = df['Biaya_Pemeliharaan_Polis_Fixed_Cost']

    # MPP
    # mpp = df['Masa_Pembayaran_Premi_Dasar']
    
    pad_value = pct_premi * (1 + pad_expense)
    fixed_cost_value = fixed_cost * (1 + pad_expense)

    # 3. Hitung Inflasi Tahunan & Bulanan per baris
    if asumsi_inflasi is not None and 'Effective' in df.columns:
        df['Inflasi_Tahunan'] = df['Effective'].apply(lambda x: get_inflation_rate(x, asumsi_inflasi))
        df['Inflasi_Bulanan'] = (1 + df['Inflasi_Tahunan']) ** (1/12) - 1
        # Gunakan inflasi bulanan aktual dari data jika ada, atau fallback ke parameter input UI
        eff_monthly_inflation = df['Inflasi_Bulanan']
    else:
        eff_monthly_inflation = monthly_inflation

    # 4. Lookup TMI (Mortality) per baris berdasarkan Usia Tertanggung
    def lookup_tmi(usia):
        if df_tmi is None:
            return 0.0
        match = df_tmi[df_tmi.iloc[:, 0] == usia]
        if not match.empty:
            return match.iloc[0, 4] # Mengambil kolom ke-5 (index 4)
        return 0.0

    def lookup_tmi_nd(usia):
        if df_tmi is None:
            return 0.0
        match = df_tmi[df_tmi.iloc[:, 0] == usia]
        if not match.empty:
            # VLOOKUP kolom ke-7 berarti index 6
            return match.iloc[0, 6] 
        return 0.0
    
    def lookup_tmi_term_life_joint(usia):
        if df_tmi is None:
            return 0.0
        match = df_tmi[df_tmi.iloc[:, 0] == usia]
        if not match.empty:
            # VLOOKUP kolom ke-9 berarti index 8
            return match.iloc[0, 8] 
        return 0.0

    def lookup_tmi_nd_joint(usia):
        if df_tmi is None:
            return 0.0
        match = df_tmi[df_tmi.iloc[:, 0] == usia]
        if not match.empty:
            # VLOOKUP kolom ke-11 berarti index 10
            return match.iloc[0, 10] 
        return 0.0

    def lookup_tmi_pa(usia):
        if df_tmi is None:
            return 0.0
        match = df_tmi[df_tmi.iloc[:, 0] == usia]
        if not match.empty:
            # VLOOKUP kolom ke-13 berarti index 12
            return match.iloc[0, 12] 
        return 0.0

    def lookup_tmi_ci(usia):
        if df_tmi is None:
                return 0.0
        match = df_tmi[df_tmi.iloc[:, 0] == usia]
        if not match.empty:
            # VLOOKUP kolom ke-15 berarti index 14
            return match.iloc[0, 14] 
        return 0.0

    def lookup_tmi_tpd(usia):
        if df_tmi is None:
                return 0.0
        match = df_tmi[df_tmi.iloc[:, 0] == usia]
        if not match.empty:
            # VLOOKUP kolom ke-17 berarti index 16
            return match.iloc[0, 16] 
        return 0.0

    def lookup_tmi_cp(usia):
        if df_tmi is None:
                return 0.0
        match = df_tmi[df_tmi.iloc[:, 0] == usia]
        if not match.empty:
            # VLOOKUP kolom ke-19 berarti index 18
            return match.iloc[0, 18] 
        return 0.0

    df['Base_qx'] = df['Usia_Tertanggung'].apply(lookup_tmi)

    # Cari nilai qx untuk ND dari TMI
    df['Base_qx_ND'] = df['Usia_Tertanggung'].apply(lookup_tmi_nd)

    # Cari nilai qx untuk Term Life Joint dari TMI
    df['Base_qx_Term_Life_Joint'] = df['Usia_Tertanggung'].apply(lookup_tmi_term_life_joint)

    # Cari nilai qx untuk ND Joint dari TMI
    df['Base_qx_ND_Joint'] = df['Usia_Tertanggung'].apply(lookup_tmi_nd_joint)

    # Cari nilai qx untuk PA dari TMI
    df['Base_qx_PA'] = df['Usia_Tertanggung'].apply(lookup_tmi_pa)

    # Cari nilai qx untuk CI dari TMI
    df['Base_qx_CI'] = df['Usia_Tertanggung'].apply(lookup_tmi_ci)

    # Cari nilai qx untuk TPD dari TMI
    df['Base_qx_TPD'] = df['Usia_Tertanggung'].apply(lookup_tmi_tpd)

    # Cari nilai qx untuk CP dari TMI
    df['Base_qx_CP'] = df['Usia_Tertanggung'].apply(lookup_tmi_cp)

    # 5. Logika Monthly qx (Term Life)
    # Pastikan Pol_Term_M minimal bernilai 1
    if 'Pol_Term_M' in df.columns:
        df['Pol_Term_M'] = df['Pol_Term_M'].apply(lambda x: max(1, int(x)) if pd.notnull(x) else 1)
    else:
        df['Pol_Term_M'] = df.get('Pol_Term_Y', 3) * 12

    bulan_ke = df['Bulan_Ke']
    masa_asuransi_bulan = df['Pol_Term_M']
    
    # Kondisi: (Bulan_Ke <= Pol_Term_M - 1) AND (Bulan_Ke <> 0)
    kondisi = (bulan_ke <= (masa_asuransi_bulan - 1)) & (bulan_ke != 0)
    
    df['Monthly_qx'] = np.where(kondisi, df['Base_qx'] * (1 + pad_mortality), 0.0)

    is_nd_total_zero = (total_nd_global == 0)
    is_term_life_joint_total_zero = (total_joint_term_life_global == 0)
    is_nd_joint_total_zero = (total_nd_joint_global == 0)
    is_pa_total_zero = (total_pa_global == 0)
    is_ci_total_zero = (total_ci_global == 0)
    is_tpd_total_zero = (total_tpd_global == 0)
    is_cp_total_zero = (total_cp_global == 0)

    df['Monthly_qx_ND'] = np.where(is_nd_total_zero, 0.0, np.where(kondisi, df['Base_qx_ND'] * (1 + pad_mortality), 0.0))

    df['Monthly_qx_Term_Life_Joint'] = np.where(is_term_life_joint_total_zero, 0.0, np.where(kondisi, df['Base_qx_Term_Life_Joint'] * (1 + pad_mortality), 0.0))

    df['Monthly_qx_ND_Joint'] = np.where(is_nd_joint_total_zero, 0.0, np.where(kondisi, df['Base_qx_ND_Joint'] * (1 + pad_mortality), 0.0))

    df['Monthly_qx_PA'] = np.where(is_pa_total_zero, 0.0, np.where(kondisi, df['Base_qx_PA'] * (1 + pad_mortality), 0.0))

    df['Monthly_qx_CI'] = np.where(is_ci_total_zero, 0.0, np.where(kondisi, df['Base_qx_CI'] * (1 + pad_mortality), 0.0))

    df['Monthly_qx_TPD'] = np.where(is_tpd_total_zero, 0.0, np.where(kondisi, df['Base_qx_TPD'] * (1 + pad_mortality), 0.0))

    df['Monthly_qx_CP'] = np.where(is_cp_total_zero, 0.0, np.where(kondisi, df['Base_qx_CP'] * (1 + pad_mortality), 0.0))

    """
    Menghitung Monthly qx (Lapse) menggunakan 2D Lookup pada tabel Lapse Rate.
    Rumus: (Tahun Polis > 0) * (Tahun Polis < Masa Asuransi) * VLOOKUP(MPP, Tabel, Tahun Polis + 1) * (1 + PAD Lapse)
    """
    
    # def get_lapse_rate(mpp, tahun_polis, table):
    #     # Cari baris berdasarkan MPP (asumsi kolom pertama tabel adalah MPP)
    #     # print(f"MASA PEMBAYARAN PREMI: {mpp} | TAHUN POLIS:{tahun_polis} | TABLE LAPSE MONTHLY:\n{table}")
    #     row_match = table[table.iloc[:, 0] == mpp]
    #     if row_match.empty:
    #         return 0.0
        
    #     # Cari kolom berdasarkan Tahun Polis + 1
    #     # Menggunakan .iloc untuk akses berdasarkan index kolom
    #     try:
    #         # tahun_polis + 1 karena di Excel indeks kolomnya geser
    #         col_idx = tahun_polis 
    #         rate = row_match.iloc[0, col_idx]
    #         return rate
    #     except:
    #         return 0.0

    def get_lapse_rate(mpp, tahun_polis, table):
        try:
            # --- DEBUGGING START ---
            # print nilai yang kita cari dan apa yang tersedia di kolom pertama tabel
            # if 'debug_printed' not in globals():
            #     print(f"DEBUG: Mencari MPP = '{mpp}' (tipe: {type(mpp)})")
            #     print(f"DEBUG: Isi kolom pertama tabel: {table.iloc[:, 0].tolist()}")
            #     global debug_printed
            #     debug_printed = True
            # --- DEBUGGING END ---

            # 1. Bersihkan dan samakan tipe data MPP menjadi integer
            mpp_clean = int(float(mpp)) if pd.notnull(mpp) else 0
            tahun_polis_int = int(float(tahun_polis))
            
            # Konversi kolom pertama tabel asumsi ke numerik untuk menghindari error string/float
            col_mpp = pd.to_numeric(table.iloc[:, 0], errors='coerce')

            table_mpp = pd.to_numeric(table.iloc[:, 0], errors='coerce')
            mpp_search = pd.to_numeric(mpp, errors='coerce')
            
            # Cari baris berdasarkan MPP
            # row_match = table[col_mpp == mpp_clean]
            row_match = table[table_mpp == mpp_search]

            # print(f"DEBUG COL MPP = {col_mpp}")
            # print(f"DEBUG MPP CLEAN = {mpp_clean}")
            # print(f"DEBUG TAHUN POLIS INT = {tahun_polis_int}")
            
            if row_match.empty:
                # Debugging: Jika baris tidak ketemu, cetak info ini di terminal
                print(f"DEBUG: MPP '{mpp_clean}' tidak ditemukan di tabel Lapse Rate!")
                return 0.0
            
            # 2. Ambil nilai berdasarkan kolom (Tahun Polis + 1)
            # Karena di Excel VLOOKUP kolom ke-(tahun_polis + 1)
            col_idx = tahun_polis_int 
            rate = row_match.iloc[0, col_idx]
            
            return float(rate) if pd.notnull(rate) else 0.0
            
        except Exception as e:
            print(f"DEBUG Error get_lapse_rate: {e}")
            return 0.0

    # Pastikan kolom referensi ada
    if 'Masa_Pembayaran_Premi_Dasar' not in df.columns or 'A_Policy_Year' not in df.columns:
        print("DEBUG: Kolom 'Masa_Pembayaran_Premi_Dasar' atau 'A_Policy_Year' tidak ditemukan di DataFrame!")
        df['Monthly_qx_Lapse'] = 0.0
        return df

    # 1. Terapkan fungsi untuk setiap baris
    df['Base_Lapse_Rate'] = df.apply(lambda x: get_lapse_rate(x['Masa_Pembayaran_Premi_Dasar'], x['A_Policy_Year']+1, asumsi_lapse_monthly), axis=1)

    # 2. Rumus: (Tahun Polis > 0) * (Tahun Polis < Masa Asuransi)
    # Catatan: Asumsi 'Pol_Term_Y' adalah Masa Asuransi dalam tahun
    # kondisi_monthly_lapse = (df['A_Policy_Year'] > 0) & (df['A_Policy_Year'] < df['Pol_Term_Y'])
    # print(f"KONDISI MONTHLY LAPSE: {kondisi_monthly_lapse}")

    # 2. Sesuai Rumus Excel: (Tahun Polis > 0) * (Tahun Polis < Masa Asuransi)
    # Pastikan nama kolom masa asuransi sesuai (misal: 'Pol_Term_Y')
    masa_asuransi = df['Pol_Term_Y'] if 'Pol_Term_Y' in df.columns else 3
    
    kondisi_monthly_lapse = (df['A_Policy_Year'] > 0) & (df['A_Policy_Year'] < masa_asuransi)

    # 3. Kalkulasi Final Monthly qx (Lapse) dengan PAD Lapse
    df['Monthly_qx_Lapse'] = kondisi_monthly_lapse.astype(int) * df['Base_Lapse_Rate'] * (1 + pad_lapse)

    # 6. Susun DataFrame Hasil Proyeksi
    projection = pd.DataFrame({
        "Tahun Polis": df['A_Policy_Year'],
        "Bulan ke-": bulan_ke,
        "Premi": df['Premi'],
        "Komisi": df['Komisi'],
        "Biaya Akuisisi": df['Biaya_Akuisisi'],
        "% Premi (PAD)": pad_value,
        "Fixed Cost": fixed_cost_value, 
        "Fixed Cost (Dihitung CARE)": round(fixed_cost_value * ((1 + eff_monthly_inflation) ** bulan_ke)),
        "Yearly Rate CV": df['Yearly_Rate_Cash_Value'],
        "Monthly Rate CV": df['Monthly_Rate_Cash_Value'],
        "Monthly qx (Term Life)": df['Monthly_qx'],
        "Monthly qx (ND)": df['Monthly_qx_ND'],
        "Monthly qx (Term Life Joint)": df['Monthly_qx_Term_Life_Joint'],
        "Monthly qx (ND Joint)": df['Monthly_qx_ND_Joint'],
        "Monthly qx (PA)": df['Monthly_qx_PA'],
        "Monthly qx (CI)": df['Monthly_qx_CI'],
        "Monthly qx (TPD)": df['Monthly_qx_TPD'],
        "Monthly qx (CP)": df['Monthly_qx_CP'],
        "Monthly qx (Lapse)": df['Monthly_qx_Lapse']
    })
    
    return projection