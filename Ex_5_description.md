Exercise 5 — Giao diện duyệt bằng Streamlit
Ở bài cuối, bạn bọc graph của Exercise 1–4 trong một ứng dụng Streamlit (app.py ở gốc repo), để người duyệt điều khiển toàn bộ luồng trên trình duyệt thay vì terminal.

Cùng ba nhánh, ba trải nghiệm khác nhau
Graph không đổi, nhưng điều người duyệt cần thấy thì khác nhau theo nhánh:

Confidence	Nhánh	Người duyệt thấy gì
Cao	auto_approve	Thẻ thành công: confidence, summary của LLM và link xem comment trên GitHub. Người duyệt không phải làm gì.
Trung bình	human_approval	Thẻ duyệt: diff, lý do của LLM, danh sách comment và ba nút Approve / Reject / Edit.
Thấp	escalate	Thẻ escalation: risk factors được làm nổi bật và một form chứa các câu hỏi của LLM.
Streamlit chạy lại cả file sau mỗi lần bấm
Đây là điều cần nắm trước khi viết app.py. Mỗi lần người dùng bấm nút hoặc submit form, Streamlit chạy lại toàn bộ script từ trên xuống. Biến Python thường sẽ mất; chỉ st.session_state còn giữ giá trị. Vì vậy khung bài lưu thread_id, pr_url, interrupt_payload và final trong st.session_state.

Bài toán này khớp với cách interrupt() hoạt động. Lần chạy đầu, graph dừng và trả payload; app lưu payload rồi vẽ thẻ tương ứng. Ở lần chạy lại sau khi người dùng bấm nút, renderer trả về câu trả lời, và app gọi graph với Command(resume=...) trên cùng thread_id. Vì trạng thái graph nằm trong AsyncSqliteSaver chứ không nằm trong tiến trình, tải lại trang vẫn không làm mất phiên.

Phần nào đã có sẵn, phần nào là của bạn
Khung app.py đã viết sẵn phần "Main flow" ở cuối file. Khi form được submit, nó tạo thread_id mới bằng uuid4, gọi run_graph(), và nếu kết quả có "__interrupt__" thì lưu payload vào st.session_state.interrupt_payload. Ở mỗi lần chạy lại, nó xem payload["kind"]: approval_request thì gọi render_approval_card, còn lại thì gọi render_escalation_card. Renderer nào trả về khác None thì app resume graph với câu trả lời đó rồi gọi st.rerun().

Nói cách khác, khung đã lo phần điều phối. Hai renderer chỉ có một trách nhiệm: trả None khi người dùng chưa quyết định, và trả đúng dạng dữ liệu mà node đang chờ khi họ đã quyết định. Nếu renderer trả sai dạng, lỗi sẽ không hiện ở UI mà hiện khi node đọc câu trả lời sau interrupt(). Vì thế hãy đối chiếu lại với Exercise 4: node_human_approval đọc resp.get("choice") và resp.get("feedback"), còn node_escalate lưu nguyên dict câu trả lời vào escalation_answers.

Phần hiển thị kết quả cuối cũng đã có: final_action bắt đầu bằng auto hoặc committed thì hiện st.success, rejected thì hiện cảnh báo. Theo README, thẻ của nhánh auto_approve nên có confidence, summary của LLM và link xem comment trên GitHub; bạn bổ sung các thông tin này vào phần hiển thị cuối.

Làm bài
1. Ở đầu app.py, import build_graph từ lời giải Exercise 4 (from exercises.exercise_4_audit import build_graph), hoặc chép phần nối graph vào thẳng file.
2. Hoàn thành run_graph(): build graph với cp làm checkpointer; nếu resume_value là None thì await app.ainvoke({"pr_url": ..., "thread_id": ...}, cfg), ngược lại thì await app.ainvoke(Command(resume=resume_value), cfg); trả về result.
3. Trong render_approval_card(), cho mỗi nút trả về dict tương ứng, ví dụ {"choice": "approve", "feedback": feedback}. Đây đúng là dạng mà node_human_approval đọc bằng resp.get("choice").
4. Trong render_escalation_card(), vẽ một st.text_input cho mỗi câu trong payload["questions"], gom thành dict {câu_hỏi: câu_trả_lời} và trả về dict đó khi form được submit.
5. Điền sidebar "Recent sessions" từ bảng audit_events: hiện thread_id, pr_url, worst_risk và last_event. Hàm audit.replay.list_threads in bảng bằng Rich ra console chứ không trả dữ liệu, nên hãy dùng lại câu SQL trong đó qua common.db.db_conn, rồi hiển thị bằng Streamlit. Khi chọn một dòng, gán st.session_state.thread_id và rerun.
streamlit đã có trong pyproject.toml, nên chỉ cần kiểm tra lại dòng này. Chạy ứng dụng:

uv run streamlit run app.py
Copy
Checkpoint
Mở trang Streamlit, dán URL PR #1 và bấm Run review. Sau spinner, bạn thấy thẻ "Approval requested — confidence ..." với diff có thể mở rộng và ba nút. Bấm Approve: trang hiện thông báo thành công kèm thread_id và lệnh replay. Lặp lại với PR #2: bạn thấy thẻ "Strong escalation", hộp đỏ liệt kê risk factors và form câu hỏi; điền và bấm Submit answers thì review đã tinh chỉnh được đăng. Chạy audit.replay --thread với thread_id hiển thị trên trang: dòng thời gian khớp với những gì bạn vừa bấm. Thấy đủ ba điều này nghĩa là app đã sẵn sàng để nộp.