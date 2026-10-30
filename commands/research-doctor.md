---
description: Kiểm tra (và tuỳ chọn cài) môi trường cho bộ công cụ research
argument-hint: [fix]
---
Chạy `python3 ${CLAUDE_PLUGIN_ROOT}/skills/tech-research/scripts/doctor.py` và tóm tắt bằng tiếng Việt mục nào còn thiếu.

Nếu $ARGUMENTS là `fix`, hoặc người dùng muốn cài phần thiếu: chạy doctor.py **không kèm `--yes`** để lấy danh sách lệnh, nêu danh sách cho người dùng, và chỉ khi họ đồng ý rõ ràng mới chạy lại với `--fix --yes`. Đăng nhập (`notebooklm login`, `gh auth login`) luôn do người dùng tự làm.
