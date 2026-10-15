Exercise 2 — Dừng chờ người duyệt bằng `interrupt()`
Ở Exercise 1, human_approval chỉ in ra một dòng rồi kết thúc. Trong exercises/exercise_2_hitl.py, bạn biến nó thành một điểm dừng thật: graph đứng lại, cho người xem diff và lý do của LLM, chờ họ chọn approve, reject hoặc edit, rồi mới đi tiếp.

Bản chất của một lần "dừng"
Một chương trình bình thường muốn hỏi người thì gọi input() và chặn tại chỗ. Cách này không hợp với agent chạy lâu: người duyệt có thể trả lời sau vài phút hoặc vài giờ, tiến trình có thể bị tắt giữa chừng, và Exercise 5 còn phải trả lời qua trình duyệt chứ không qua terminal. LangGraph giải quyết bằng cách lưu trạng thái graph lại rồi trả quyền điều khiển cho bên gọi. Bên gọi hỏi người theo cách nào cũng được, sau đó đưa câu trả lời vào để graph chạy tiếp từ đúng chỗ đã dừng.

interrupt(), Command(resume=...), checkpointer và thread_id
interrupt(payload): gọi bên trong node. Graph dừng, và payload xuất hiện trong kết quả trả về dưới khoá "__interrupt__". Khi graph chạy tiếp, chính lời gọi interrupt() đó trả về giá trị người dùng gửi vào.
Command(resume=giá_trị): thứ bạn truyền vào app.invoke(...) để tiếp tục graph đang dừng.
Checkpointer: nơi lưu trạng thái giữa hai lần invoke. Không có checkpointer thì không có gì để tiếp tục; README ghi rõ quên checkpointer=... sẽ làm interrupt() ném GraphInterrupt thay vì dừng. Bài này dùng MemorySaver, chỉ lưu trong bộ nhớ.
thread_id: định danh của một phiên. Lần invoke đầu và mọi lần resume phải dùng cùng cfg = {"configurable": {"thread_id": ...}}, nếu không graph sẽ chạy lại từ đầu.
Một chi tiết dễ gây lỗi: node chạy lại từ đầu
Khi resume, node chứa interrupt() được chạy lại từ dòng đầu tiên, chỉ khác là lần này interrupt() trả về câu trả lời thay vì dừng. Vì thế mọi side-effect đặt trước interrupt() trong cùng node sẽ chạy hai lần. Đây là lý do khung bài tách việc đăng comment sang node commit riêng: node_human_approval chỉ hỏi và ghi lựa chọn vào state, còn node_commit đăng comment khi human_choice == "approve". Hãy giữ cách tách này, đừng gọi post_review_comment trong node có interrupt().

Cũng để ý rằng ở bài này, node_commit chỉ đăng khi bạn chọn approve; reject và edit đều đi vào nhánh bỏ qua và trả rejected. Việc dùng feedback để LLM viết lại review là bonus challenge 4.

Làm bài
1. Trong node_human_approval, gọi interrupt(...) với payload có đủ các khoá mà comment TODO liệt kê: kind là "approval_request", confidence, confidence_reasoning, summary, comments (danh sách c.model_dump()) và diff_preview (2000 ký tự đầu của diff). prompt_human() đọc đúng các khoá này để vẽ panel, nên thiếu khoá nào sẽ lỗi ngay khi hiển thị. Trả về human_choice và human_feedback từ câu trả lời.
2. Trong build_graph, compile với checkpointer=MemorySaver().
3. Trong main(), viết vòng lặp resume: lấy payload, đưa cho prompt_human(), rồi invoke lại với Command(resume=...) và cùng cfg. Dùng while chứ không dùng if, vì sau một lần resume graph có thể dừng thêm lần nữa.
1. Chạy với PR #1:
uv run python exercises/exercise_2_hitl.py --pr https://github.com/VinUni-AI20k/PR-Demo/pull/1
Copy
Approve là đăng comment thật
Chọn approve sẽ đăng một comment thật lên PR #1 của VinUni-AI20k/PR-Demo dưới username của bạn. Hãy kiểm tra nội dung trong panel trước khi gõ approve.

Checkpoint
Terminal dừng lại với một panel viền xanh tên Approval request, hiện confidence, lý do, summary, danh sách comment đề xuất và phần diff preview, rồi hỏi Choice (approve/reject/edit)?. Gõ approve: bạn thấy dòng ✓ posted comment to ... và phần Done in committed. Mở PR #1 trên GitHub, comment ### Automated review (confidence ...) xuất hiện dưới tên bạn. Thử chạy lại và chọn reject: terminal in skipping comment và kết quả là rejected, không có comment mới.

Nhánh approve chỉ phù hợp khi LLM đã gần chắc chắn. Với PR như #2, hỏi "duyệt hay không" là chưa đủ; Exercise 3 xử lý trường hợp đó.

