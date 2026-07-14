# PSAK 117 Actuarial Calculator Engine

Aplikasi berbasis web untuk otomatisasi perhitungan instrumen asuransi berdasarkan standar **PSAK 117 (IFRS 17)** menggunakan **Python** dan **Streamlit**. Aplikasi ini memproyeksikan arus kas masa depan, menghitung nilai kini (BEL), mengintegrasikan elemen risiko (RA), serta melacak pergerakan saldo CSM.

## Features
* **Data Ingestion**: Unggah langsung file Excel dengan format sheet standar (`HEADER` & `DETAIL`).
* **Assumption Engine**: Modul dinamis membaca tabel asumsi (`ASUMSI`) untuk *discounting rate* dan parameter aktuaria lainnya.
* **Core Actuarial Calculations**:
  * Proyeksi Cash Flow & Perhitungan *Best Estimate Liability* (BEL).
  * Perhitungan *Risk Adjustment* (RA) dan *Contractual Service Margin* (CSM).
* **Movement Roll-Forward**: Visualisasi tabel pergerakan dari saldo awal hingga saldo akhir.

## 💻 Cara Menjalankan Aplikasi

Pastikan Anda sudah berada di dalam folder proyek melalui Terminal / Command Prompt lalu ketikan : **py -m streamlit run app.py**