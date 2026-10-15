Exercise 1 — Định tuyến theo confidence
Bạn mở exercises/exercise_1_confidence.py và dựng graph đầu tiên: lấy PR, cho LLM phân tích, rồi rẽ vào một trong ba node cuối theo confidence. Ở bài này chưa có HITL; ba node cuối chỉ in ra nhánh nào được chọn.

Câu hỏi bài này trả lời
Mọi thứ phía sau đều dựa vào một quyết định: PR này có cần người hay không. Nếu bước phân loại sai, các bài sau dù viết đúng cũng sẽ chạy nhầm nhánh. Vì vậy trước khi nghĩ đến chuyện dừng lại hay hỏi người, bạn cần một graph rẽ nhánh ổn định, và cần thấy tận mắt hai PR mẫu đi vào hai nhánh khác nhau.

Hai PR mẫu nằm ở repo private <https://github.com/VinUni-AI20k/PR-Demo> (bạn cần quyền truy cập để mở các link dưới đây):

PR	Nội dung	Nhánh mong đợi
#1	Add task priority field — khoảng 40 dòng, một câu hỏi mở về migration schema	human_approval (~65%)
#2	Add user login + cloud sync — hash mật khẩu bằng MD5, lưu token dạng plaintext, SQL injection trong Storage.add, user_id hard-code, không có test	escalate (<58%)
Confidence và ba ngưỡng
Confidence ở đây là số từ 0 đến 1 mà LLM tự báo cáo về độ chắc chắn rằng review của nó đầy đủ và đúng. Nó không phải xác suất đã được hiệu chỉnh; đó là lý do bonus challenge 2 yêu cầu bạn kiểm tra xem model tự tin quá mức hay chưa đủ. Model trả về confidence qua trường confidence của PRAnalysis, kèm confidence_reasoning giải thích vì sao chọn con số đó.

Ngưỡng nằm trong common/schemas.py:

AUTO_APPROVE_THRESHOLD = 0.73   # >= 73% → no human, agent commits the comment directly
ESCALATE_THRESHOLD = 0.58       # < 58% → escalate: agent asks the reviewer specific questions
Copy
Từ 0.73 trở lên đi auto_approve, dưới 0.58 đi escalate, còn lại đi human_approval.

Tin số trong schemas.py
Comment TODO trong exercise_1_confidence.py còn ghi ngưỡng cũ (0.85 và 0.60), docstring Exercise 3 ghi "< 60%". Hãy luôn import và dùng AUTO_APPROVE_THRESHOLD, ESCALATE_THRESHOLD thay vì gõ số trực tiếp.

Vì sao dùng structured output
node_analyze phải gọi LLM qua get_llm().with_structured_output(PRAnalysis). Thay vì nhận một đoạn văn tự do rồi tự bóc tách, bạn nhận về một object Pydantic có sẵn summary, risk_factors, comments, confidence, confidence_reasoning và escalation_questions. Nhờ vậy node_route chỉ cần đọc state["analysis"].confidence, và các bài sau đưa thẳng các trường này vào payload cho người duyệt. Đây là contract mà toàn bộ Lab dựa vào, nên hãy giữ nguyên PRAnalysis; thư mục common/ được cung cấp sẵn và không cần sửa.

Làm bài
1. Trong node_analyze, tạo llm có structured output như trên. Gọi llm.invoke(...) với một message system (vai senior reviewer) và một message user chứa state['pr_title'] và state['pr_diff']. Bọc lời gọi trong console.status(...) như comment gợi ý, rồi trả về {"analysis": analysis}.
2. Trong node_route, đọc confidence, so với hai ngưỡng, trả về {"decision": ...} với một trong ba giá trị auto_approve, human_approval, escalate. Node chỉ trả quyết định; việc rẽ nhánh là của graph.
3. Trong build_graph, thêm 6 node, nối START → fetch_pr → analyze → route, dùng add_conditional_edges trên "route" với mapping cho cả ba nhánh, rồi nối mỗi node cuối tới END.
4. Chạy cả hai PR:
uv run python exercises/exercise_1_confidence.py --pr https://github.com/VinUni-AI20k/PR-Demo/pull/1
uv run python exercises/exercise_1_confidence.py --pr https://github.com/VinUni-AI20k/PR-Demo/pull/2
Copy
Nếu kẹt ở bước 3, hãy xem cách Exercise 2 nối graph: hàm điều kiện chỉ đọc lại giá trị route đã ghi vào state.

Checkpoint
Bài đạt khi hai PR in ra hai nhánh khác nhau. Với PR #1 bạn thấy dòng ✓ HUMAN APPROVAL, phần Final in action = pending_human_approval. Với PR #2 bạn thấy ✓ ESCALATE và action = pending_escalation. Dòng confidence = ... cho bạn biết model đặt PR ở đâu so với ngưỡng.

LLM không cho kết quả giống hệt mỗi lần chạy. Nếu PR #2 cứ bị chấm quá cao và không vào escalate, README cho phép tạm nâng ESCALATE_THRESHOLD lên 0.70 để ép nhánh. Khi đã thấy nhánh human_approval hoạt động, bạn sẵn sàng biến placeholder của nó thành một điểm dừng thật ở Exercise 2.
