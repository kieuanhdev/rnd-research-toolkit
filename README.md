# rnd-research-toolkit

Plugin Claude Code cho team R&D: nghiên cứu một chủ đề công nghệ từ nhiều nguồn, phân tích có trích dẫn bằng NotebookLM, rồi viết báo cáo tiếng Việt kèm infographic.

## Gồm những skill nào

| Skill | Việc làm |
|---|---|
| `tech-research` | Quy trình chính: tìm nguồn (YouTube, Hacker News, Reddit, docs/blog, arXiv), gắn nhãn nguồn, phân tích, kiểm chứng, lấy số liệu GitHub/pub.dev/npm/PyPI/crates.io, viết báo cáo + infographic |
| `youtube-search` | Tìm video YouTube bằng yt-dlp, lọc theo thời gian, tính tỉ lệ views/subscribers |
| `notebooklm-studio` | Đưa nguồn vào NotebookLM, hỏi đáp có trích dẫn, tạo podcast, mind map, flashcards, infographic |

## Cài đặt

```
/plugin marketplace add <org>/rnd-research-toolkit
/plugin install rnd-research-toolkit
```

## Cài nhanh

```
/research-doctor        # kiểm tra máy còn thiếu gì
/research-doctor fix    # liệt kê lệnh cài, hỏi xác nhận, rồi cài
```

Tự cài được: `yt-dlp`, `notebooklm-py`, Playwright và Chromium. Bạn phải tự đăng nhập: `notebooklm login` (mở trình duyệt, đăng nhập Google) và tuỳ chọn `gh auth login`.

## Chuẩn bị thủ công (nếu không dùng `/research-doctor fix`)

| Việc | Cách làm | Bắt buộc |
|---|---|---|
| Python 3 | có sẵn trên hầu hết máy | Có |
| `yt-dlp` | `pipx install yt-dlp` | Có |
| `notebooklm-py` | `pipx install notebooklm-py`, rồi `notebooklm login` (mở trình duyệt) | Có |
| Playwright + Chrome | để xuất infographic thành ảnh | Có, nếu muốn có ảnh |
| `gh auth login` | tăng giới hạn số liệu GitHub từ 60 lên 5.000 lượt/giờ | Không |

Không cần API key hay token nào khác.

## Cách dùng

Mở Claude Code trong thư mục bạn muốn lưu báo cáo, rồi nói bình thường:

```
research công cụ kiểm thử tự động bằng AI cho app Flutter chạy cả Android và iOS
so sánh Patrol, Maestro và Detox cho app Flutter, nên chọn cái nào?
chỉ YouTube: research Claude Code skills vs MCP servers
```

Mẹo: nói rõ bạn cần quyết định gì, kể tên các công cụ đang cân nhắc, và nêu ràng buộc của team. Một lần chạy mất khoảng 10–20 phút.

Báo cáo lưu ở `<Chủ đề>.md`, kèm thư mục `assets/<chủ-đề>/` (nguồn, phân tích, infographic).

## Kiểm tra môi trường

Chạy `/research-doctor` để biết máy còn thiếu gì và cách sửa.

## Lệnh nhanh

- `/research <chủ đề>`: nghiên cứu đa nguồn
- `/research-youtube <chủ đề>`: chỉ YouTube
- `/research-doctor`: kiểm tra môi trường

## Tuỳ chỉnh cho team

Tạo file `research.config.json` trong thư mục làm việc (tuỳ chọn):

```json
{ "team_name": "Team R&D ABC", "reviewer": "Tên người review", "output_dir": "reports" }
```

Mẫu báo cáo nằm trong `skills/tech-research/SKILL.md`, mục 9.
