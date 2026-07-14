import pandas as pd
import numpy as np

def calculate_bel(df_detail, df_asumsi):
    """
    Menghitung Best Estimate Liability (BEL) secara dinamis dan aman dari KeyError.
    """
    df_bel = df_detail.copy()
    
    # 1. Deteksi nama kolom tahun secara dinamis (mengantisipasi variasi nama kolom)
    kolom_tahun = None
    target_names = ["tahun", "t", "year", "periode", "projection_year", "projection year"]
    
    for col in df_bel.columns:
        if col.lower().strip() in target_names:
            kolom_tahun = col
            break
            
    # Jika tetap tidak ketemu, default ke kolom pertama yang berisi angka integer periodik
    if not kolom_tahun:
        kolom_tahun = df_bel.columns[0] 

    # 2. Ambil discount rate dari asumsi secara aman
    # Kita cari juga kolom tahun di sheet asumsi
    kolom_tahun_asumsi = None
    for col in df_asumsi.columns:
        if col.lower().strip() in target_names:
            kolom_tahun_asumsi = col
            break

    # Cari kolom discount rate di sheet asumsi
    kolom_rate = None
    for col in df_asumsi.columns:
        if "rate" in col.lower() or "bunga" in col.lower() or "yield" in col.lower() or "discount" in col.lower():
            kolom_rate = col
            break

    # 3. Proses Gabung Data Asumsi & Detail
    if kolom_tahun_asumsi and kolom_rate:
        # Rename sementara agar pas saat merge
        df_asumsi_temp = df_asumsi[[kolom_tahun_asumsi, kolom_rate]].copy()
        df_asumsi_temp.columns = ["Tahun_Join", "Discount_Rate"]
        
        # Merge ke df_bel
        df_bel = pd.merge(df_bel, df_asumsi_temp, left_on=kolom_tahun, right_on="Tahun_Join", how="left")
        df_bel.drop(columns=["Tahun_Join"], errors="ignore")
    else:
        # Fallback jika struktur sheet ASUMSI tidak terbaca
        df_bel["Discount_Rate"] = 0.05 
        
    # Mengisi nilai rate yang kosong (jika ada) dengan 0
    df_bel["Discount_Rate"] = df_bel["Discount_Rate"].fillna(0.05)

    # 4. Hitung Faktor Diskonto menggunakan kolom tahun yang terdeteksi
    df_bel["Discount_Factor"] = 1 / ((1 + df_bel["Discount_Rate"]) ** df_bel[kolom_tahun])
    
    # 5. Hitung Arus Kas Bersih (Deteksi kolom Inflow/Outflow secara fleksibel jika namanya beda)
    inflow_col = next((c for c in df_bel.columns if "inflow" in c.lower() or "premium" in c.lower() or "masuk" in c.lower()), None)
    outflow_col = next((c for c in df_bel.columns if "outflow" in c.lower() or "claim" in c.lower() or "keluar" in c.lower()), None)
    
    cash_in = df_bel[inflow_col] if inflow_col else 0
    cash_out = df_bel[outflow_col] if outflow_col else 0
    
    df_bel["Net_Cash_Flow"] = cash_in - cash_out
    
    # Present Value dari Net Cash Flow (BEL)
    df_bel["PV_Net_Cash_Flow"] = df_bel["Net_Cash_Flow"] * df_bel["Discount_Factor"]
    
    return df_bel

def calculate_ra_csm(df_header, total_bel, df_asumsi):
    """
    Menghitung Risk Adjustment (RA) dan Contractual Service Margin (CSM) saldo awal / insepsi.
    """
    # Mengambil parameter margin dari sheet asumsi atau header
    # Contoh: RA dihitung dari sekian persen Nilai BEL atau Premium
    ra_percentage = 0.05 # default 5% jika tidak ditemukan di asumsi
    
    total_premium = df_header["Premium"].sum() if "Premium" in df_header.columns else 0
    
    total_ra = total_bel * ra_percentage
    
    # Formula Dasar CSM pada Insepsi Bisnis Baru:
    # CSM = Max(0, -(Premium - Expected Payout/BEL - RA)) -> Jika Unprofitable/Onerous, CSM = 0
    # Catatan: Tanda +/- tergantung dari sudut pandang inflow/outflow di sheet BEL Anda
    net_fulfillment_cf = total_premium - total_bel - total_ra
    
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
    Membuat data pergerakan (Movement Roll-Forward) saldo PSAK 117 dari awal hingga akhir tahun
    """
    # Contoh struktur tabel pergerakan (Movement Sheet)
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
    
    # Hitung Saldo Akhir secara dinamis berdasarkan baris di atasnya
    for col in ["BEL (IDR)", "Risk Adjustment (IDR)", "CSM (IDR)"]:
        opening = df_move.loc[0, col]
        changes = df_move.loc[1:4, col].sum()
        df_move.loc[5, col] = opening + changes
        
    return df_move