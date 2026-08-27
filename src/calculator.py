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
                                  asumsi_lapse_monthly=None, pad_lapse=0.0, bonus_rate_monthly=0.0, discount_rate_monthly=0.0):
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

    def get_lapse_rate(row, table):
        try:
            # 1. Ambil UW_Year dari tanggal Effective polis
            tanggal_eff = pd.to_datetime(row.get('Effective', '2023-01-01'))
            uw_year_target = tanggal_eff.year
            
            # 2. Ambil nilai MPP (Masa Pembayaran Premi)
            mpp_val = row.get('Masa_Pembayaran_Premi_Dasar', 0)
            mpp_clean = int(float(mpp_val)) if pd.notnull(mpp_val) else 0
            
            # 3. PERBAIKAN: Utamakan mengambil nilai dari kolom 'A_Policy_Year'
            tahun_polis_val = row.get('A_Policy_Year', 1)
            tahun_polis_int = int(float(tahun_polis_val)) if pd.notnull(tahun_polis_val) else 1
            
            # 4. Filter baris tabel berdasarkan UW_Year DAN MPP
            col_uw = pd.to_numeric(table.iloc[:, 0], errors='coerce').astype('Int64')
            col_mpp = pd.to_numeric(table.iloc[:, 1], errors='coerce').astype('Int64')
            
            row_match = table[(col_uw == uw_year_target) & (col_mpp == mpp_clean)]
            
            if row_match.empty:
                return 0.0
            
            # 5. Ambil posisi kolom (Tahun Polis + 1)
            # Index 0: UW_Year | Index 1: MPP/Year | Index 2: Tahun 1 | Index 3: Tahun 2 | Index 4: Tahun 3 ...
            col_idx = tahun_polis_int + 1
            
            # Pengecekan batas kolom agar tidak IndexError
            if col_idx < len(row_match.columns):
                rate = row_match.iloc[0, col_idx]
                return float(rate) if pd.notnull(rate) else 0.0
                
            return 0.0
            
        except Exception as e:
            return 0.0

    # Pastikan kolom referensi ada
    if 'Masa_Pembayaran_Premi_Dasar' not in df.columns or 'A_Policy_Year' not in df.columns:
        print("DEBUG: Kolom 'Masa_Pembayaran_Premi_Dasar' atau 'A_Policy_Year' tidak ditemukan di DataFrame!")
        df['Monthly_qx_Lapse'] = 0.0
        return df

    # 1. Terapkan fungsi untuk setiap baris
    # df['Base_Lapse_Rate'] = df.apply(lambda x: get_lapse_rate(x['Masa_Pembayaran_Premi_Dasar'], x['A_Policy_Year']+1, asumsi_lapse_monthly), axis=1)
    # Terapkan fungsi lookup per baris dengan axis=1
    df['Base_Lapse_Rate'] = df.apply(
        lambda row: get_lapse_rate(row, asumsi_lapse_monthly), 
        axis=1
    )

    # 2. Ambil Masa Asuransi dalam Bulan (Pol_Term_M) dari Header atau kolom terkait
    masa_asuransi_bulan = df['Pol_Term_M'] if 'Pol_Term_M' in df.columns else (df.get('Pol_Term_Y', 3) * 12)

    # 3. KONDISI BARU: 
    # - Bulan_Ke harus > 0
    # - Bulan_Ke harus KURANG DARI Pol_Term_M (sehingga saat masuk bulan ke-36 / pas di Pol_Term_M, hasilnya False -> jadi 0)
    bulan_ke = df['Bulan_Ke']
    kondisi_monthly_lapse = (bulan_ke > 0) & (bulan_ke < masa_asuransi_bulan)

    # 3. Kalkulasi Final Monthly qx (Lapse) dengan PAD Lapse
    df['Monthly_qx_Lapse'] = kondisi_monthly_lapse.astype(int) * df['Base_Lapse_Rate'] * (1 + pad_lapse)

    # Jika Bulan_Ke sama dengan Masa Asuransi (dalam bulan), bernilai 1, selain itu 0
    df['Monthly_qx_Mature'] = np.where(bulan_ke == masa_asuransi_bulan, 1.0, 0.0)

    # Inisialisasi list untuk menampung hasil perhitungan decrement
    survive_beg_list = []
    term_life_list = []
    nd_list = []
    lapse_list = []
    mature_list = []
    term_life_joint_list = []
    nd_joint_list = []
    pa_list = []
    ci_list = []
    tpd_list = []
    cp_list = []
    survive_end_list = []
    akumulasi_bonus_list = []

    # Dictionary untuk melacak survive ending per polis (jika ada banyak polis)
    prev_survive_end_dict = {}

    # Ambil nilai dasar benefits dari sheet Detail (menggantikan sel R4 dan S4 per baris)
    base_term_life_benefit = df['Term_Life'] if 'Term_Life' in df.columns else 0.0
    base_nd_benefit = df['ND'] if 'ND' in df.columns else 0.0
    base_joint_term_life_benefit = df['Term_Life_Joint'] if 'Term_Life_Joint' in df.columns else 0.0
    base_joint_nd_benefit = df['ND_Joint'] if 'ND_Joint' in df.columns else 0.0
    base_pa_benefit = df['PA'] if 'PA' in df.columns else 0.0
    base_pv_death_before_pv_benefit = df['PV_Death_Before_PV'] if 'PV_Death_Before_PV' in df.columns else 0.0
    # base_pv_death_benefit = df['PV_Death'] if 'PV_Death' in df.columns else 0.0
    base_ci_benefit = df['CI'] if 'CI' in df.columns else 0.0
    base_tpd_benefit = df['TPD'] if 'TPD' in df.columns else 0.0
    base_cp_benefit = df['CP'] if 'CP' in df.columns else 0.0
    base_bonus_benefit = df['Bonus'] if 'Bonus' in df.columns else 0.0

    base_surrender_benefit = df['Surrender'] if 'Surrender' in df.columns else 0.0
    base_tahapan_benefit = df['Tahapan'] if 'Tahapan' in df.columns else 0.0
    base_maturity_benefit = df['Maturity'] if 'Maturity' in df.columns else 0.0

    # Inisialisasi list benefit
    term_life_benefit_list = []
    nd_benefit_list = []
    joint_term_life_benefit_list = []
    joint_nd_benefit_list = []
    pa_benefit_list = []
    pv_death_before_pv_benefit_list = []
    # pv_death_benefit_list = []
    ci_benefit_list = []
    tpd_benefit_list = []
    cp_benefit_list = []
    bonus_benefit_list = []

    # Inisialisasi list survival benefit
    surrender_list = []
    tahapan_list = []
    maturity_list = []

    # Inisialisasi list penampung akumulasi bonus
    akumulasi_bonus_list = []
    prev_akumulasi_bonus_dict = {} # Melacak akumulasi bonus per polis

    # Inisialisasi list penampung After Decrement Benefits
    after_term_life_list = []
    after_nd_list = []
    after_joint_term_life_list = []
    after_joint_nd_list = []
    after_pa_list = []
    after_pv_death_list = []
    after_ci_list = []
    after_tpd_list = []
    after_cp_list = []

    # Inisialisasi list penampung Survival Benefits & Summary After Decrement
    after_surrender_list = []
    after_tahapan_list = []
    after_maturity_list = []
    total_future_benefits_list = []
    surrender_refund_list = []

    # ==========================================
    # 1. LOOPING UTAMA PER BARIS (Forward Iteration)
    # ==========================================
    for idx, row in df.iterrows():
        policy_id = row.get('Policy_ID', row.get('A_PolicyNo', 'default_policy'))
        bulan_ke = row.get('Bulan_Ke', 1)
        
        # Survive beginning
        if bulan_ke == 1 or policy_id not in prev_survive_end_dict:
            survive_beg = 1.0
        else:
            survive_beg = prev_survive_end_dict.get(policy_id, 1.0)

        # Ambil qx masing-masing decrement
        q_term = row.get('Monthly_qx', row.get('Monthly qx (Term Life)', 0.0))
        q_nd = row.get('Monthly_qx_ND', row.get('Monthly qx (ND)', 0.0))
        q_lapse = row.get('Monthly_qx_Lapse', row.get('Monthly qx (Lapse)', 0.0))
        q_mature = row.get('Monthly_qx_Mature', row.get('Monthly qx (Mature)', 0.0))
        q_term_joint = row.get('Monthly_qx_Term_Life_Joint', row.get('Monthly qx (Term Life Joint)', 0.0))
        q_nd_joint = row.get('Monthly_qx_ND_Joint', row.get('Monthly qx (ND Joint)', 0.0))
        q_pa = row.get('Monthly_qx_PA', row.get('Monthly qx (PA)', 0.0))
        q_ci = row.get('Monthly_qx_CI', row.get('Monthly qx (CI)', 0.0))
        q_tpd = row.get('Monthly_qx_TPD', row.get('Monthly qx (TPD)', 0.0))
        q_cp = row.get('Monthly_qx_CP', row.get('Monthly qx (CP)', 0.0))

        # Decrement values
        term_life_val = q_term * survive_beg
        nd_val = q_nd * survive_beg
        lapse_val = q_lapse * survive_beg
        mature_val = q_mature * survive_beg
        term_life_joint_val = q_term_joint * survive_beg
        nd_joint_val = q_nd_joint * survive_beg
        pa_val = q_pa * survive_beg
        ci_val = q_ci * survive_beg
        tpd_val = q_tpd * survive_beg
        cp_val = q_cp * survive_beg

        # Survive ending
        if bulan_ke == 0:
            survive_end = 0.0
        else:
            survive_end = survive_beg - (term_life_val + lapse_val + mature_val)

        prev_survive_end_dict[policy_id] = survive_end

        survive_beg_list.append(survive_beg)
        term_life_list.append(term_life_val)
        nd_list.append(nd_val)
        lapse_list.append(lapse_val)
        mature_list.append(mature_val)
        term_life_joint_list.append(term_life_joint_val)
        nd_joint_list.append(nd_joint_val)
        pa_list.append(pa_val)
        ci_list.append(ci_val)
        tpd_list.append(tpd_val)
        cp_list.append(cp_val)
        survive_end_list.append(survive_end)

        # Base benefits
        term_life_benefit_val = base_term_life_benefit.iloc[idx]
        nd_benefit_val = base_nd_benefit.iloc[idx]
        joint_term_life_benefit_val = base_joint_term_life_benefit.iloc[idx]
        joint_nd_benefit_val = base_joint_nd_benefit.iloc[idx]
        pa_benefit_val = base_pa_benefit.iloc[idx]
        pv_death_before_pv_benefit_val = base_pv_death_before_pv_benefit.iloc[idx]
        ci_benefit_val = base_ci_benefit.iloc[idx]
        tpd_benefit_val = base_tpd_benefit.iloc[idx]
        cp_benefit_val = base_cp_benefit.iloc[idx]
        bonus_benefit_val = base_bonus_benefit.iloc[idx]

        surrender_benefit_val = base_surrender_benefit.iloc[idx]
        tahapan_benefit_val = base_tahapan_benefit.iloc[idx]
        maturity_benefit_val = base_maturity_benefit.iloc[idx]

        term_life_benefit_list.append(term_life_benefit_val)
        nd_benefit_list.append(nd_benefit_val)
        joint_term_life_benefit_list.append(joint_term_life_benefit_val)
        joint_nd_benefit_list.append(joint_nd_benefit_val)
        pa_benefit_list.append(pa_benefit_val)
        pv_death_before_pv_benefit_list.append(pv_death_before_pv_benefit_val)
        ci_benefit_list.append(ci_benefit_val)
        tpd_benefit_list.append(tpd_benefit_val)
        cp_benefit_list.append(cp_benefit_val)
        bonus_benefit_list.append(bonus_benefit_val)

        surrender_list.append(surrender_benefit_val)
        tahapan_list.append(tahapan_benefit_val)
        maturity_list.append(maturity_benefit_val)

        # Akumulasi Bonus
        bonus_val = base_bonus_benefit.iloc[idx]
        prev_akrual = prev_akumulasi_bonus_dict.get(policy_id, 0.0)
        if bulan_ke == 1 or policy_id not in prev_akumulasi_bonus_dict:
            akumulasi_bonus_val = bonus_val * (1 + bonus_rate_monthly)
        else:
            akumulasi_bonus_val = (bonus_val + prev_akrual) * (1 + bonus_rate_monthly)
        prev_akumulasi_bonus_dict[policy_id] = akumulasi_bonus_val
        akumulasi_bonus_list.append(akumulasi_bonus_val)

        # After Decrement (Term Life, ND, Joint)
        b_term = term_life_benefit_val
        b_nd = nd_benefit_val
        b_joint_term = joint_term_life_benefit_val
        b_joint_nd = joint_nd_benefit_val
        akr_bonus = akumulasi_bonus_val

        val_after_term = 0.0 if b_term == 0 else (b_term + akr_bonus) * term_life_val
        val_after_nd = 0.0 if b_nd == 0 else b_nd * nd_val
        val_after_joint_term = b_joint_term * term_life_joint_val
        val_after_joint_nd = b_joint_nd * nd_joint_val

        after_term_life_list.append(val_after_term)
        after_nd_list.append(val_after_nd)
        after_joint_term_life_list.append(val_after_joint_term)
        after_joint_nd_list.append(val_after_joint_nd)

        # After Decrement (PA, CI, TPD, CP)
        val_after_pa = pa_benefit_val * pa_val
        val_after_ci = ci_benefit_val * ci_val
        val_after_tpd = tpd_benefit_val * tpd_val
        val_after_cp = cp_benefit_val * cp_val

        after_pa_list.append(val_after_pa)
        after_ci_list.append(val_after_ci)
        after_tpd_list.append(val_after_tpd)
        after_cp_list.append(val_after_cp)

        # Survival Benefits After
        b_surrender = surrender_benefit_val
        b_tahapan = tahapan_benefit_val
        b_maturity = maturity_benefit_val

        val_after_surrender = (b_surrender + akr_bonus) * lapse_val
        val_after_tahapan = b_tahapan * survive_end
        val_after_maturity = (b_maturity + akr_bonus) * mature_val

        after_surrender_list.append(val_after_surrender)
        after_tahapan_list.append(val_after_tahapan)
        after_maturity_list.append(val_after_maturity)
        surrender_refund_list.append(val_after_surrender)


    # ==========================================
    # 2. PERHITUNGAN MUNDUR (BACKWARD RECURSION) UNTUK PV DEATH
    # Dilakukan di luar loop utama setelah seluruh list dasar terbentuk
    # ==========================================
    base_pv_death_bpv = pv_death_before_pv_benefit_list if pv_death_before_pv_benefit_list else [0.0] * len(df)
    pv_death_before_decr_list = [0.0] * len(df)
    after_pv_death_list = [0.0] * len(df)
    
    running_pv_decr = 0.0
    rate_divisor = (1 + discount_rate_monthly) if discount_rate_monthly != 0 else 1.0

    # Iterasi mundur dari baris terakhir ke baris pertama
    for idx in range(len(df) - 1, -1, -1):
        current_val = float(base_pv_death_bpv[idx])
        if idx == len(df) - 1:
            running_pv_decr = current_val
        else:
            running_pv_decr = current_val + (running_pv_decr / rate_divisor)
            
        pv_death_before_decr_list[idx] = running_pv_decr
        
        # PV Death After = PV Death Before Decr * Term Life Decrement (term_life_list[idx])
        after_pv_death_list[idx] = running_pv_decr * term_life_list[idx]


    # ==========================================
    # 3. PENYUSUNAN TOTAL FUTURE BENEFITS (CLAIM) PER BARIS
    # ==========================================
    for idx in range(len(df)):
        t_term = after_term_life_list[idx]
        t_nd = after_nd_list[idx]
        t_j_term = after_joint_term_life_list[idx]
        t_j_nd = after_joint_nd_list[idx]
        t_pa = after_pa_list[idx]
        t_pv_death = after_pv_death_list[idx]
        t_ci = after_ci_list[idx]
        t_tpd = after_tpd_list[idx]
        t_cp = after_cp_list[idx]
        t_tahapan = after_tahapan_list[idx]
        t_maturity = after_maturity_list[idx]

        total_claim = (
            t_term + t_nd + t_j_term + t_j_nd + 
            t_pa + t_pv_death + t_ci + t_tpd + t_cp + 
            t_tahapan + t_maturity
        )
        total_future_benefits_list.append(total_claim)

    # Inisialisasi list penampung untuk komisi, akuisisi, premi, dan expenses after decrement
    after_komisi_list = []
    after_biaya_akuisisi_list = []
    after_pct_premi_list = []
    after_fixed_cost_list = []
    total_future_expenses_1_list = []
    total_future_expenses_list = []
    future_premiums_list = []

    for idx in range(len(df)):
        # Ambil nilai dasar baris berjalan
        # 1. Ambil nilai dasar mentah dari DataFrame
        raw_komisi = float(df['Komisi'].iloc[idx]) if 'Komisi' in df.columns else 0.0
        raw_biaya_akuisisi = float(df['Biaya_Akuisisi'].iloc[idx]) if 'Biaya_Akuisisi' in df.columns else 0.0
        
        # Ambil nilai PAD / % Premi mentah
        raw_pct_premi = float(pad_value.iloc[idx]) if hasattr(pad_value, 'iloc') else float(pad_value)
        
        # Fixed Cost CARE mentah
        raw_fixed_cost_care = float(
            fixed_cost_value.iloc[idx] * ((1 + eff_monthly_inflation.iloc[idx]) ** df['Bulan_Ke'].iloc[idx]) 
            if hasattr(fixed_cost_value, 'iloc') else fixed_cost_value
        )
        
        premi_val = float(df['Premi'].iloc[idx]) if 'Premi' in df.columns else 0.0

        survive_beg_val = survive_beg_list[idx] if idx < len(survive_beg_list) else 1.0
        # survive_end_val = survive_end_list[idx] if idx < len(survive_end_list) else 1.0

        # --- PEMBULATAN DASAR SEPERTI DI EXCEL ---
        # Bulatkan nilai dasar biaya akuisisi dan % premi (PAD) ke bilangan bulat terdekat (ROUND)
        base_biaya_akuisisi = round(raw_biaya_akuisisi)  # 17.000
        base_pct_premi = round(raw_pct_premi)            # 27.600
        base_komisi = round(raw_komisi)                  # 92.000

        # --- RUMUS AFTER DECREMENT (EXPENSES & PREMIUMS) ---
        # 1. Komisi After: = Komisi * Survive Beginning
        val_after_komisi = base_komisi * survive_beg_val

        # 2. Biaya Akuisisi After: = Biaya Akuisisi (Bulat) * Survive Ending / Beginning
        val_after_biaya_akuisisi = base_biaya_akuisisi * survive_beg_val

        # 3. % Premi After: = % Premi (Bulat) * Survive Ending
        val_after_pct_premi = base_pct_premi * survive_beg_val

        # 4. Fixed Cost After: = Fixed Cost (Dihitung CARE) * Survive Ending
        val_after_fixed_cost = raw_fixed_cost_care * survive_beg_val

        # 5. Total Future Expenses 1: = % Premi After + Fixed Cost After
        val_total_expenses_1 = val_after_pct_premi + val_after_fixed_cost

        # 6. Total Future Expenses: = (Komisi + Biaya Akuisisi + % Premi + Fixed Cost CARE) * Survive Beginning
        val_total_expenses = (base_komisi + base_biaya_akuisisi + base_pct_premi + raw_fixed_cost_care) * survive_beg_val

        # 7. Future Premiums: = Premi * Survive Beginning
        val_future_premiums = premi_val * survive_beg_val

        after_komisi_list.append(val_after_komisi)
        after_biaya_akuisisi_list.append(val_after_biaya_akuisisi)
        after_pct_premi_list.append(val_after_pct_premi)
        after_fixed_cost_list.append(val_after_fixed_cost)
        total_future_expenses_1_list.append(val_total_expenses_1)
        total_future_expenses_list.append(val_total_expenses)
        future_premiums_list.append(val_future_premiums)

    # ==========================================
    # BACKWARD RECURSION UNTUK SELURUH KOLOM PV (PRESENT VALUE)
    # ==========================================
    n_rows = len(df)
    rate_divisor = (1 + discount_rate_monthly) if discount_rate_monthly != 0 else 1.0

    # Inisialisasi list penampung hasil PV
    pv_benefits_list = [0.0] * n_rows
    pv_surrender_list = [0.0] * n_rows
    pv_komisi_list = [0.0] * n_rows
    pv_akuisisi_list = [0.0] * n_rows
    pv_pct_premi_list = [0.0] * n_rows
    pv_fixed_cost_list = [0.0] * n_rows
    pv_exp_1_list = [0.0] * n_rows
    pv_exp_2_list = [0.0] * n_rows
    pv_premiums_list = [0.0] * n_rows
    bel_list = [0.0] * n_rows
    bel_per_unit_list = [0.0] * n_rows

    # Variabel pelacak akumulasi mundur (running PV)
    run_ben = 0.0
    run_sur = 0.0
    run_kom = 0.0
    run_aku = 0.0
    run_pct = 0.0
    run_fix = 0.0
    run_ex1 = 0.0
    run_ex2 = 0.0
    run_pre = 0.0

    # Iterasi mundur dari baris terakhir ke baris pertama (index n_rows-1 turun ke 0)
    for idx in range(n_rows - 1, -1, -1):
        # Ambil nilai baris berjalan
        curr_ben = total_future_benefits_list[idx] if idx < len(total_future_benefits_list) else 0.0
        curr_sur = surrender_refund_list[idx] if idx < len(surrender_refund_list) else 0.0
        curr_kom = after_komisi_list[idx] if idx < len(after_komisi_list) else 0.0
        curr_aku = after_biaya_akuisisi_list[idx] if idx < len(after_biaya_akuisisi_list) else 0.0
        curr_pct = after_pct_premi_list[idx] if idx < len(after_pct_premi_list) else 0.0
        curr_fix = after_fixed_cost_list[idx] if idx < len(after_fixed_cost_list) else 0.0
        curr_ex1 = total_future_expenses_1_list[idx] if idx < len(total_future_expenses_1_list) else 0.0
        curr_ex2 = total_future_expenses_list[idx] if idx < len(total_future_expenses_list) else 0.0
        curr_pre = future_premiums_list[idx] if idx < len(future_premiums_list) else 0.0

        if idx == n_rows - 1:
            run_ben = curr_ben
            run_sur = curr_sur
            run_kom = curr_kom
            run_aku = curr_aku
            run_pct = curr_pct
            run_fix = curr_fix
            run_ex1 = curr_ex1
            run_ex2 = curr_ex2
            run_pre = curr_pre
        else:
            run_ben = (curr_ben + run_ben) / rate_divisor
            run_sur = (curr_sur + run_sur) / rate_divisor
            run_kom = curr_kom + (run_kom / rate_divisor)
            run_aku = curr_aku + (run_aku / rate_divisor)
            run_pct = curr_pct + (run_pct / rate_divisor)
            run_fix = curr_fix + (run_fix / rate_divisor)
            run_ex1 = curr_ex1 + (run_ex1 / rate_divisor)
            run_ex2 = curr_ex2 + (run_ex2 / rate_divisor)
            run_pre = curr_pre + (run_pre / rate_divisor)

        # print(f"DEBUG: KOMISI = {curr_kom} | PV FUTURE KOMISI BERIKUTNYA = {run_kom}")
        # print(f"DEBUG: PV FUTURE KOMISI BERIKUTNYA = {run_kom}")
        # print(f"DEBUG: DISC RATE PER MONTH = {rate_divisor}")

        pv_benefits_list[idx] = run_ben
        pv_surrender_list[idx] = run_sur
        pv_komisi_list[idx] = run_kom
        pv_akuisisi_list[idx] = run_aku
        pv_pct_premi_list[idx] = run_pct
        pv_fixed_cost_list[idx] = run_fix
        pv_exp_1_list[idx] = run_ex1
        pv_exp_2_list[idx] = run_ex2
        pv_premiums_list[idx] = run_pre

        # --- RUMUS BEL ---
        # BEL = PV Future Benefits (Claim) + PV Surrender (Refund) + PV Future Expenses 2 - PV Future Premiums
        val_bel = run_ben + run_sur + run_ex2 - run_pre
        bel_list[idx] = val_bel

        # --- RUMUS BEL PER UNIT ---
        # =IF(AND(bulan_ke=0; bulan_ke_berikutnya=0); 0; BEL / survive_beginning_decrement)
        b_ke = float(df['Bulan_Ke'].iloc[idx]) if 'Bulan_Ke' in df.columns else 1.0
        next_b_ke = float(df['Bulan_Ke'].iloc[idx + 1]) if idx + 1 < n_rows else 0.0
        surv_beg = survive_beg_list[idx] if idx < len(survive_beg_list) else 1.0

        if b_ke == 0 and next_b_ke == 0:
            val_bel_unit = 0.0
        else:
            val_bel_unit = val_bel / surv_beg if surv_beg != 0 else 0.0

        bel_per_unit_list[idx] = val_bel_unit

    # Inisialisasi list penampung Movement BEL
    bel_beginning_list = []
    bel_premium_list = []
    bel_commission_list = []
    bel_expense_list = []
    bel_other_expense_list = []
    bel_claim_list = []
    bel_surrender_list = []
    unwind_list = []
    inc_dec_bel_list = []
    bel_ending_list = []
    selisih_list = []

    n_rows = len(df)
    prev_bel_ending = 0.0  # Variabel pelacak BEL Ending bulan sebelumnya

    for idx in range(n_rows):
        # A. BEL Beginning: 
        # Bulan pertama ambil dari nilai BEL asli, bulan berikutnya ambil dari BEL Ending baris sebelumnya
        if idx == 0:
            bel_beg = float(bel_list[idx]) if idx < len(bel_list) else 0.0
        else:
            bel_beg = prev_bel_ending

        # Ambil variabel pendukung per baris
        surv_beg = survive_beg_list[idx] if idx < len(survive_beg_list) else 1.0
        surv_end = survive_end_list[idx] if idx < len(survive_end_list) else 1.0
        
        fut_prem = future_premiums_list[idx] if idx < len(future_premiums_list) else 0.0
        komisi_after = after_komisi_list[idx] if idx < len(after_komisi_list) else 0.0
        exp_1_after = total_future_expenses_1_list[idx] if idx < len(total_future_expenses_1_list) else 0.0
        akuisisi_after = after_biaya_akuisisi_list[idx] if idx < len(after_biaya_akuisisi_list) else 0.0
        
        tot_fut_ben_after = (
            after_term_life_list[idx] + after_nd_list[idx] + 
            after_joint_term_life_list[idx] + after_joint_nd_list[idx] + 
            after_pa_list[idx] + after_pv_death_list[idx] + 
            after_ci_list[idx] + after_tpd_list[idx] + after_cp_list[idx] + 
            after_tahapan_list[idx] + after_maturity_list[idx]
        ) if idx < len(after_term_life_list) else 0.0

        surr_after = after_surrender_list[idx] if idx < len(after_surrender_list) else 0.0

        # B. BEL Premium
        bel_prem = (fut_prem / surv_beg) if surv_beg != 0 else 0.0

        # C. BEL Commission
        bel_comm = (-komisi_after / surv_beg) if surv_beg != 0 else 0.0

        # D. BEL Expense
        bel_exp = (-exp_1_after / surv_beg) if surv_beg != 0 else 0.0

        # E. BEL Other Expenses
        bel_oth_exp = (-akuisisi_after / surv_beg) if surv_beg != 0 else 0.0

        # F. BEL Claim
        bel_claim = (-tot_fut_ben_after / surv_beg) if surv_beg != 0 else 0.0

        # G. BEL Surrender
        bel_surr = (-surr_after / surv_beg) if surv_beg != 0 else 0.0

        # H. Unwind
        unwind_val = (bel_beg + bel_prem + bel_comm + bel_exp + bel_oth_exp) * discount_rate_monthly

        # I. Inc (Dec) of BEL
        next_bel = bel_list[idx + 1] if idx + 1 < n_rows else 0.0
        if next_bel == 0:
            inc_dec_val = 0.0
        else:
            inv_surv_end = (1.0 / surv_end) if surv_end != 0 else 0.0
            inv_surv_beg = (1.0 / surv_beg) if surv_beg != 0 else 0.0
            inc_dec_val = next_bel * (inv_surv_end - inv_surv_beg)

        # J. BEL Ending
        bel_end = (
            bel_beg + bel_prem + bel_comm + bel_exp + bel_oth_exp + 
            bel_claim + bel_surr + unwind_val + inc_dec_val
        )

        # Simpan BEL Ending untuk dibaca sebagai BEL Beginning pada iterasi bulan berikutnya
        prev_bel_ending = bel_end

        # K. Selisih
        bel_per_unit_val = bel_per_unit_list[idx] if idx < len(bel_per_unit_list) else 0.0
        selisih_val = bel_beg - bel_per_unit_val

        bel_beginning_list.append(bel_beg)
        bel_premium_list.append(bel_prem)
        bel_commission_list.append(bel_comm)
        bel_expense_list.append(bel_exp)
        bel_other_expense_list.append(bel_oth_exp)
        bel_claim_list.append(bel_claim)
        bel_surrender_list.append(bel_surr)
        unwind_list.append(unwind_val)
        inc_dec_bel_list.append(inc_dec_val)
        bel_ending_list.append(bel_end)
        selisih_list.append(selisih_val)

    # Masukkan ke kolom DataFrame
    df['Survive_Beginning'] = survive_beg_list
    df['Term_Life_Decr'] = term_life_list
    df['Lapse_Decr'] = lapse_list
    df['Mature_Decr'] = mature_list
    df['Survive_Ending'] = survive_end_list
    df['ND'] = nd_list
    df['Term_Life_Joint'] = term_life_joint_list
    df['ND_Joint'] = nd_joint_list
    df['PA'] = pa_list
    df['CI'] = ci_list
    df['TPD'] = tpd_list
    df['CP'] = cp_list
    df['Term_Life_Benefit'] = term_life_benefit_list
    df['ND_Benefit'] = nd_benefit_list
    df['Joint_Term_Life_Benefit'] = joint_term_life_benefit_list
    df['Joint_ND_Benefit'] = joint_nd_benefit_list
    df['PA_Benefit'] = pa_benefit_list
    df['PV_Death_Before_PV_Benefit'] = pv_death_before_pv_benefit_list
    df['PV_Death_Benefit'] = pv_death_before_decr_list
    df['CI_Benefit'] = ci_benefit_list
    df['TPD_Benefit'] = tpd_benefit_list
    df['CP_Benefit'] = cp_benefit_list
    df['Bonus_Benefit'] = bonus_benefit_list
    df['Surrender_Benefit'] = surrender_list
    df['Tahapan_Benefit'] = tahapan_list
    df['Maturity_Benefit'] = maturity_list
    df['Akumulasi_Bonus'] = akumulasi_bonus_list

    df['After_Term_Life'] = after_term_life_list
    df['After_ND'] = after_nd_list
    df['After_Joint_Term_Life'] = after_joint_term_life_list
    df['After_Joint_ND'] = after_joint_nd_list
    df['After_PA'] = after_pa_list
    df['After_PV_Death'] = after_pv_death_list
    df['After_CI'] = after_ci_list
    df['After_TPD'] = after_tpd_list
    df['After_CP'] = after_cp_list

    df['After_Surrender'] = after_surrender_list
    df['After_Tahapan'] = after_tahapan_list
    df['After_Maturity'] = after_maturity_list
    df['Total_Future_Benefits_Claim'] = total_future_benefits_list
    df['Surrender_Refund'] = surrender_refund_list

    df['After_Komisi'] = after_komisi_list
    df['After_Biaya_Akuisisi'] = after_biaya_akuisisi_list
    df['After_Pct_Premi'] = after_pct_premi_list
    df['After_Fixed_Cost'] = after_fixed_cost_list
    df['Total_Future_Expenses_1'] = total_future_expenses_1_list
    df['Total_Future_Expenses_2'] = total_future_expenses_list
    df['Future_Premiums'] = future_premiums_list

    df['PV_Future_Benefits'] = pv_benefits_list
    df['PV_Surrender'] = pv_surrender_list
    df['PV_Future_Komisi'] = pv_komisi_list
    df['PV_Future_Akuisisi'] = pv_akuisisi_list
    df['PV_Future_Pct_Premi'] = pv_pct_premi_list
    df['PV_Future_Fixed_Cost'] = pv_fixed_cost_list
    df['PV_Future_Exp_1'] = pv_exp_1_list
    df['PV_Future_Exp_2'] = pv_exp_2_list
    df['PV_Future_Premiums'] = pv_premiums_list
    df['BEL'] = bel_list
    df['BEL_Per_Unit'] = bel_per_unit_list

    df['Movement_BEL_Beginning'] = bel_beginning_list
    df['Movement_BEL_Premium'] = bel_premium_list
    df['Movement_BEL_Commission'] = bel_commission_list
    df['Movement_BEL_Expense'] = bel_expense_list
    df['Movement_BEL_Other_Expense'] = bel_other_expense_list
    df['Movement_BEL_Claim'] = bel_claim_list
    df['Movement_BEL_Surrender'] = bel_surrender_list
    df['Movement_Unwind'] = unwind_list
    df['Movement_Inc_Dec_BEL'] = inc_dec_bel_list
    df['Movement_BEL_Ending'] = bel_ending_list
    df['Movement_Selisih'] = selisih_list

    # 6. Susun DataFrame Hasil Proyeksi
    projection = pd.DataFrame({
        "Tahun Polis": df['A_Policy_Year'],
        "Bulan ke-": df['Bulan_Ke'],
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
        "Monthly qx (Lapse)": df['Monthly_qx_Lapse'],
        "Monthly qx (Mature)": df['Monthly_qx_Mature'],
        # Kolom Decrement Baru (sesuai manfaat)
        "Survive beginning": df['Survive_Beginning'],
        "Term Life": df['Term_Life_Decr'],
        "Lapse": df['Lapse_Decr'],
        "Mature": df['Mature_Decr'],
        "Survive ending": df['Survive_Ending'],
        "ND": df['ND'],
        "Term Life Joint": df['Term_Life_Joint'],
        "ND Joint": df['ND_Joint'],
        "PA": df['PA'],
        "CI": df['CI'],
        "TPD": df['TPD'],
        "CP": df['CP'],
        # Kolom Before Decrement
        "Term Life (BD - Benefit)": df['Term_Life_Benefit'],
        "ND (BD - Benefit)": df['ND_Benefit'],
        "Term Life Joint (BD - Benefit)": df['Joint_Term_Life_Benefit'],
        "ND Joint (BD - Benefit)": df['Joint_ND_Benefit'],
        "PA (BD - Benefit)": df['PA_Benefit'],
        "PV Death Before PV (BD - Benefit)": df['PV_Death_Before_PV_Benefit'],
        "PV Death (Before Decr)": df['PV_Death_Benefit'],
        "CI (BD - Benefit)": df['CI_Benefit'],
        "TPD (BD - Benefit)": df['TPD_Benefit'],
        "CP (BD - Benefit)": df['CP_Benefit'],
        "Bonus (BD - Benefit)": df['Bonus_Benefit'],
        "Akumulasi Bonus (BD - Benefit)": df['Akumulasi_Bonus'],
        # Kolom Survival Benefits
        "Surrender (SB - Benefit)": df['Surrender_Benefit'],
        "Tahapan (SB - Benefit)": df['Tahapan_Benefit'],
        "Maturity (SB - Benefit)": df['Maturity_Benefit'],
        # Kolom After Decrement (Benefits)
        "Term Life (After)": df['After_Term_Life'],
        "ND (After)": df['After_ND'],
        "Joint Term Life (After)": df['After_Joint_Term_Life'],
        "Joint ND (After)": df['After_Joint_ND'],
        "PA (After)": df['After_PA'],
        "PV Death (After)": df['After_PV_Death'],
        "CI (After)": df['After_CI'],
        "TPD (After)": df['After_TPD'],
        "CP (After)": df['After_CP'],
        "Surrender (After)": df['After_Surrender'],
        "Tahapan (After)": df['After_Tahapan'],
        "Maturity (After)": df['After_Maturity'],
        # Kolom Ringkasan Berdiri Sendiri di Luar Grup (atau sesuai struktur Excel)
        "Total Future Benefits (Claim)": df['Total_Future_Benefits_Claim'],
        "Surrender (Refund)": df['Surrender_Refund'],
        # Kolom After Decrement Expenses & Premiums
        "Komisi (After)": df['After_Komisi'],
        "Biaya Akuisisi (After)": df['After_Biaya_Akuisisi'],
        "% Premi (After)": df['After_Pct_Premi'],
        "Fixed Cost (After)": df['After_Fixed_Cost'],
        "Total Future Expenses 1": df['Total_Future_Expenses_1'],
        "Total Future Expenses 2": df['Total_Future_Expenses_2'],
        "Future Premiums": df['Future_Premiums'],
        # Kolom PV Future (Present Value) & BEL
        "PV Future Benefits (Claim)": df['PV_Future_Benefits'],
        "PV Surrender (Refund)": df['PV_Surrender'],
        "PV Future Komisi": df['PV_Future_Komisi'],
        "PV Future Biaya Akuisisi (Other Expense)": df['PV_Future_Akuisisi'],
        "PV Future % Premi": df['PV_Future_Pct_Premi'],
        "PV Future Fixed Cost": df['PV_Future_Fixed_Cost'],
        "PV Future Expenses 1": df['PV_Future_Exp_1'],
        "PV Future Expenses 2": df['PV_Future_Exp_2'],
        "PV Future Premiums": df['PV_Future_Premiums'],
        "BEL": df['BEL'],
        "BEL Per Unit": df['BEL_Per_Unit'],
        # Kolom Movement BEL
        "BEL Beginning": df['Movement_BEL_Beginning'],
        "BEL Premium": df['Movement_BEL_Premium'],
        "BEL Commission": df['Movement_BEL_Commission'],
        "BEL Expense": df['Movement_BEL_Expense'],
        "BEL Other Expense": df['Movement_BEL_Other_Expense'],
        "BEL Claim": df['Movement_BEL_Claim'],
        "BEL Surrender": df['Movement_BEL_Surrender'],
        "Unwind": df['Movement_Unwind'],
        "Inc (Dec) of BEL": df['Movement_Inc_Dec_BEL'],
        "BEL Ending": df['Movement_BEL_Ending'],
        "Selisih": df['Movement_Selisih']
    })
    
    return projection

def get_discount_rate_ibpa(row, df_ibpa):
    try:
        eff_date = pd.to_datetime(row.get('Effective'))
        pol_term_y = int(float(row.get('Pol_Term_Y', 3)))
        
        # 1. Konversi kolom tenor ke numerik, lalu ke integer untuk membuang desimal (.0)
        # pd.to_numeric(..., errors='coerce') menangani jika ada data kotor
        col_tenor_numeric = pd.to_numeric(df_ibpa.iloc[:, 0], errors='coerce').fillna(0).astype(int)
        
        # 2. Cari baris di mana kolom tenor (integer) == pol_term_y
        row_match = df_ibpa[col_tenor_numeric == pol_term_y]
        
        if row_match.empty:
            print(f"DEBUG: Tenor {pol_term_y} tidak ditemukan! Data kolom tenor: {col_tenor_numeric.tolist()}")
            return 0.0

        # 3. Penentuan Kolom (Logika Lookup Tahun)
        lookup_year = max(eff_date.year, 2011) if eff_date.year <= 2023 else eff_date.year
        
        # Cari kolom yang mengandung tahun tersebut
        target_col = next((col for col in df_ibpa.columns if str(lookup_year) in str(col)), None)
        
        if target_col is None:
            return 0.0
        
        # 4. Ambil rate
        rate = row_match.iloc[0][target_col]
        rate_val = float(rate)
        
        # Jika nilai dalam format persentase (misal 5.37), konversi ke desimal
        if rate_val > 1:
            rate_val = rate_val / 100
            
        return rate_val
        
    except Exception as e:
        print(f"DEBUG Error get_discount_rate_ibpa: {e}")
        return 0.0