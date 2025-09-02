#!/bin/bash
# 우분투 서버에서 adksetch.info 도메인 설정용 스크립트

echo "=== 네이버 리뷰 웹앱 서버 설정 시작 ==="

# 1. 시스템 업데이트
echo "1. 시스템 업데이트..."
sudo apt update && sudo apt upgrade -y

# 2. 필수 패키지 설치
echo "2. 필수 패키지 설치..."
sudo apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx

# 3. Chrome 및 ChromeDriver 설치
echo "3. Chrome 브라우저 설치..."
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt update
sudo apt install -y google-chrome-stable

# ChromeDriver 자동 설치를 위한 webdriver-manager 설치 (Python에서 처리)

# 4. 프로젝트 디렉토리 설정
echo "4. 프로젝트 디렉토리 설정..."
cd /home/ubuntu
git clone https://github.com/seongha27/receipt.git naver-review-webapp
cd naver-review-webapp

# 5. Python 가상환경 설정
echo "5. Python 가상환경 설정..."
python3 -m venv venv
source venv/bin/activate

# 6. Python 패키지 설치
echo "6. Python 패키지 설치..."
pip install -r requirements.txt
pip install webdriver-manager gunicorn

# 7. systemd 서비스 파일 생성
echo "7. 시스템 서비스 설정..."
sudo tee /etc/systemd/system/naver-review.service > /dev/null <<EOF
[Unit]
Description=Naver Review WebApp
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/naver-review-webapp
Environment=PATH=/home/ubuntu/naver-review-webapp/venv/bin
ExecStart=/home/ubuntu/naver-review-webapp/venv/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 8. 서비스 활성화
echo "8. 서비스 활성화..."
sudo systemctl daemon-reload
sudo systemctl enable naver-review.service
sudo systemctl start naver-review.service

# 9. Nginx 설정
echo "9. Nginx 웹서버 설정..."
sudo tee /etc/nginx/sites-available/adksetch.info > /dev/null <<EOF
server {
    listen 80;
    server_name adksetch.info www.adksetch.info;
    
    client_max_body_size 50M;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
}
EOF

# 10. Nginx 사이트 활성화
echo "10. Nginx 사이트 활성화..."
sudo ln -sf /etc/nginx/sites-available/adksetch.info /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx

# 11. SSL 인증서 설정
echo "11. SSL 인증서 설정..."
sudo certbot --nginx -d adksetch.info -d www.adksetch.info --non-interactive --agree-tos --email your-email@example.com

# 12. 방화벽 설정
echo "12. 방화벽 설정..."
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw --force enable

# 13. 서비스 상태 확인
echo "13. 서비스 상태 확인..."
sudo systemctl status naver-review.service --no-pager
sudo systemctl status nginx --no-pager

echo "=== 설정 완료! ==="
echo "브라우저에서 https://adksetch.info 로 접속하세요"
echo ""
echo "관리 명령어:"
echo "- 서비스 재시작: sudo systemctl restart naver-review.service"
echo "- 로그 확인: sudo journalctl -u naver-review.service -f"
echo "- Nginx 재시작: sudo systemctl restart nginx"