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

import pandas as pd

def generate_cashflow_projection2(df_detail, pad_expense=0.0):
    """
    Melakukan looping pada setiap baris di df_detail dan menghasilkan proyeksi
    untuk seluruh polis yang ada di dalam sheet.
    """
    all_projections = []

    # Mengambil nilai PCT_Premi dari sheet Detail
    pct_premi = df_detail['Biaya_Pemeliharaan_Polis_PCT_Premi'].iloc[0]

    # Mengambil nilai Fixed Cost dari sheet Detail
    fixed_cost = df_detail['Biaya_Pemeliharaan_Polis_Fixed_Cost'].iloc[0]

    # Rumus Excel: Biaya_Pemeliharaan_Polis_PCT_Premi * (1 + PAD Expense)
    pad_value = pct_premi * (1 + pad_expense)

    # Rumus Excel: Biaya_Pemeliharaan_Polis_Fixed_Cost * (1 + PAD Expense)
    fixed_cost_value = fixed_cost * (1 + pad_expense)

    # print(f"FIXED COST VALUE: {fixed_cost_value} | FIXED COST: {fixed_cost}")
    # print(f"DATA FRAME DETAIL: {df_detail}")
    
    # Looping setiap baris di df_detail
    for index, row in df_detail.iterrows():
        # Mengambil parameter dari setiap baris
        premium = row.get('Premi', 0)
        komisi = row.get('Komisi', 0)
        akuisisi = row.get('Biaya_Akuisisi', 0)
        pct_premi = row.get('Biaya_Pemeliharaan_Polis_PCT_Premi', 0)
        fixed_cost_base = row.get('Fixed_Cost', 1.0) # Mengambil nilai dari kolom Fixed Cost di sheet Detail
        duration = row.get('Duration_Years', 3) # Asumsi ada kolom durasi
        
        # Perhitungan PAD Expense
        pad_value = pct_premi * (1 + pad_expense)

        # print(f"PAD VALUE: {pad_value}")

        # Buat array bulan dari 1 sampai durasi
        total_months = duration * 12
        months = np.arange(1, total_months + 1)
        
        # print(f"Polis_ID: {row.get('Polis_ID', index)} | Tahun: {tahun} | Bulan: {month}")
            
        projection = pd.DataFrame({
            # "Polis_ID": row.get('Polis_ID', index), # Identitas unik
            "Tahun Polis": ((months - 1) // 12) + 1,
            "Bulan ke-": months,
            "Premi": [premium if m == 1 else 0 for m in months],
            "Komisi": komisi if is_first_month else 0,
            "Biaya Akuisisi": akuisisi if is_first_month else 0,
            "% Premi (PAD)": pad_value if is_first_month else 0,
            "Fixed Cost":  fixed_cost_value if is_first_month else 0, 
            "Fixed Cost (Dihitung CARE)": 1.000 * (1.002 ** (month - 1))
        })
        all_projections.append(projection)

        print(f"ALL PROJECTIONS: {all_projections}")
    
    return pd.DataFrame(all_projections)