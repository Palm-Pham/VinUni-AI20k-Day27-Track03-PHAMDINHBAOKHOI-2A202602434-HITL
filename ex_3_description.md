Exercise 3 — Escalation: hỏi reviewer câu hỏi cụ thể
Khi confidence thấp, agent không nên đưa người duyệt một lựa chọn approve/reject. Trong exercises/exercise_3_escalation.py, agent hỏi những câu hỏi cụ thể để lấy thêm ngữ cảnh, rồi phân tích lại với câu trả lời đó.

Vì sao không chỉ hỏi "duyệt hay không"
Confidence thấp nghĩa là LLM thiếu thông tin để đánh giá, chứ chưa chắc PR sai. Ví dụ README nêu: "Why MD5? Is SYNC_URL meant to be HTTPS in production?". Đó là những điều chỉ tác giả hoặc người hiểu hệ thống mới trả lời được. Nếu chỉ hỏi approve/reject, người duyệt phải tự đọc lại toàn bộ diff và tự đoán LLM đang lo điều gì. Hỏi đúng câu thì người duyệt trả lời trong vài dòng, và LLM có ngữ cảnh để viết một review tốt hơn.

Hai node mới và một trường có sẵn
escalation_questions: trường có sẵn trong PRAnalysis, mặc định rỗng. LLM chỉ điền khi được dặn trong prompt.
node_escalate: dừng bằng interrupt() với kind="escalation". Câu trả lời trả về là một dict {câu_hỏi: câu_trả_lời}, được lưu vào state["escalation_answers"].
node_synthesize: gọi LLM lần thứ hai với diff, phân tích ban đầu và phần hỏi–đáp, rồi trả về một PRAnalysis mới thay cho bản cũ.
node_commit đã được viết để nhận hai đường vào: từ human_approval thì chỉ đăng khi approve, còn từ synthesize thì luôn đăng review đã tinh chỉnh, kèm phần hỏi–đáp ở cuối comment. Vì vậy bạn không cần sửa commit, chỉ cần nối đường cho đúng.

node_escalate đã có sẵn phần dự phòng: nếu LLM không sinh câu hỏi nào, nó dùng hai câu hỏi chung. Phần dự phòng giữ cho graph không hỏng, nhưng mục tiêu của bài là để LLM tự sinh câu hỏi bám vào diff.

Làm bài
1. Trong node_analyze, bổ sung system prompt theo comment TODO: khi confidence thấp, điền escalation_questions với 2–4 câu hỏi cụ thể, giàu ngữ cảnh, nêu rõ file hoặc đoạn nào trong diff. Comment TODO ghi mốc 60%; ngưỡng thật trong code là 0.58.
2. Trong node_escalate, gọi interrupt(...) với payload kind="escalation" gồm pr_url, confidence, confidence_reasoning, summary, risk_factors và questions. Trả về {"escalation_answers": answers}.
3. Trong node_synthesize, dựng prompt gồm diff gốc, phân tích ban đầu và từng cặp hỏi–đáp. Gọi get_llm().with_structured_output(PRAnalysis).invoke(...) và trả về {"analysis": refined}.
4. Trong build_graph, nối escalate → synthesize → commit. Vòng resume trong main() đã có sẵn.
5. Chạy với PR #2:
uv run python exercises/exercise_3_escalation.py --pr https://github.com/VinUni-AI20k/PR-Demo/pull/2
Copy
Checkpoint
Terminal hiện một panel viền vàng có tiêu đề Escalation conf=..., sau đó lần lượt in từng câu hỏi dạng Q: ... và chờ bạn gõ câu trả lời. Đọc các câu hỏi trước khi trả lời: chúng nên nhắc tới điểm cụ thể trong PR #2 như cách hash mật khẩu hay truy vấn trong Storage.add. Nếu bạn chỉ thấy hai câu hỏi chung của phần dự phòng, prompt ở bước 1 chưa đủ rõ.

Sau khi trả lời hết, phần Final in final_action = committed_after_escalation và final confidence = ... của bản phân tích mới. Trên GitHub, comment trên PR #2 có thêm phần "Reviewer answered escalation questions".

Lúc này agent đã đi đủ cả ba nhánh, nhưng mọi thứ vẫn chỉ nằm trong bộ nhớ. Tắt terminal là mất cả trạng thái lẫn dấu vết ai đã quyết định gì. Exercise 4 giải quyết hai việc đó.