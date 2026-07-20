import pandas as pd
import numpy as np

def find_correct_header_row(file_path, sheet_name, target_keyword):
    try:
        df_scan = pd.read_excel(file_path, sheet_name=sheet_name, header=None, nrows=30)
        for idx, row in df_scan.iterrows():
            row_str = row.astype(str).str.lower().str.strip().tolist()
            if any(target_keyword.lower() in str(val) for val in row_str):
                return idx
    except Exception:
        pass
    return 0

def extract_table_from_sheet(df_raw, keyword):
    """
    Fungsi cerdas untuk mengekstrak blok tabel 2D secara dinamis di dalam satu sheet
    berdasarkan kata kunci (keyword).
    """
    for r in range(df_raw.shape[0]):
        for c in range(df_raw.shape[1]):
            cell_val = str(df_raw.iloc[r, c]).strip().lower()
            if keyword.lower() in cell_val:
                
                # 1. Cari Batas Kanan Tabel
                c_end = c
                while c_end < df_raw.shape[1]:
                    # Jika sel header kosong dan sel di bawahnya juga kosong, anggap itu batas kanan
                    if pd.isna(df_raw.iloc[r, c_end]) and (r+1 < df_raw.shape[0] and pd.isna(df_raw.iloc[r+1, c_end])):
                        break
                    c_end += 1
                
                if c_end == c:
                    c_end = c + 1
                    
                # 2. Cari Batas Bawah Tabel
                r_end = r
                while r_end < df_raw.shape[0]:
                    # Jika satu baris penuh kosong (di rentang kolom tabel ini), anggap itu batas bawah
                    if df_raw.iloc[r_end, c:c_end].isna().all():
                        break
                    r_end += 1
                    
                # 3. Potong Dataframe sesuai batas
                df_block = df_raw.iloc[r:r_end, c:c_end].copy()
                
                # 4. Tentukan Baris Header
                if len(df_block) > 1:
                    # Jika baris pertama hanya berisi 1 teks (judul tabel besar), pakai baris kedua sbg kolom
                    if df_block.iloc[0].notna().sum() == 1:
                        df_block.columns = df_block.iloc[1].fillna("").astype(str).str.strip()
                        df_block = df_block.iloc[2:]
                    else:
                        df_block.columns = df_block.iloc[0].fillna("").astype(str).str.strip()
                        df_block = df_block.iloc[1:]
                
                # 5. Pembersihan Akhir
                df_block.dropna(how='all', inplace=True)
                df_block = df_block.loc[:, ~df_block.columns.str.lower().isin(['nan', 'none', ''])]
                df_block.reset_index(drop=True, inplace=True)
                
                return df_block
                
    return pd.DataFrame() # Kembalikan dataframe kosong jika keyword tidak ketemu

def load_psak117_data(uploaded_file):
    try:
        # --- 1. PROSES TABEL ATAS (DATA INPUT - HEADER) ---
        header_idx = find_correct_header_row(uploaded_file, "DATA INPUT - HEADER", "BookDate")
        df_header_full = pd.read_excel(uploaded_file, sheet_name="DATA INPUT - HEADER", header=header_idx)
        
        cut_idx = None
        for idx, row in df_header_full.iterrows():
            if row.astype(str).str.contains("TEMPLATE GMM", case=False, na=False).any():
                cut_idx = idx
                break
                
        df_header = df_header_full.iloc[:cut_idx].copy() if cut_idx is not None else df_header_full.copy()
        df_header.dropna(how='all', inplace=True)
        df_header.index += 1
        df_header.columns = df_header.columns.str.strip()
        df_header.drop(columns=[c for c in df_header.columns if "unnamed" in str(c).lower()], errors="ignore", inplace=True)

        # --- 2. PROSES TABEL BAWAH (TEMPLATE GMM) ---
        gmm_idx = find_correct_header_row(uploaded_file, "DATA INPUT - HEADER", "GroupType")
        if gmm_idx != 0:
            df_gmm = pd.read_excel(uploaded_file, sheet_name="DATA INPUT - HEADER", header=gmm_idx)
            df_gmm.dropna(how='all', inplace=True)
            df_gmm.index += 1
            df_gmm.columns = df_gmm.columns.str.strip()
            df_gmm.drop(columns=[c for c in df_gmm.columns if "unnamed" in str(c).lower()], errors="ignore", inplace=True)
        else:
            df_gmm = pd.DataFrame()

        # --- 3. PROSES DATA DETAIL ---
        detail_idx = find_correct_header_row(uploaded_file, "DATA INPUT - DETAIL", "A_PolicyNo")
        if detail_idx != 0:
            df_detail = pd.read_excel(uploaded_file, sheet_name="DATA INPUT - DETAIL", header=detail_idx)
            df_detail.dropna(how='all', inplace=True)
            df_detail.columns = df_detail.columns.str.strip()
            df_detail.index += 1
        else:
            df_detail = pd.DataFrame()
       
        # --- 4. PROSES MULTI-TABEL ASUMSI ---
        # df_asumsi_raw = pd.read_excel(uploaded_file, sheet_name="ASUMSI", header=None)
        
        # 4a. Ekstrak Tabel TMI secara eksplisit (Range E3:W117)
        try:
            # skiprows=2 (melewati baris 1 dan 2, sehingga baris 3 otomatis jadi Header)
            # nrows=114 (mengambil data dari baris 4 sampai 117)
            # usecols="E:W" (hanya mengambil kolom E sampai W)
            asumsi_tmi = pd.read_excel(
                uploaded_file, 
                sheet_name="ASUMSI", 
                usecols="E:W", 
                skiprows=4, 
                nrows=114 
            )
            # Bersihkan nama kolom
            asumsi_tmi.columns = asumsi_tmi.columns.astype(str).str.strip()
            asumsi_tmi.dropna(how='all', inplace=True)
            asumsi_tmi.index += 1
        except Exception as e:
            asumsi_tmi = pd.DataFrame()

        # 4b. Ekstrak Tabel RATE IBPA (Z4:BG36) secara eksplisit
        try:
            # skiprows=3 (melewati baris 1-3, sehingga baris 4 menjadi header)
            # nrows=33 (jarak dari baris 4 sampai 36 adalah 33 baris)
            # usecols="Z:BG" (rentang kolom Z sampai BG)
            asumsi_ibpa = pd.read_excel(
                uploaded_file, 
                sheet_name="ASUMSI", 
                usecols="Z:BG", 
                skiprows=3, 
                nrows=33 
            )
            asumsi_ibpa.dropna(how='all', inplace=True)
            asumsi_ibpa.reset_index(drop=True, inplace=True)
            asumsi_ibpa.index += 1  # Indeks mulai dari 1
        except:
            asumsi_ibpa = pd.DataFrame()

        # --- 4c. Ekstrak Tabel LAPSE RATE MONTHLY (BM4:CQ19) ---
        try:
            # BM4:CQ19 -> skiprows=3, nrows=16, usecols="BM:CQ"
            asumsi_lapse_m = pd.read_excel(uploaded_file, sheet_name="ASUMSI", usecols="BM:CQ", skiprows=3, nrows=16)
            asumsi_lapse_m.dropna(how='all', inplace=True)
            asumsi_lapse_m.reset_index(drop=True, inplace=True)
            asumsi_lapse_m.index += 1
        except:
            asumsi_lapse_m = pd.DataFrame()

        # --- 4d. Ekstrak Tabel LAPSE RATE YEARLY (BM24:CQ39) ---
        try:
            # BM24:CQ39 -> skiprows=23, nrows=16, usecols="BM:CQ"
            asumsi_lapse_y = pd.read_excel(uploaded_file, sheet_name="ASUMSI", usecols="BM:CQ", skiprows=23, nrows=16)
            asumsi_lapse_y.dropna(how='all', inplace=True)
            asumsi_lapse_y.reset_index(drop=True, inplace=True)
            asumsi_lapse_y.index += 1
        except:
            asumsi_lapse_y = pd.DataFrame()

        # --- 4e. Ekstrak Tabel LAPSE RATE MONTHLY 2 (BM77:CR108) ---
        try:
            # BM77:CR108 -> skiprows=76, nrows=32, usecols="BM:CR"
            asumsi_lapse_m2 = pd.read_excel(uploaded_file, sheet_name="ASUMSI", usecols="BM:CR", skiprows=76, nrows=32)
            asumsi_lapse_m2.dropna(how='all', inplace=True)
            asumsi_lapse_m2.reset_index(drop=True, inplace=True)
            asumsi_lapse_m2.index += 1
        except:
            asumsi_lapse_m2 = pd.DataFrame()

        # --- 4f. Ekstrak Tabel RATE INFLASI (BJ4:BK39) secara eksplisit
        try:
            # skiprows=3 (melewati 3 baris teratas, baris 4 menjadi header)
            # nrows=35 (jarak dari baris 4 sampai 39 adalah 35 baris)
            # usecols="BJ:BK" (rentang kolom BJ sampai BK)
            asumsi_inflasi = pd.read_excel(
                uploaded_file, 
                sheet_name="ASUMSI", 
                usecols="BJ:BK", 
                skiprows=3, 
                nrows=35 
            )
            asumsi_inflasi.dropna(how='all', inplace=True)
            asumsi_inflasi.reset_index(drop=True, inplace=True) #
            asumsi_inflasi.index += 1  # Indeks mulai dari 1
            # Konversi kolom kunci menjadi format yang sama dengan Tanggal_Mulai_Polis
            # asumsi_inflasi.iloc[:, 0] = pd.to_datetime(asumsi_inflasi.iloc[:, 0], errors='coerce')
        except:
            asumsi_inflasi = pd.DataFrame()

        return {
            "header": df_header,
            "template_gmm": df_gmm,
            "detail": df_detail,
            "asumsi_tmi": asumsi_tmi,
            "asumsi_ibpa": asumsi_ibpa,
            "asumsi_inflasi": asumsi_inflasi,
            "asumsi_lapse_m": asumsi_lapse_m,
            "asumsi_lapse_y": asumsi_lapse_y,
            "asumsi_lapse_m2": asumsi_lapse_m2,
            "status": True,
            "message": "Sukses mengekstrak tabel data & memisahkan blok tabel asumsi!"
        }
        
    except Exception as e:
        return {
            "status": False,
            "message": f"Gagal memproses data. Error: {str(e)}"
        }