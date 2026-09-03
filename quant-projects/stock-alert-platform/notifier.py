import requests, smtplib
from email.mime.text import MIMEText


class Notifier:
    def __init__(self, cfg):
        self.cfg = cfg

    def send(self, sig):
        ok = False
        if self.cfg.get("dingtalk_webhook"):
            ok = self._dingtalk(sig) or ok
        if self.cfg.get("smtp", {}).get("host"):
            ok = self._email(sig) or ok
        if not ok:
            print(f"[告警-无通道] {sig.title}: {sig.message}")
        return ok

    def _dingtalk(self, sig):
        """钉钉自定义机器人（支持「加签」安全设置）。
        钉钉返回 {"errcode":0,"errmsg":"ok"} 表示成功。"""
        import time, hashlib, base64, hmac, urllib.parse
        url = self.cfg["dingtalk_webhook"]
        secret = self.cfg.get("dingtalk_secret", "")
        if secret:                                   # 开启「加签」时必须带时间戳+签名
            timestamp = str(round(time.time() * 1000))
            string_to_sign = f"{timestamp}\n{secret}"
            hmac_code = hmac.new(secret.encode("utf-8"),
                                 string_to_sign.encode("utf-8"),
                                 hashlib.sha256).digest()
            sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}timestamp={timestamp}&sign={sign}"
        text = (f"## ⚠️ {sig.title}\n"
                f"> 级别: {sig.level}\n> {sig.message}\n> 标的: {sig.symbol}")
        try:
            r = requests.post(url,
                              json={"msgtype": "markdown",
                                    "markdown": {"title": f"[股票预警] {sig.title}",
                                                 "text": text}},
                              timeout=10)
            return r.status_code == 200 and r.json().get("errcode") == 0
        except Exception as e:
            print(f"[钉钉发送失败] {e}")
            return False

    def _email(self, sig):
        s = self.cfg["smtp"]
        try:
            msg = MIMEText(f"{sig.title}\n{sig.message}", "plain", "utf-8")
            msg["Subject"] = f"[股票预警] {sig.title}"
            msg["From"] = s["user"]; msg["To"] = s["to"]
            with smtplib.SMTP_SSL(s["host"], s["port"], timeout=10) as m:
                m.login(s["user"], s["pass"])
                m.send_message(msg)
            return True
        except Exception as e:
            print(f"[邮件发送失败] {e}")
            return False
