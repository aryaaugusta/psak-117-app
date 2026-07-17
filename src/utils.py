import pandas as pd

def format_date_columns(df):
    """
    Memformat tanggal hanya jika data tampak seperti tanggal lengkap (bukan sekadar tahun 4 digit).
    """
    for col in df.columns:
        # Cek kolom yang memiliki karakter tanggal (seperti '-' atau '/')
        if df[col].astype(str).str.contains('-|/').any():
            try:
                # Konversi ke datetime, paksa error menjadi NaT
                converted = pd.to_datetime(df[col], errors='coerce')
                sample_data = df[col].astype(str)
                
                # Hanya format jika kolom tersebut benar-benar berisi tanggal (bukan hanya angka tahun 4 digit yang jadi epoch)
                # Kita cek jika nilainya lebih besar dari 1970 atau memiliki komponen bulan/hari
                if converted.notna().any():
                    # Jika data asli tidak mengandung karakter '-' (asumsi tahun saja), lewati
                    if not df[col].astype(str).str.contains('-|/').all():
                        continue
                    
                    df[col] = converted.dt.strftime('%d-%m-%Y')

                # Hanya proses jika kolom berisi data yang polanya tanggal (ada tanda '-')
                if sample_data.str.contains(r'\d{4}-\d{2}-\d{2}').any():
                    # Konversi ke datetime, paksa error menjadi NaT
                    converted = pd.to_datetime(df[col], errors='coerce')
                    
                    # Cek apakah kolom tersebut benar-benar mengandung data datetime
                    if converted.notna().any():
                        # Terapkan format hanya pada baris yang valid (bukan tahun saja)
                        df[col] = converted.dt.strftime('%d-%m-%Y')
            except:
                continue
    return df

def format_idr(val):
    """
    Mengubah float/int menjadi format string Rupiah yang rapi
    """
    if isinstance(val, (int, float)):
        return f"Rp {val:,.2f}"
    return val