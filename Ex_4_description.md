Exercise 4 — Audit trail SQLite và phát lại phiên
Trong exercises/exercise_4_audit.py, bạn làm cho mỗi phiên review để lại dấu vết có thể truy vấn: mỗi bước quan trọng ghi một dòng có cấu trúc vào bảng audit_events. Phần checkpointer bền vững và vòng resume đã được viết sẵn trong run().

Vì sao agent có quyền đăng comment cần audit trail
Khi agent tự đăng comment hoặc dừng chờ người, đội cần trả lời được những câu hỏi như: PR này đi nhánh nào, LLM tự tin bao nhiêu, ai đã duyệt, mỗi bước mất bao lâu. README đưa ra một truy vấn kiểm tra đáng chú ý: một PR rủi ro cao mà lại được tự động duyệt là điều không được xảy ra.

SELECT * FROM audit_events WHERE risk_level = 'high' AND decision = 'auto';
Copy
Muốn chạy được truy vấn như vậy, log phải là các cột riêng, không phải một chuỗi văn bản tự do.

Hai cơ chế lưu trữ trong cùng một file
Cơ chế	Mục đích	Dạng dữ liệu	Ai dùng
Checkpointer của LangGraph (AsyncSqliteSaver)	Resume sau khi tiến trình chết, time-travel	Blob trạng thái	Runtime LangGraph
Bảng audit_events	Nhật ký quyết định có cấu trúc	Cột riêng, truy vấn được	Auditor, con người
Cả hai nằm trong ./hitl_audit.db, file này được tạo tự động ở lần chạy đầu. Yêu cầu "ghi vào audit trail" của bài được đáp ứng bởi audit_events; checkpointer là phần có thêm nhờ dùng AsyncSqliteSaver. Lab dùng SQLite thay cho PostgreSQL để không cần cài đặt; theo README, schema dạng cột giúp các truy vấn trên AuditEntry chuyển sang Postgres được bằng cách đổi checkpointer và connection string.

Đọc các trường của AuditEntry
AuditEntry (trong common/schemas.py) có timestamp tự điền, agent_id, action, confidence, risk_level, reviewer_id, decision, reason và execution_time_ms. Cách điền đúng là trả lời câu hỏi: tại bước này, điều gì đã thực sự được biết? node_fetch_pr là ví dụ mẫu duy nhất, hãy đọc kỹ trước khi viết. Ở bước đó chưa có phân tích, nên confidence=0.0, risk_level="med" làm giá trị trung tính, decision="pending", reviewer_id để None vì chưa có người tham gia.

Ba quy tắc giúp bạn điền các node còn lại:

Từ khi có analysis, tính risk_level bằng risk_level_for(confidence); đừng tự đặt chuỗi.
decision chỉ nhận auto, approve, reject, edit, escalate hoặc pending. Node route là dòng đầu tiên có quyết định thật.
reviewer_id chỉ có giá trị ở các bước có người, lấy từ os.environ.get("GITHUB_USER").
Làm bài
Docstring đầu file liệt kê 10 TODO.

1. Viết thân hàm audit(): một lời gọi write_audit_event(thread_id=state["thread_id"], pr_url=state["pr_url"], entry=entry). Hàm này là async, nên nhớ await.
2. Ghi một AuditEntry cho mỗi node analyze, route, commit, auto_approve và synthesize. Đo thời gian bằng t0 đã có sẵn: int((time.monotonic() - t0) * 1000). Ở synthesize, dùng confidence mới refined.confidence.
3. Ghi hai entry cho mỗi node human_approval và escalate: một dòng trước interrupt() khi chưa ai trả lời, một dòng sau khi đã có câu trả lời. Dòng trước interrupt sẽ được ghi lại lần nữa khi node chạy lại lúc resume; đó là hệ quả của cơ chế bạn đã gặp ở Exercise 2, và bạn sẽ thấy nó khi replay.
4. Chạy một phiên, rồi phát lại bằng thread_id được in ra:
uv run python exercises/exercise_4_audit.py --pr https://github.com/VinUni-AI20k/PR-Demo/pull/1
uv run python -m audit.replay --thread <thread_id-in-ra-ở-trên>
uv run python -m audit.replay --list
Copy
Checkpoint
audit.replay --thread in ra một dòng thời gian, mỗi dòng có action, conf=, risk= (màu xanh, vàng hoặc đỏ), decision= và reviewer=. Một phiên PR #1 hoàn chỉnh đi qua fetch_pr, analyze, route, các dòng human_approval và commit. Ở dòng sau khi bạn trả lời, reviewer là username của bạn thay vì -. --list hiện bảng các phiên gần đây cùng worst_risk và số event.

Bạn có thể xem trực tiếp file bằng sqlite3 nếu máy có sẵn:

sqlite3 hitl_audit.db "SELECT action, confidence, decision, reviewer_id FROM audit_events ORDER BY id;"
Copy
Nếu schema bị cũ sau khi bạn sửa code, xoá hitl_audit.db để tạo lại từ đầu. Khi đã có build_graph(checkpointer) chạy được cùng audit trail, bạn có đủ phần lõi để gắn giao diện web ở Exercise 5.