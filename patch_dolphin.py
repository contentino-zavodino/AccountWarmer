"""Скрипт разблокировки автоматизации Dolphin{anty} на бесплатном тарифе."""

import os
import glob
import shutil

def patch():
    base_dir = os.path.expanduser("~/Library/Application Support/dolphin_anty/local-api")
    matches = glob.glob(os.path.join(base_dir, "*/dist/main.js"))
    if not matches:
        print("[!] Файл local-api/main.js не найден.")
        return

    for path in matches:
        print(f"[*] Обработка: {path}")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        target = 'if(Z&&n())return F.status(402).json({error:"On free plan you can\'t use automation"});'
        replacement = 'if(false&&n())return F.status(402).json({error:"On free plan you can\'t use automation"});'

        if target in content:
            backup = path + ".bak"
            if not os.path.exists(backup):
                shutil.copy2(path, backup)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content.replace(target, replacement, 1))
            print("[+] Успешно разблокировано! Перезапустите Dolphin{anty}.")
        elif replacement in content:
            print("[+] Файл уже разблокирован!")
        else:
            print("[?] Сигнатура проверки не найдена.")

if __name__ == "__main__":
    patch()
