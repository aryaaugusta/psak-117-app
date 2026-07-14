import pandas as pd

def clean_and_extract_table(df_slice):
    """
    Fungsi untuk mengekstrak sub-tabel secara bersih.
    Mendeteksi baris header asli yang padat data (melewati merged title cell).
    """
    if df_slice.empty:
        return pd.DataFrame()

    # 1. Deteksi baris header asli secara cerdas
    # Baris header asli adalah baris yang memiliki variasi kata kunci terbanyak (bukan merged cell tunggal)
    best_header_idx = 0
    max_valid_cols = -1
    
    # Scan 6 baris pertama untuk mencari baris header yang paling padat/banyak kolom terisi
    for idx in range(min(6, len(df_slice))):
        row_values = df_slice.iloc[idx].astype(str).str.lower().str.strip().tolist()
        # Hitung berapa banyak kolom yang terisi text valid (bukan nan/none/kosong)
        valid_count = sum(1 for val in row_values if val not in ['nan', 'none', '', 'unnamed'])
        
        if valid_count > max_valid_cols:
            max_valid_cols = valid_count
            best_header_idx = idx

    # 2. Ambil baris terbaik sebagai nama kolom
    columns_raw = df_slice.iloc[best_header_idx].tolist()
    
    # 3. Ambil data di bawah baris header tersebut
    df_final = df_slice.iloc[best_header_idx + 1:].copy()
    
    # 4. Standarisasi nama kolom agar tidak ada duplikat atau kolom kosong 'nan'
    clean_columns = []
    seen_cols = {}
    for i, col in enumerate(columns_raw):
        col_str = str(col).strip()
        if col_str.lower() in ['nan', 'none', '']:
            col_str = f"Kolom_Kosong_{i}"
        
        if col_str in seen_cols:
            seen_cols[col_str] += 1
            col_str = f"{col_str}_{seen_cols[col_str]}"
        else:
            seen_cols[col_str] = 0
            
        clean_columns.append(col_str)
        
    df_final.columns = clean_columns
    
    # 5. Buang kolom yang benar-benar tidak bernama (sisa kolom kosong di sebelah kanan Excel)
    df_final = df_final.loc[:, ~df_final.columns.str.contains("Kolom_Kosong_")].copy()
    
    # 6. Buang baris yang kosong total akibat sisa potongan
    df_final.dropna(how='all', inplace=True)
    df_final.reset_index(drop=True, inplace=True)
    
    return df_final

def load_psak117_data(uploaded_file):
    """
    Membaca dan memisahkan sheet DATA INPUT - HEADER secara vertikal dengan aman.
    """
    try:
        # Baca mentah seluruh sheet tanpa header default
        df_raw = pd.read_excel(uploaded_file, sheet_name="DATA INPUT - HEADER", header=None)
        
        # Bersihkan text sel untuk pencarian marker
        df_raw_cleaned = df_raw.astype(str).apply(lambda x: x.str.strip())

        # Cari letak baris kata kunci "TEMPLATE GMM"
        gmm_marker_idx = None
        for idx, row in df_raw_cleaned.iterrows():
            if row.str.contains("TEMPLATE GMM", case=False, na=False).any():
                gmm_marker_idx = idx
                break

        # Potong secara vertikal menjadi dua bagian
        if gmm_marker_idx is not None:
            # Tabel Atas: Dari baris 0 sampai sebelum marker TEMPLATE GMM
            slice_header = df_raw.iloc[0:gmm_marker_idx].copy()
            df_header = clean_and_extract_table(slice_header)
            
            # Tabel Bawah: Dari setelah baris marker TEMPLATE GMM ke bawah
            slice_gmm = df_raw.iloc[gmm_marker_idx + 1:].copy()
            df_gmm = clean_and_extract_table(slice_gmm)
        else:
            # Fallback jika marker pembatas tidak ditemukan
            df_header = clean_and_extract_table(df_raw)
            df_gmm = pd.DataFrame()

        # Load DATA INPUT - DETAIL (Jika ada sheet terpisah)
        try:
            df_detail_raw = pd.read_excel(uploaded_file, sheet_name="DATA INPUT - DETAIL", header=None)
            df_detail = clean_and_extract_table(df_detail_raw)
        except:
            df_detail = df_gmm.copy() if not df_gmm.empty else df_header.copy()

        # Load ASUMSI
        try:
            df_asumsi_raw = pd.read_excel(uploaded_file, sheet_name="ASUMSI", header=None)
            df_asumsi = clean_and_extract_table(df_asumsi_raw)
        except:
            df_asumsi = pd.DataFrame(columns=["Tahun", "Discount_Rate"])

        return {
            "header": df_header,
            "template_gmm": df_gmm,
            "detail": df_detail,
            "asumsi": df_asumsi,
            "status": True,
            "message": "Sukses memisahkan sub-tabel secara vertikal dengan kolom lengkap!"
        }
    except Exception as e:
        return {
            "status": False,
            "message": f"Gagal memproses pemotongan vertikal sheet. Error: {str(e)}"
        }