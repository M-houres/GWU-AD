import base64
from html import escape
from io import BytesIO


def build_qrcode_data_url(payload: str) -> str:
    try:
        import qrcode  # type: ignore

        img = qrcode.make(payload)
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    except Exception:
        safe_payload = escape(str(payload or "")[:96])
        svg = f"""
<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240" viewBox="0 0 240 240">
  <rect width="240" height="240" rx="24" fill="#f5f7fa"/>
  <rect x="18" y="18" width="204" height="204" rx="18" fill="#ffffff" stroke="#d9e0e6"/>
  <text x="120" y="98" text-anchor="middle" font-size="18" font-family="Arial, sans-serif" fill="#111111">QR Preview</text>
  <text x="120" y="126" text-anchor="middle" font-size="12" font-family="Arial, sans-serif" fill="#5b6771">qrcode package unavailable</text>
  <text x="120" y="158" text-anchor="middle" font-size="10" font-family="Arial, sans-serif" fill="#7b8792">{safe_payload}</text>
</svg>
""".strip()
        encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        return f"data:image/svg+xml;base64,{encoded}"
