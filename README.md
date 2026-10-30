# rnd-research-toolkit

Plugin Claude Code cho team R&D: nghiên cứu một chủ đề công nghệ từ nhiều nguồn, phân tích có trích dẫn bằng NotebookLM, rồi viết báo cáo tiếng Việt kèm infographic.

## Gồm những skill nào

| Skill | Việc làm |
|---|---|
| `tech-research` | Quy trình chính: tìm nguồn (YouTube, Hacker News, Reddit, Stack Overflow, GitHub issues/changelog, docs/blog, arXiv), gắn nhãn nguồn, phân tích, kiểm chứng, lấy số liệu GitHub/pub.dev/npm/PyPI/crates.io, viết báo cáo + infographic |
| `youtube-search` | Tìm video YouTube bằng yt-dlp, lọc theo thời gian, tính tỉ lệ views/subscribers |
| `notebooklm-studio` | Đưa nguồn vào NotebookLM, hỏi đáp có trích dẫn, tạo podcast, mind map, flashcards, infographic |

## Cài đặt

```
/plugin install rnd-research-toolkit --marketplace kieuanhdev/rnd-research-toolkit
```

Claude Code cũ hơn 2.1.275 thì cài bằng hai lệnh:

```
/plugin marketplace add kieuanhdev/rnd-research-toolkit
/plugin install rnd-research-toolkit
```

## Nguồn dữ liệu

**Nguồn để đọc và phân tích** (khoảng 20–30 nguồn mỗi lần, không độn nguồn lạc đề):

| Nguồn | Cách lấy | Ghi chú |
|---|---|---|
| YouTube | `yt-dlp`, lọc theo thời gian | Có thống kê views/subscribers |
| Hacker News | API Algolia miễn phí | Chỉ giữ bài có bình luận; chủ đề hẹp thì HN ít, và đó cũng là một kết quả |
| Reddit | Tìm web `site:reddit.com` | Thường chỉ lấy được một phần, báo cáo sẽ ghi rõ |
| Stack Overflow | API Stack Exchange miễn phí (300 lượt/ngày) | Chỉ lấy câu hỏi đã có trả lời; hợp với thư viện, framework |
| GitHub issues | API GitHub, issue nhiều bình luận nhất của chính công cụ | Thấy lỗi thật người dùng gặp; đánh dấu bình luận của maintainer |
| Changelog | GitHub Releases (hoặc file CHANGELOG) | Biết công cụ còn phát triển không, phiên bản mới thay đổi gì |
| Tài liệu chính thức và blog kỹ thuật | Tìm web, rồi đọc trang | Gồm cả bài so sánh và kinh nghiệm chuyển đổi |
| arXiv | API arXiv, nạp cả file PDF | Chỉ khi chủ đề có nghiên cứu học thuật |

**Số liệu áp dụng:** GitHub (sao, issue/PR mở), pub.dev, npm, PyPI, crates.io.

**Nhãn nguồn:** mỗi nguồn được gắn đúng một nhãn (`Nhà cung cấp`, `Cộng đồng`, `Tài liệu chính thức`, `Nghiên cứu`, `Báo chí / tổng hợp`). Nhờ vậy báo cáo phân biệt được lời quảng cáo với ý kiến người dùng độc lập.

**Phân tích:** toàn bộ nguồn được nạp vào một notebook NotebookLM mới để hỏi đáp có trích dẫn. Nếu công cụ bạn hỏi không xuất hiện trong nguồn, báo cáo nói là "thiếu trong bộ nguồn", không kết luận là nó không tồn tại.

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

Cần câu trả lời nhanh thì dùng `/research-quick`. Bản này cũng là phương án dự phòng khi NotebookLM lỗi.

Mẹo: nói rõ bạn cần quyết định gì, kể tên các công cụ đang cân nhắc, và nêu ràng buộc của team. Một lần chạy mất khoảng 10–20 phút.

Báo cáo lưu ở `<Chủ đề>.md`, kèm thư mục `assets/<chủ-đề>/` (nguồn, phân tích, infographic).

## Kiểm tra môi trường

Chạy `/research-doctor` để biết máy còn thiếu gì và cách sửa.

## Lệnh nhanh

- `/research <chủ đề>`: nghiên cứu đa nguồn
- `/research-quick <chủ đề>`: bản nhanh, không qua NotebookLM, ít nguồn hơn
- `/research-update <báo cáo.md>`: cập nhật báo cáo cũ, chỉ tìm những gì mới từ ngày viết
- `/research-youtube <chủ đề>`: chỉ YouTube
- `/research-doctor`: kiểm tra môi trường

## Tuỳ chỉnh cho team

Tạo file `research.config.json` trong thư mục làm việc (tuỳ chọn):

```json
{ "team_name": "Team R&D ABC", "reviewer": "Tên người review", "output_dir": "reports" }
```

Mẫu báo cáo nằm trong `skills/tech-research/SKILL.md`, mục 9.
