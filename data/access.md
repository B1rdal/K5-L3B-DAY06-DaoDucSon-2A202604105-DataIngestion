# Nguồn dữ liệu và cách tái tạo

- Corpus: **Roshidere, Vol. 10 — Glucose Translations**, bản PDF tiếng Anh do học viên cung cấp.
- Bản local đã dùng: `F:\FDownload\MainDownload\Roshidere, Vol. 10 - Glucose Translations.pdf`.
- SHA-256: `dd48d3ff9c189bf4987e985e0b356edd5ea18b75fb010c92d3bb5b4c49b50fcf`.
- **Quyền xử lý và chia sẻ chưa được xác nhận.** Địa chỉ website ghi trong PDF không được coi là giấy phép. Chưa biết URL tải ban đầu hoặc văn bản cho phép. Học viên lựa chọn giữ corpus và ghi rõ điểm chưa hoàn thiện này.

PDF, nội dung trang/chunk, câu evidence và full-text trace được giữ local, không đưa vào bộ file dự kiến chia sẻ qua Git. `artifact_references.json` giữ source/page/offset, hash, câu hỏi tự soạn, metadata, ranking và số liệu; các trường text/evidence trích từ PDF được thay bằng tham chiếu. Không mã hóa/base64 toàn bộ sách để né việc loại nội dung nguồn.

Người chấm cần có **bản PDF được phép sử dụng**, khớp SHA-256 ở trên. Bài nộp này không cấp quyền truy cập hay tái phân phối tài liệu đó. Có thể đối chiếu trực tiếp bản local trên máy học viên hoặc thống nhất kênh cung cấp hợp lệ với giảng viên.

## Khôi phục minh chứng local từ một bản PDF được phép sử dụng

Từ `starter/`, sau khi cài dependencies:

```powershell
.\.venv\Scripts\python.exe scripts\submission.py restore --pdf "PATH_TO_AUTHORIZED_MATCHING_PDF"
```

Lệnh trích xuất lại PDF, áp dụng cùng chuẩn hóa/chọn trang và khôi phục 17 file evidence/trace từ offset. Tất cả file phải khớp SHA-256 bản đã chạy. File khác nội dung đã tồn tại sẽ không bị ghi đè.

Source ID và đường dẫn canonical của lần chạy gốc được giữ để khớp hash. Đối số `--pdf` là ánh xạ tới bản file thực tế trên máy đang kiểm tra; đường dẫn F: trong các record lưu trữ không được hiểu là luôn tồn tại trên máy khác.

Để kiểm tra trong thư mục khác thay vì repo:

```powershell
.\.venv\Scripts\python.exe scripts\submission.py restore --pdf "PATH_TO_AUTHORIZED_MATCHING_PDF" --output-root "PATH_TO_REVIEW_FOLDER"
```

Manifest, quy tắc đếm và danh sách trang nằm trong [manifest.json](manifest.json) và [pages.csv](pages.csv). Tiêu chí quyền dữ liệu vẫn **chưa đạt xác nhận**, dù kỹ thuật tái tạo và kiểm chứng đã có.
