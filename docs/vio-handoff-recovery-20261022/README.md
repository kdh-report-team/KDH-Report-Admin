# Khôi phục VIO handoff — 22/10/2026

Người dùng không mở được báo cáo mới `rpt_795f2c05f18e6eed68b2bb247e731317`, revision 1. New hiển thị lỗi kết nối hệ thống báo cáo tại `/auth/handoff/start`.

## Nguyên nhân và thay đổi

- Bundle thực tế là `provisional`, client `client_meta_sandbox`; grant đúng user active, revision 1–1. Không cần cấp lại quyền.
- Relay riêng `kdh-vio-relay-phase9-20261019` restart liên tục. Sau Docker restart, PostgreSQL thực tế là `192.168.0.2`; `pg_ip` trong phép kiểm tra cách ly của relay vẫn là `192.168.0.4` từ lần phục hồi trước.
- Đã sao lưu `private-relay-config-before.json`, đối chiếu identity Admin/PG/relay và cập nhật duy nhất `pg_ip` sang IP PG thực tế trong file bind mount `D:/KDH-Meta-Phase2B/20261016-132836-5c512a53/phase9-private-relay-4e536289/config.json`.
- Chỉ restart relay hiện hữu. Listener `192.168.96.2:8090` và upstream `192.168.0.3:8090` không đổi. Không rebuild, recreate, sửa OAuth, sync, review, publish hoặc cấp grant.

## Kiểm tra

- New → relay → Admin `/health`: HTTP 200.
- Relay và New đều không có default route; TCP tới PG `192.168.0.2:5432`, Meta gateway `192.168.0.10:8090`, Internet `1.1.1.1:443` bị từ chối ENETUNREACH (101).
- Browser đăng nhập Admin bằng tài khoản hiện hữu → handoff đúng report/revision → dashboard: PASS.
- KPI đọc từ dashboard: posts 15, reactions lifetime 81, comments lifetime 10; engagements và shares vẫn null. Timezone UTC.
- 1440px/390px: không overflow trang, không lỗi JavaScript. Sai revision: DENIED. Logout Viewer: PASS.
- Hash toàn bộ row Bundle và grants trước/sau giống nhau. Phiên kiểm tra đã logout.

Bằng chứng: [browser.json](browser.json), [recovery.json](recovery.json), [desktop](report-1440.png), [mobile](report-390.png).

## Giới hạn và rollback

IP PostgreSQL còn được Docker cấp động. Đây là khôi phục kết nối hiện tại; chưa phải sửa triệt để khả năng lệch IP kiểm tra sau một lần Docker restart khác. Cần thiết kế riêng cơ chế kiểm tra cách ly không phụ thuộc IP cũ, giữ nguyên nguyên tắc chỉ forward tới Admin.

Backup cấu hình chỉ dùng rollback sau khi đối chiếu topology thực tế; không chép IP cũ vào một topology đã đổi. Admin chính 8090 và các container ngoài VIO không được thay đổi trong lượt này.
