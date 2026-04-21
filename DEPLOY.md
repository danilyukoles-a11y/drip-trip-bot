# DEPLOY — інструкції по роботі з сервером

## Локальні файли (НЕ комітяться, лежать в `tmp/`)

- `tmp/ssh.py` — SSH/upload helper через paramiko
- `tmp/deploy.py` — оновлення бота на сервері однією командою
- `tmp/.env.production` — копія прод `.env` (для повторних upload якщо знадобиться)
- `tmp/vape_bot.service` — systemd unit (вихідник, реальний живе на сервері)
- `tmp/99-bot-deploy.conf` — sshd override для key-only auth

## На сервері (185.25.119.92)

- `/opt/vape_bot/` — git репо (можна `cd` і робити `git pull` вручну)
- `/opt/vape_bot/venv/` — Python virtualenv
- `/opt/vape_bot/.env` — production креди (chmod 600)
- `/etc/systemd/system/vape_bot.service` — systemd unit
- `/etc/ssh/sshd_config.d/99-bot-deploy.conf` — sshd override для key-only auth
- `/root/.ssh/authorized_keys` — публічний ключ для деплою

## Workflow

### Локально (розробка)

1. Кодиш → тестуєш через локального dev-бота (зміниш токен як домовились) → `git push`

### Деплой (одна команда)

```bash
MSYS_NO_PATHCONV=1 python tmp/deploy.py
```

(префікс `MSYS_NO_PATHCONV=1` потрібен на Git Bash, щоб не конвертувало `/opt/...` у Windows-шлях)

## Корисні команди для сервера

```bash
# Подивитись логи в реальному часі
python tmp/ssh.py 'journalctl -u vape_bot -f'

# Останні N рядків логу
python tmp/ssh.py 'journalctl -u vape_bot -n 50 --no-pager'

# Зупинити / запустити / перезапустити
python tmp/ssh.py 'systemctl restart vape_bot'
python tmp/ssh.py 'systemctl stop vape_bot'
python tmp/ssh.py 'systemctl start vape_bot'

# Поточний стан
python tmp/ssh.py 'systemctl status vape_bot --no-pager'

# Поглянути .env
python tmp/ssh.py 'cat /opt/vape_bot/.env'
```

## Безпека

- SSH-ключ: `~/.ssh/id_ed25519_drip_trip_bot`
- Password auth на сервері **вимкнений** (тільки через ключ)
- Backup початкового `sshd_config` на сервері: `/etc/ssh/sshd_config.bak.YYYYMMDD`

## Якщо щось зламалось

**Бот не стартує після деплою:**
```bash
python tmp/ssh.py 'systemctl status vape_bot --no-pager -l'
python tmp/ssh.py 'journalctl -u vape_bot -n 50 --no-pager'
```

**Відкат до попередньої версії:**
```bash
python tmp/ssh.py 'cd /opt/vape_bot && git log --oneline -5'
python tmp/ssh.py 'cd /opt/vape_bot && git reset --hard <COMMIT_SHA> && systemctl restart vape_bot'
```

**Втратив SSH-ключ → потрапив в lockout:**
- Через панель провайдера VPS відновити `sshd_config` з `/etc/ssh/sshd_config.bak.*`
- Або повернути PasswordAuthentication через console провайдера
