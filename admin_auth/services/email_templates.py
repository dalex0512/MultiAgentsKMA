"""Template email OTP — giao diện chuẩn Học viện KMA."""

from admin_auth.core.config import settings


def build_otp_email(full_name: str, otp: str) -> tuple[str, str, str]:
    """Returns (subject, plain_text, html)."""
    name = (full_name or "Quản trị viên").strip()
    minutes = settings.OTP_EXPIRE_MINUTES
    year = "2026"

    subject = f"[Học viện KMA] Mã xác thực đăng nhập — {otp}"

    plain = f"""HỌC VIỆN KỸ THUẬT MẬT MÃ
Academy of Cryptography Techniques

Xin chào {name},

Bạn vừa yêu cầu đăng nhập Cổng quản trị Chatbot trợ lý ảo đa tác tử.

Mã OTP của bạn: {otp}

Mã có hiệu lực trong {minutes} phút.
Nếu bạn không thực hiện đăng nhập, hãy bỏ qua email này.

Cảnh báo: Không chia sẻ mã OTP với bất kỳ ai. Cán bộ KMA không yêu cầu cung cấp mã qua điện thoại hay email khác.

---
Hệ thống trợ lý ảo — Học viện Kỹ thuật Mật mã
Email tự động, vui lòng không trả lời trực tiếp.
"""

    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Mã xác thực OTP</title>
</head>
<body style="margin:0;padding:0;background-color:#f0f3f7;font-family:'Segoe UI',Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#f0f3f7;">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:560px;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 8px 28px rgba(26,31,38,0.08);">
          <tr>
            <td height="4" style="background-color:#c9a227;font-size:0;line-height:4px;">&nbsp;</td>
          </tr>
          <tr>
            <td style="background-color:#9a1218;padding:28px 32px;text-align:center;">
              <p style="margin:0 0 8px;font-size:11px;letter-spacing:0.12em;text-transform:uppercase;color:#f5d77a;">
                Học viện Kỹ thuật Mật mã
              </p>
              <h1 style="margin:0;font-size:22px;font-weight:700;color:#ffffff;line-height:1.35;">
                Xác thực đăng nhập Quản trị
              </h1>
              <p style="margin:10px 0 0;font-size:13px;color:#ffe8e8;">
                Chatbot trợ lý ảo đa tác tử
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:32px 32px 24px;color:#1a1f26;font-size:15px;line-height:1.65;">
              <p style="margin:0 0 16px;">Xin chào <strong style="color:#9a1218;">{name}</strong>,</p>
              <p style="margin:0 0 20px;color:#5c6573;">
                Hệ thống ghi nhận yêu cầu đăng nhập vào <strong>Cổng quản trị</strong>.
                Vui lòng nhập mã OTP bên dưới trên trang xác thực để hoàn tất đăng nhập.
              </p>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td align="center" style="padding:8px 0 24px;">
                    <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="background-color:#fafbfc;border:2px dashed #c5ced8;border-radius:12px;">
                      <tr>
                        <td style="padding:22px 40px;text-align:center;">
                          <p style="margin:0 0 8px;font-size:12px;letter-spacing:0.1em;text-transform:uppercase;color:#5c6573;">
                            Mã xác thực (OTP)
                          </p>
                          <p style="margin:0;font-size:38px;font-weight:700;letter-spacing:0.32em;color:#9a1218;font-family:Consolas,'Courier New',monospace;">
                            {otp}
                          </p>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#f8fafc;border-radius:8px;border:1px solid #e8edf2;">
                <tr>
                  <td style="padding:14px 18px;font-size:14px;color:#5c6573;line-height:1.55;">
                    <strong style="color:#1a1f26;">Hiệu lực:</strong> {minutes} phút kể từ khi email được gửi.<br>
                    <strong style="color:#1a1f26;">Lưu ý:</strong> Mã chỉ dùng một lần cho phiên đăng nhập hiện tại.
                  </td>
                </tr>
              </table>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:20px;">
                <tr>
                  <td style="padding:14px 16px;background-color:#fff5f5;border-left:4px solid #d41f26;font-size:13px;color:#7a0e13;line-height:1.55;">
                    <strong>Không chia sẻ mã OTP</strong> với bất kỳ cá nhân hoặc đơn vị nào.
                    Cán bộ Học viện <strong>không</strong> yêu cầu cung cấp mã qua điện thoại, Zalo hay email khác.
                  </td>
                </tr>
              </table>
              <p style="margin:24px 0 0;font-size:13px;color:#8a939f;">
                Nếu bạn không thực hiện đăng nhập, có thể bỏ qua email này — tài khoản vẫn an toàn.
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:20px 32px 28px;background-color:#f4f6f8;border-top:1px solid #e8edf2;text-align:center;">
              <p style="margin:0 0 6px;font-size:13px;font-weight:600;color:#9a1218;">
                Học viện Kỹ thuật Mật mã
              </p>
              <p style="margin:0;font-size:12px;color:#8a939f;line-height:1.5;">
                Academy of Cryptography Techniques<br>
                Hệ thống trợ lý ảo — Email tự động, vui lòng không trả lời.
              </p>
              <p style="margin:14px 0 0;font-size:11px;color:#aab2bd;">
                © {year} KMA
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    return subject, plain, html
