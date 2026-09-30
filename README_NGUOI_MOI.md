# Hướng dẫn cài đặt cho người mới

> Tài liệu này dành cho máy Windows mới, chưa cài công cụ lập trình. Làm lần lượt từ trên xuống. Bạn không cần biết Python hay R để làm theo.

## Hệ thống này làm gì?

Ứng dụng đọc dữ liệu khoản vay Freddie Mac, xử lý dữ liệu, chạy các mô hình rủi ro vỡ nợ/trả trước, rồi mở dashboard trong trình duyệt.

**Lưu ý quan trọng:** tải mã nguồn từ GitHub thôi chưa đủ để xem dashboard. Các bộ dữ liệu và kết quả mô hình có dung lượng lớn nên không nằm trong nhánh Git. Bạn cần lấy dữ liệu Freddie Mac và chạy các bước xử lý bên dưới, hoặc nhờ nhóm cung cấp bộ dữ liệu/kết quả đã được chuẩn bị đúng phiên bản.

## 1. Chuẩn bị trên máy Windows

Bạn cần kết nối Internet và vài GB dung lượng trống. Cài các chương trình sau:

1. **Git** để tải dự án: [tải Git cho Windows](https://git-scm.com/install/windows). Khi cài đặt, có thể giữ các lựa chọn mặc định.
2. **Python 3.12 bản 64-bit**: mở [trang tải Python cho Windows](https://www.python.org/downloads/windows/), chọn bản Python 3.12 mới nhất và chọn Windows installer 64-bit. Trong cửa sổ cài đặt, đánh dấu **Add Python to PATH** trước khi bấm Install.
3. **R 4.6.1 bản 64-bit**: tải từ [CRAN](https://cran.r-project.org/bin/windows/base/). Giữ tùy chọn cài các package được đề xuất. Dự án yêu cầu package `survival` phiên bản **3.8-6**; hướng dẫn kiểm tra ở bước 6.
4. **Visual Studio Code** (không bắt buộc, nhưng giúp mở thư mục dự án): [tải VS Code](https://code.visualstudio.com/Download).

## 2. Tải mã nguồn dự án

Mở **PowerShell**: bấm Start, gõ `PowerShell`, rồi mở ứng dụng Windows PowerShell. Dán từng dòng sau và nhấn Enter:

```powershell
git clone --branch frontend-kha --single-branch https://github.com/nguynhoanggiaviethung-beep/mortgage-risk-survival-analysis.git
cd mortgage-risk-survival-analysis
```

Nếu GitHub báo không có quyền truy cập, hãy nhờ người quản lý dự án cấp quyền cho tài khoản GitHub của bạn. Nếu dự án đã được tải về trước đó, chỉ cần mở PowerShell tại thư mục dự án.

## 3. Cài thư viện của dự án

Trong PowerShell, tại thư mục dự án, chạy lần lượt:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Khi thành công, đầu dòng PowerShell thường có chữ `(.venv)`. Nếu Windows báo rằng không cho chạy `Activate.ps1`, chỉ cho phép trong cửa sổ PowerShell hiện tại rồi thử lại:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Cài thư viện có thể mất vài phút. Giữ kết nối Internet cho đến khi lệnh kết thúc.

## 4. Tải dữ liệu Freddie Mac

Dữ liệu được tải từ [trang Freddie Mac Single-Family Loan-Level Dataset](https://www.freddiemac.com/research/datasets/sf-loanlevel-dataset). Freddie Mac yêu cầu đăng ký và đăng nhập Clarity Data Intelligence để tải dữ liệu; hãy đọc điều khoản sử dụng trên trang đó. Không đưa tài khoản hoặc mật khẩu vào mã nguồn.

Tải **sample data** cho từng vintage từ **2016 đến 2026**, bao gồm cả dữ liệu origination và monthly performance. Đặt ZIP vào thư mục `src/data/` trong dự án và đặt đúng tên như sau:

```text
src/data/sample_2016.zip
src/data/sample_2017.zip
src/data/sample_2018.zip
src/data/sample_2019.zip
src/data/sample_2020.zip
src/data/sample_2021.zip
src/data/sample_2022.zip
src/data/sample_2023.zip
src/data/sample_2024.zip
src/data/sample_2025.zip
src/data/sample_2026.zip
```

Mỗi ZIP phải chứa đúng hai tệp của năm đó, ví dụ `sample_orig_2016.txt` và `sample_perf_2016.txt`. Không giải nén thủ công. Nếu tên file tải về khác, chỉ đổi tên ZIP khi bên trong vẫn có hai tệp đúng tên và đúng năm như trên.

Nếu trang Freddie Mac chỉ cung cấp dữ liệu mới hơn và các bước kiểm định ở dưới báo sai số dòng, **dừng tại đó**. Không sửa số kiểm định hoặc gộp dữ liệu khác phiên bản; liên hệ người quản lý dự án để xác nhận bộ dữ liệu phù hợp với nghiên cứu. Dữ liệu Freddie Mac có thể được cập nhật theo thời gian.

## 5. Tạo dữ liệu phân tích

Trong PowerShell vẫn ở thư mục dự án và đang thấy `(.venv)`, chạy **từng lệnh một**, chờ lệnh trước chạy xong mới chạy lệnh kế tiếp:

```powershell
python scripts\process_all.py
python scripts\check_data.py
python scripts\clean_all.py
python scripts\final_data_validation.py
python scripts\audit_event_conflicts.py
python scripts\build_event_maps_all.py
python scripts\audit_loan_age_duration.py
python scripts\build_survival_duration_all.py
python scripts\build_model_datasets_all.py
```

`process_all.py` cần tìm đủ ZIP từ `sample_2016.zip` đến `sample_2026.zip`. Hãy kiểm tra phần tổng kết của mỗi lệnh. Nếu thấy `FAILED`, `Missing ZIP`, hoặc lỗi màu đỏ, hãy dừng lại và xử lý nguyên nhân trước khi chạy bước kế tiếp.

## 6. Kiểm tra R và package survival

Trong PowerShell, kiểm tra R đã được cài:

```powershell
Rscript --version
Rscript -e "packageVersion('survival')"
```

Kết quả mong đợi là R **4.6.1** và `survival` **3.8.6** (R hiển thị phiên bản package là `3.8.6`, tương ứng `3.8-6`). Nếu PowerShell không tìm thấy `Rscript`, R chưa được cài đúng hoặc chưa mở lại PowerShell sau khi cài. Nếu phiên bản khác, dừng và nhờ người quản lý dự án hướng dẫn cài đúng phiên bản; không dùng phiên bản mới nhất thay thế một cách tự động.

## 7. Chạy và xuất bản các mô hình

Kiểm tra đầu vào trước. Lệnh này chỉ kiểm tra và không chạy mô hình:

```powershell
python scripts\run_production.py preflight --group complete --rscript "C:\Program Files\R\R-4.6.1\bin\Rscript.exe"
```

Nếu R được cài ở chỗ khác, thay đường dẫn trên bằng vị trí `Rscript.exe` trên máy bạn. Nếu kết quả preflight có lỗi, không bỏ qua.

Khi preflight thành công, chạy toàn bộ mô hình:

```powershell
python scripts\run_production.py build --rscript "C:\Program Files\R\R-4.6.1\bin\Rscript.exe" --confirm-full-production
```

Đây là bước nặng và có thể mất nhiều phút. Để cửa sổ PowerShell mở. Khi kết thúc, lệnh in ra thư mục run có tên dạng `20260929T235303Z_ca7d0c1`. Dùng đúng tên được in trên máy của bạn trong hai lệnh tiếp theo:

```powershell
python scripts\run_production.py validate --run-id 20260929T235303Z_ca7d0c1
python scripts\run_production.py publish --run-id 20260929T235303Z_ca7d0c1 --confirm-publish
```

Thay `20260929T235303Z_ca7d0c1` bằng tên run vừa được tạo. Chỉ publish nếu validate báo `VALIDATED`. Sau publish, kết quả mới đã sẵn sàng cho dashboard.

## 8. Mở dashboard

Chạy:

```powershell
python -m streamlit run app/app.py
```

Trình duyệt thường tự mở. Nếu không, mở trình duyệt và vào [http://localhost:8501](http://localhost:8501). Dashboard có các trang Tổng quan, Rủi ro danh mục, Yếu tố rủi ro, Tra cứu khoản vay và Kết quả mô hình.

Khi dùng xong, quay lại PowerShell và nhấn **Ctrl+C** để tắt dashboard. Lần sau chỉ cần mở lại PowerShell tại thư mục dự án, bật môi trường và chạy dashboard:

```powershell
cd mortgage-risk-survival-analysis
.\.venv\Scripts\Activate.ps1
python -m streamlit run app/app.py
```

## Lỗi thường gặp

| Thông báo | Cách xử lý |
|---|---|
| `No module named streamlit` | Mở PowerShell tại thư mục dự án, bật `.venv`, rồi chạy `python -m pip install -r requirements.txt`. |
| `git is not recognized` | Cài Git for Windows, đóng PowerShell, mở lại rồi thử lệnh tải dự án. |
| `py is not recognized` hoặc `No suitable Python runtime found` | Cài Python 3.12 bản 64-bit, chọn **Add Python to PATH**, rồi mở PowerShell mới. |
| `Rscript is unavailable` | Cài R 4.6.1 hoặc dùng đường dẫn đầy đủ tới `Rscript.exe` trong các lệnh production. |
| `sample_20XX.zip` bị thiếu | Đặt đúng ZIP vào `src/data/` và kiểm tra chính tả tên file. Cần đủ năm 2016–2026. |
| Preflight báo sai số dòng hoặc sai phiên bản dữ liệu | Dữ liệu tải về không khớp bản nghiên cứu đã khóa. Dừng lại và hỏi người quản lý dự án; không bỏ qua kiểm định. |
| Trình duyệt không mở dashboard | Để cửa sổ PowerShell chạy, rồi tự mở `http://localhost:8501`. |

## Dữ liệu nào không nằm trên GitHub?

Các file ZIP Freddie Mac, dữ liệu trung gian `.parquet`, môi trường `.venv` và một số kết quả lớn được loại khỏi Git để tránh chia sẻ nhầm dữ liệu hoặc đẩy file rất lớn lên kho mã nguồn. Không xóa các thư mục dữ liệu nếu chưa có bản sao. Nếu nhóm đã có bộ dữ liệu/kết quả hợp lệ, có thể xin nhóm cung cấp theo kênh được phép thay vì chạy lại toàn bộ từ đầu.

## Liên kết chính thức

- [Freddie Mac Single-Family Loan-Level Dataset](https://www.freddiemac.com/research/datasets/sf-loanlevel-dataset)
- [Python cho Windows](https://www.python.org/downloads/windows/)
- [R cho Windows (CRAN)](https://cran.r-project.org/bin/windows/base/)
- [Git for Windows](https://git-scm.com/install/windows)
- [Visual Studio Code](https://code.visualstudio.com/Download)

