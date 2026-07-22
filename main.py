import os
from flask import Flask, request

app = Flask(__name__)


@app.route("/")
def home():
  return "WhatsApp Bot is Active and Running!"


@app.route("/webhook", methods=["POST"])
def webhook():
  # Yahan WhatsApp ke messages aate hain
  data = request.json
  print("Received data:", data)
  return "OK", 200


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)
