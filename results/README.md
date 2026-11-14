# Kết quả và minh chứng

| Nội dung | File |
|---|---|
| Metrics A/B/C và thí nghiệm cải tiến, tách theo benchmark/split | [retrieval_metrics.csv](retrieval_metrics.csv) |
| Thống kê ingestion, phiên bản, thời gian và chi phí | [ingestion_summary.json](ingestion_summary.json) |
| Coherence, metadata, grounding; không gộp các cohort khác nhau | [audit_summary.csv](audit_summary.csv) |
| Nhãn audit và lý do | [coherence](../starter/results/checkpoint_audit/coherence_labels.csv), [metadata](../starter/results/checkpoint_audit/metadata_labels.csv), [grounding](../starter/results/checkpoint_audit/grounding_labels.csv) |
| Tham số, giả thuyết, kết quả A/B/C | [experiment_log.csv](../artifacts/experiment_log.csv) |
| So sánh cải tiến D/E/F và C gốc | [improvement_log.csv](../artifacts/improvement_log.csv) |
| Hash/freeze/selection và run metadata | [v1](../starter/results/roshidere/benchmark/), [v2](../starter/results/roshidere-v2/) |

Full-text top-3 traces và evidence quotes được giữ local. [artifact_references.json](../data/artifact_references.json) cung cấp cùng record, ranking, source/page/offset và hash, thay trường text bằng tham chiếu. Cách khôi phục từ bản PDF hợp lệ: [data/access.md](../data/access.md).

Các điểm định tính có rubric và lý do. Benchmark v1: 15 dev/5 test. Thí nghiệm v2: cùng 15 dev và 10 test mới, chọn cấu hình trước khi xem test. Không gộp tỷ lệ của hai tập test.
