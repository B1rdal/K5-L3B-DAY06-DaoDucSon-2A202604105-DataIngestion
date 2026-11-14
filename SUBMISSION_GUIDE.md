# Hướng dẫn bài nộp — Đào Đức Sơn

**MSSV:** 2A202604105 · **Lớp:** L3B  
**Repo:** https://github.com/B1rdal/K5-L3B-Day06-DataIngestionEngineering

Setup và các lệnh chạy nằm trong [README.md](README.md#setup-bài-làm). File này là danh mục minh chứng của bài làm; nội dung đề bài gốc được giữ lại.

## Hồ sơ chính

| Nội dung | Minh chứng |
|---|---|
| Thông tin học viên | [STUDENT.md](STUDENT.md) |
| Báo cáo đủ năm khía cạnh, bảng kết quả và giới hạn | [2A202604105_DaoDucSon.md](report/individual/2A202604105_DaoDucSon.md) |
| Nguồn, quyền, snapshot và quy tắc đếm trang | [manifest.json](data/manifest.json), [pages.csv](data/pages.csv) |
| Code | [starter/src](starter/src/), [requirements.txt](starter/requirements.txt), [môi trường đã đo](starter/requirements-lock.txt) |
| Cấu hình | [A/B/C](starter/configs/roshidere.json), [cải tiến](starter/configs/roshidere-v2.json), [active](starter/configs/active.json) |
| Câu hỏi/split/protocol/freeze | [benchmark v1](benchmark/roshidere/), [v2](benchmark/roshidere-v2/) |
| Metrics, thời gian, chi phí và audit | [results](results/README.md), [experiment log](artifacts/experiment_log.csv) |
| Evidence và full-text trace được giữ local | [tham chiếu tái tạo](data/artifact_references.json), [cách truy cập](data/access.md) |

## Setup và chạy

Xem [hướng dẫn trong README.md](README.md#setup-bài-làm) để cài môi trường, bật database, khôi phục dữ liệu, tạo index A/B/C/F, truy vấn và kiểm tra.
