#!/usr/bin/env python3
"""
🤖 BOT DE SUBIDA A REVISTAS
Con sistema de proxies integrado
"""

import asyncio
import shutil
import os
import re
import json
import aiohttp
import yt_dlp
import pymegatools
from pathlib import Path
import time
from datetime import datetime
from bs4 import BeautifulSoup
from pyrogram import Client, filters
from pyrogram.types import Message
from json import loads, dumps
from urllib.parse import unquote_plus, quote_plus
from random import randint
from io import BufferedReader
import mimetypes
import ssl
import base64
####division zip
import traceback
# ===== FUNCIONES DE COMPRESIÓN Y DIVISIÓN =====
import zipfile
import math

def dividir_archivo(filepath, max_size_mb):
    """
    Divide un archivo en partes de max_size_mb MB
    Retorna lista de rutas de los archivos creados
    """
    max_size_bytes = max_size_mb * 1024 * 1024
    file_size = os.path.getsize(filepath)
    
    if file_size <= max_size_bytes:
        return [filepath]  # No necesita división
    
    partes_necesarias = math.ceil(file_size / max_size_bytes)
    partes = []
    
    print(f"📦 Dividiendo archivo de {sizeof_fmt(file_size)} en {partes_necesarias} partes...")
    
    with open(filepath, 'rb') as f:
        for i in range(partes_necesarias):
            parte_path = f"{filepath}_parte_{i+1:03d}"
            
            # Calcular tamaño de esta parte
            inicio = i * max_size_bytes
            fin = min((i + 1) * max_size_bytes, file_size)
            tamano_parte = fin - inicio
            
            # Leer y escribir la parte
            f.seek(inicio)
            datos = f.read(tamano_parte)
            
            with open(parte_path, 'wb') as parte_file:
                parte_file.write(datos)
                
            partes.append(parte_path)
            print(f"  ✅ Parte {i+1}: {sizeof_fmt(tamano_parte)}")
            
    return partes

def comprimir_y_dividir(filepath, max_size_mb, username):
    """
    Comprime un archivo y lo divide si es necesario
    Retorna lista de archivos .zip creados
    """
    filename = os.path.basename(filepath)
    filename_base = os.path.splitext(filename)[0]
    file_size = os.path.getsize(filepath)
    max_size_bytes = max_size_mb * 1024 * 1024
    
    user_dir = f"downloads/{username}"
    temp_dir = os.path.join(user_dir, "temp_zips")
    os.makedirs(temp_dir, exist_ok=True)
    
    archivos_zip = []
    
    # Si el archivo ya es pequeño, comprimirlo directamente
    if file_size <= max_size_bytes:
        zip_path = os.path.join(temp_dir, f"{filename_base}.zip")
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(filepath, filename)
            
        print(f"📦 Comprimido: {filename} → {sizeof_fmt(os.path.getsize(zip_path))}")
        archivos_zip.append(zip_path)
        
    else:
        # Dividir primero, luego comprimir cada parte
        partes = dividir_archivo(filepath, max_size_mb)
        
        for i, parte_path in enumerate(partes):
            parte_name = os.path.basename(parte_path)
            zip_name = f"{filename_base}_parte_{i+1:03d}.zip"
            zip_path = os.path.join(temp_dir, zip_name)
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(parte_path, f"{filename_base}_parte_{i+1:03d}{os.path.splitext(filename)[1]}")
                
            archivos_zip.append(zip_path)
            
            # Eliminar la parte temporal
            os.remove(parte_path)
            
    return archivos_zip

def limpiar_archivos_temporales(username):
    """Limpia los archivos temporales de compresión"""
    temp_dir = f"downloads/{username}/temp_zips"
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
        print(f"🧹 Limpiados archivos temporales de {username}")


# Importar el sistema de proxies
from proxy_manager import proxy_manager

# ===== CONFIGURACIÓN DEL BOT =====
API_ID = 9652234
API_HASH = "e532d52554115eed48f82f7dcb10b171"
BOT_TOKEN = "7640035042:AAHYO51QUhKFikvBqBgzoO9huxcxtXKrX0s"
USUARIOS_AUTORIZADOS = ["Thedota9"]

# Configuración por usuario
user_configs = {}
user_files = {}
user_roots = {}
active_uploads = {}

bot = Client(
    "bot_revistas",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ===== FUNCIONES UTILITARIAS =====
def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return f"{num:3.2f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.2f}Yi{suffix}"

def update_progress_bar(current, total):
    if total == 0:
        return "[                    ] 0%"
        
    percentage = (current / total) * 100
    percentage = min(100, max(0, percentage))
    percentage_int = int(percentage)
    
    hashes = int(percentage_int / 5)
    spaces = 20 - hashes
    
    return f"[{'█' * hashes}{' ' * spaces}] {percentage_int:3d}%"

async def verificar_usuario(username):
    if not username or username not in USUARIOS_AUTORIZADOS:
        return False
        
    user_dir = f"downloads/{username}"
    if not os.path.exists(user_dir):
        os.makedirs(user_dir, exist_ok=True)
        
    if username not in user_configs:
        user_configs[username] = {
            "revistas_host": "",
            "revistas_user": "",
            "revistas_pass": "",
            "revistas_upid": "",
            "revistas_zips": 100,
            "revistas_mode": "n"
        }
        
    if username not in user_files:
        user_files[username] = []
        
    if username not in user_roots:
        user_roots[username] = user_dir
        
    if username not in active_uploads:
        active_uploads[username] = False
        
    # Configurar proxy por defecto para el usuario
    proxy_manager.set_user_setting(username, 'use_proxy', True)
    
    return True

def listar_archivos(path):
    try:
        items = os.listdir(path)
        directorios = []
        archivos = []
        
        for item in items:
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path):
                directorios.append(item)
            else:
                archivos.append(item)
                
        directorios.sort()
        archivos.sort()
        
        return directorios + archivos
    except Exception as e:
        print(f"Error listando archivos: {e}")
        return []

def generar_nombre_archivo(extension=""):
    timestamp = int(time.time())
    random_num = randint(1000, 9999)
    if extension:
        return f"archivo_{timestamp}_{random_num}.{extension}"
    return f"archivo_{timestamp}_{random_num}"

class ProgressReader(BufferedReader):
    def __init__(self, filename, callback):
        f = open(filename, "rb")
        self.filename = os.path.basename(filename)
        self.callback = callback
        super().__init__(raw=f)
        self.start_time = time.time()
        self.length = os.path.getsize(filename)
        self.last_update = 0
        
    def read(self, size=None):
        if not size:
            size = self.length - self.tell()
            
        current_pos = self.tell()
        if time.time() - self.last_update > 1:
            self.callback(current_pos, self.length, self.start_time, self.filename)
            self.last_update = time.time()
            
        return super().read(size)

# ===== COMANDOS BÁSICOS =====
@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    username = message.from_user.username
    if not await verificar_usuario(username):
        await message.reply("⛔ No estás autorizado para usar este bot.")
        return
        
    total, used, free = shutil.disk_usage(".")
    proxy_stats = proxy_manager.get_stats()
    
    msg = "🤖 **Bot de Subida a Revistas** 🤖\n\n"
    msg += "**Comandos disponibles:**\n"
    msg += "• /start - Iniciar bot\n"
    msg += "• /help - Mostrar ayuda completa\n"
    msg += "• /rv - Configurar revistas\n"
    msg += "• /ls - Listar archivos\n"
    msg += "• /up N - Subir archivo número N\n"
    msg += "• /download - Descargar archivos cargados\n"
    msg += "• /rm N - Eliminar archivo\n"
    msg += "• /mkdir nombre - Crear carpeta\n"
    msg += "• /cd .. - Subir directorio\n"
    msg += "• /cd N - Entrar a carpeta\n"
    msg += "• /rename N nuevo_nombre - Renombrar\n"
    msg += "• /deleteall - Limpiar todo\n"
    msg += "• /cancel - Cancelar subida\n"
    msg += "• /debug - Información de depuración\n\n"
    msg += "**🔧 Comandos de Proxy:**\n"
    msg += "• /proxies - Gestionar proxies\n"
    msg += "• /testproxy - Probar conexión\n\n"
    msg += f"💾 **Espacio disponible:** {sizeof_fmt(free)} / {sizeof_fmt(total)}\n"
    msg += f"🔧 **Proxies activos:** {proxy_stats['total_proxies']}"
    
    await message.reply(msg)

@bot.on_message(filters.command("help") & filters.private)
async def help_cmd(client: Client, message: Message):
    help_text = """
    🤖 **AYUDA - Bot de Revistas**

    📋 **COMANDOS BÁSICOS:**
    • /start - Iniciar bot
    • /help - Mostrar esta ayuda
    • /rv - Configurar revistas
    • /ls - Listar archivos
    • /up N - Subir archivo número N
    • /download - Descargar archivos enviados
    • /mkdir nombre - Crear carpeta
    • /cd N - Entrar a carpeta N
    • /cd .. - Subir directorio
    • /rm N - Eliminar archivo N
    • /rename N nombre - Renombrar
    • /deleteall - Limpiar todo
    • /cancel - Cancelar subida
    • /debug - Información de depuración

    🔧 **COMANDOS DE PROXY:**
    • /proxies - Ver y gestionar proxies
    • /proxies refresh - Buscar nuevos proxies
    • /proxies test - Probar proxies funcionando
    • /proxies set socks5://ip:port - Fijar proxy específico
    • /proxies auto - Volver a auto-rotación
    • /proxies on/off - Activar/desactivar proxy
    • /testproxy [url] - Probar conexión con proxy

    📥 **DESCARGA DE ARCHIVOS:**
    1. **Enlaces directos**: Envía cualquier enlace HTTP/HTTPS
    2. **YouTube**: Envía enlace de YouTube
    3. **Mega.nz**: Envía enlace de Mega
    4. **Archivos**: Envía archivos al bot, luego usa /download

    ⚙️ **CONFIGURACIÓN REVISTAS:**
    Formato: /rv host usuario contraseña upid zips mode

    Ejemplo:

    🎯 **EJEMPLO DE USO:**
    1. /rv https://ejemplo.com/ user pass 12345 100 n
    2. Envía un enlace o archivo
    3. /ls
    4. /up 0
    """
    await message.reply(help_text)

# ===== COMANDOS DE PROXIES =====
@bot.on_message(filters.command("proxies") & filters.private)
async def proxies_cmd(client: Client, message: Message):
    """Gestiona el sistema de proxies"""
    username = message.from_user.username
    if not await verificar_usuario(username):
        return
        
    partes = message.text.split()
    
    if len(partes) == 1:
        # Mostrar información
        proxy_stats = proxy_manager.get_stats()
        user_info = proxy_manager.get_user_proxy_info(username)
        
        msg = "🔧 **SISTEMA DE PROXIES**\n\n"
        msg += f"📊 **Proxies disponibles:** {proxy_stats['total_proxies']}\n"
        msg += f"🔄 **Última actualización:** {proxy_stats['last_fetch']}\n"
        msg += f"👤 **Tu proxy:** `{user_info['personal_proxy']}`\n"
        msg += f"⚡ **Proxy activado:** {'Sí' if user_info['use_proxy'] else 'No'}\n\n"
        
        if proxy_stats['total_proxies'] > 0:
            # Mostrar algunos proxies
            proxy_list = proxy_manager.proxies[:5]
            msg += "📋 **Proxies activos (primeros 5):**\n"
            for i, proxy in enumerate(proxy_list):
                msg += f"{i+1}. `{proxy}`\n"
                
        msg += "\n⚙️ **Subcomandos:**\n"
        msg += "• `/proxies refresh` - Buscar nuevos proxies\n"
        msg += "• `/proxies test` - Probar proxies\n"
        msg += "• `/proxies set socks5://ip:puerto` - Fijar proxy\n"
        msg += "• `/proxies auto` - Auto-rotación\n"
        msg += "• `/proxies on` - Activar proxy\n"
        msg += "• `/proxies off` - Desactivar proxy\n"
        
        await message.reply(msg)
        
    elif len(partes) >= 2:
        comando = partes[1].lower()
        
        if comando == "refresh":
            msg = await message.reply("🔄 Buscando nuevos proxies...")
            count = await proxy_manager.fetch_proxies()
            await msg.edit(f"✅ **Proxies actualizados:** {count} funcionando")
            
        elif comando == "test":
            msg = await message.reply("🧪 Probando proxies...")
            
            # Probar algunos proxies
            test_proxies = proxy_manager.proxies[:10]
            resultados = []
            
            for proxy in test_proxies:
                funciona = await proxy_manager.test_proxy(proxy)
                resultados.append((proxy, funciona))
                
            funcionando = sum(1 for _, func in resultados if func)
            total = len(resultados)
            
            await msg.edit(
                f"📊 **Resultados de prueba:**\n\n"
                f"✅ Funcionando: {funcionando}/{total}\n"
                f"📈 Tasa de éxito: {(funcionando/total*100):.1f}%"
            )
            
        elif comando == "set" and len(partes) >= 3:
            proxy_url = partes[2]
            msg = await message.reply(f"🔍 Probando proxy: `{proxy_url}`")
            
            if await proxy_manager.test_proxy(proxy_url):
                proxy_manager.set_user_proxy(username, proxy_url)
                await msg.edit(f"✅ **Proxy configurado:**\n`{proxy_url}`")
            else:
                await msg.edit(f"❌ **Proxy no funciona:**\n`{proxy_url}`")
                
        elif comando == "auto":
            proxy_manager.set_user_proxy(username, None)
            await message.reply("✅ **Proxy configurado en modo auto-rotación**")
            
        elif comando == "on":
            proxy_manager.set_user_setting(username, 'use_proxy', True)
            await message.reply("✅ **Proxy activado**")
            
        elif comando == "off":
            proxy_manager.set_user_setting(username, 'use_proxy', False)
            await message.reply("✅ **Proxy desactivado**")


@bot.on_message(filters.command("testproxy") & filters.private)
async def test_proxy_cmd(client: Client, message: Message):
    """Prueba la conexión con proxy"""
    username = message.from_user.username
    if not await verificar_usuario(username):
        return
        
    partes = message.text.split()
    test_url = "https://httpbin.org/ip"
    
    if len(partes) >= 2:
        test_url = partes[1]
        
    msg = await message.reply(f"🔍 **Probando conexión a:**\n`{test_url}`")
    
    # Probar sin proxy
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(test_url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    ip_direct = data.get('origin', 'No detectado')
                else:
                    ip_direct = f"Error HTTP: {resp.status}"
    except Exception as e:
        ip_direct = f"Error: {str(e)[:50]}"
        
    # Probar con proxy
    connector = await proxy_manager.get_connector(username, ssl_verify=True)
    
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get(test_url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    ip_proxy = data.get('origin', 'No detectado')
                else:
                    ip_proxy = f"Error HTTP: {resp.status}"
    except Exception as e:
        ip_proxy = f"Error: {str(e)[:50]}"
        
    resultado = f"📊 **RESULTADOS DE CONEXIÓN**\n\n"
    resultado += f"🌐 **URL probada:** `{test_url}`\n\n"
    resultado += f"🔓 **Sin proxy:**\n`{ip_direct}`\n\n"
    resultado += f"🔒 **Con proxy:**\n`{ip_proxy}`\n\n"
    
    if "Error" not in ip_proxy and ip_direct != ip_proxy:
        resultado += "✅ **Proxy funcionando correctamente**"
    elif "Error" in ip_proxy:
        resultado += "❌ **Proxy no funciona**"
    else:
        resultado += "⚠️ **Proxy puede no estar funcionando**"
        
    await msg.edit(resultado)

# ===== COMANDOS DE CONFIGURACIÓN REVISTAS =====
@bot.on_message(filters.command("rv") & filters.private)
async def config_revistas(client: Client, message: Message):
    username = message.from_user.username
    if not await verificar_usuario(username):
        return
        
    try:
        partes = message.text.split(" ", 6)
        if len(partes) < 7:
            await message.reply(
                "❌ **Formato incorrecto**\n\n"
                "✅ **Uso correcto:**\n"
                "`/rv host usuario contraseña upid zips mode`\n\n"
                "📌 **Ejemplo:**\n"
                "`/rv https://revistas.ejemplo.com/ usuario pass 12345 100 n`"
            )
            return
            
        _, host, user, password, upid, zips_str, mode = partes
        
        if not host.startswith(("http://", "https://")):
            host = "https://" + host
            
        if not host.endswith("/"):
            host += "/"
            
        try:
            zips = int(zips_str)
            if zips < 1 or zips > 1000:
                await message.reply("❌ El tamaño de zips debe estar entre 1 y 1000 MB")
                return
        except ValueError:
            await message.reply("❌ El tamaño de zips debe ser un número")
            return
            
        if mode not in ["n", "a"]:
            await message.reply("❌ El modo debe ser 'n' (normal) o 'a' (alternativo)")
            return
            
        user_configs[username].update({
            "revistas_host": host,
            "revistas_user": user,
            "revistas_pass": password,
            "revistas_upid": upid,
            "revistas_zips": zips,
            "revistas_mode": mode
        })
        
        config_file = f"config_{username}.json"
        with open(config_file, "w") as f:
            f.write(dumps(user_configs[username], indent=4))
            
        await message.reply(
            f"✅ **Configuración guardada**\n\n"
            f"🌐 **Host:** `{host}`\n"
            f"👤 **Usuario:** `{user}`\n"
            f"🔑 **UpID:** `{upid}`\n"
            f"📦 **Zips:** `{zips} MB`\n"
            f"🔧 **Modo:** `{mode}`\n"
            f"📄 Guardado en: `{config_file}`"
        )
        
    except Exception as e:
        await message.reply(f"❌ **Error:**\n`{str(e)[:200]}`")

# ===== COMANDOS DE GESTIÓN DE ARCHIVOS =====
@bot.on_message(filters.command("ls") & filters.private)
async def list_files(client: Client, message: Message):
    username = message.from_user.username
    if not await verificar_usuario(username):
        return
        
    current_dir = user_roots.get(username, f"downloads/{username}")
    items = listar_archivos(current_dir)
    
    if not items:
        await message.reply(f"📂 **Directorio vacío**\n\n`{current_dir}`")
        return
        
    msg = f"📂 **Contenido de:** `{current_dir.replace('downloads/' + username, '~')}`\n\n"
    
    for idx, item in enumerate(items):
        item_path = os.path.join(current_dir, item)
        if os.path.isdir(item_path):
            try:
                file_count = len([f for f in os.listdir(item_path) if os.path.isfile(os.path.join(item_path, f))])
                msg += f"{idx:2d}. 📁 `{item}/` ({file_count} archivos)\n"
            except:
                msg += f"{idx:2d}. 📁 `{item}/`\n"
        else:
            try:
                size = os.path.getsize(item_path)
                msg += f"{idx:2d}. 📄 `{item}` ({sizeof_fmt(size)})\n"
            except:
                msg += f"{idx:2d}. 📄 `{item}`\n"
                
    msg += "\n📌 **Usa:**\n• `/cd N` para entrar a carpeta\n• `/up N` para subir archivo"
    
    if len(msg) > 4000:
        mitad = len(msg) // 2
        await message.reply(msg[:mitad])
        await message.reply(msg[mitad:])
    else:
        await message.reply(msg)

@bot.on_message(filters.command("cd") & filters.private)
async def change_dir(client: Client, message: Message):
    username = message.from_user.username
    if not await verificar_usuario(username):
        return
        
    try:
        partes = message.text.split()
        current_dir = user_roots.get(username, f"downloads/{username}")
        
        if len(partes) < 2:
            await message.reply("❌ Especifica un directorio o número")
            return
            
        target = partes[1]
        
        if target == "..":
            if current_dir == f"downloads/{username}":
                await message.reply("⚠️ Ya estás en el directorio raíz")
                return
                
            new_dir = os.path.dirname(current_dir)
            user_roots[username] = new_dir
            await list_files(client, message)
            return
            
        try:
            idx = int(target)
            items = listar_archivos(current_dir)
            
            if idx < 0 or idx >= len(items):
                await message.reply("❌ Índice inválido")
                return
                
            selected = items[idx]
            new_path = os.path.join(current_dir, selected)
            
            if os.path.isdir(new_path):
                user_roots[username] = new_path
                await list_files(client, message)
            else:
                await message.reply("❌ Solo puedes entrar a carpetas")
                
        except ValueError:
            new_path = os.path.join(current_dir, target)
            if os.path.exists(new_path) and os.path.isdir(new_path):
                user_roots[username] = new_path
                await list_files(client, message)
            else:
                await message.reply("❌ Directorio no encontrado")
                
    except Exception as e:
        await message.reply(f"❌ **Error:**\n`{str(e)[:200]}`")

@bot.on_message(filters.command("mkdir") & filters.private)
async def make_dir(client: Client, message: Message):
    username = message.from_user.username
    if not await verificar_usuario(username):
        return
        
    try:
        partes = message.text.split(maxsplit=1)
        if len(partes) < 2:
            await message.reply("❌ Especifica un nombre para la carpeta")
            return
            
        folder_name = partes[1]
        current_dir = user_roots.get(username, f"downloads/{username}")
        new_folder = os.path.join(current_dir, folder_name)
        
        os.makedirs(new_folder, exist_ok=True)
        await message.reply(f"✅ **Carpeta creada:**\n`{folder_name}`")
        await list_files(client, message)
        
    except Exception as e:
        await message.reply(f"❌ **Error:**\n`{str(e)[:200]}`")

@bot.on_message(filters.command("rm") & filters.private)
async def remove_file(client: Client, message: Message):
    username = message.from_user.username
    if not await verificar_usuario(username):
        return
        
    try:
        partes = message.text.split()
        if len(partes) < 2:
            await message.reply("❌ Especifica el número del archivo")
            return
            
        idx = int(partes[1])
        current_dir = user_roots.get(username, f"downloads/{username}")
        items = listar_archivos(current_dir)
        
        if idx < 0 or idx >= len(items):
            await message.reply("❌ Índice inválido")
            return
            
        item_name = items[idx]
        item_to_remove = os.path.join(current_dir, item_name)
        
        if os.path.isdir(item_to_remove):
            shutil.rmtree(item_to_remove)
        else:
            os.remove(item_to_remove)
            
        await message.reply(f"✅ **Eliminado:**\n`{item_name}`")
        await list_files(client, message)
        
    except Exception as e:
        await message.reply(f"❌ **Error:**\n`{str(e)[:200]}`")

@bot.on_message(filters.command("rename") & filters.private)
async def rename_file(client: Client, message: Message):
    username = message.from_user.username
    if not await verificar_usuario(username):
        return
        
    try:
        partes = message.text.split(maxsplit=2)
        if len(partes) < 3:
            await message.reply("❌ Formato: /rename N nuevo_nombre")
            return
            
        idx = int(partes[1])
        new_name = partes[2]
        current_dir = user_roots.get(username, f"downloads/{username}")
        items = listar_archivos(current_dir)
        
        if idx < 0 or idx >= len(items):
            await message.reply("❌ Índice inválido")
            return
            
        old_name = items[idx]
        old_path = os.path.join(current_dir, old_name)
        new_path = os.path.join(current_dir, new_name)
        
        os.rename(old_path, new_path)
        await message.reply(f"✅ **Renombrado:**\n`{old_name}` → `{new_name}`")
        await list_files(client, message)
        
    except Exception as e:
        await message.reply(f"❌ **Error:**\n`{str(e)[:200]}`")

@bot.on_message(filters.command("deleteall") & filters.private)
async def delete_all(client: Client, message: Message):
    username = message.from_user.username
    if not await verificar_usuario(username):
        return
        
    user_dir = f"downloads/{username}"
    if os.path.exists(user_dir):
        shutil.rmtree(user_dir)
        os.makedirs(user_dir, exist_ok=True)
        user_roots[username] = user_dir
        user_files[username] = []
        
        await message.reply("✅ **Directorio limpiado**")
        await list_files(client, message)


# ===== DESCARGA DE ARCHIVOS =====
@bot.on_message(filters.command("download") & filters.private)
async def download_files(client: Client, message: Message):
    username = message.from_user.username
    if not await verificar_usuario(username):
        return
        
    if not user_files.get(username):
        await message.reply("📭 No hay archivos cargados")
        return
        
    msg = await message.reply("⏬ **Descargando archivos...**")
    downloaded = 0
    errors = 0
    
    for file_msg in user_files[username]:
        try:
            if file_msg.document:
                filename = file_msg.document.file_name or f"documento_{int(time.time())}"
            elif file_msg.video:
                filename = f"video_{int(time.time())}.mp4"
            elif file_msg.audio:
                filename = f"audio_{int(time.time())}.mp3"
            else:
                filename = f"archivo_{int(time.time())}"
                
            await msg.edit(f"📥 **Descargando:** `{filename}`")
            
            await file_msg.download(
                file_name=os.path.join(user_roots[username], filename),
                progress=lambda current, total: download_progress(current, total, filename, msg)
            )
            
            downloaded += 1
            
        except Exception as e:
            errors += 1
            print(f"❌ Error descargando: {e}")
            
    user_files[username] = []
    
    if downloaded > 0:
        await msg.edit(f"✅ **Descarga completada**\n\n• Descargados: {downloaded}\n• Errores: {errors}")
    else:
        await msg.edit("❌ No se pudo descargar ningún archivo")
        
    await list_files(client, message)

def download_progress(current, total, filename, msg):
    if total == 0:
        return
        
    progress = update_progress_bar(current, total)
    
    if int(time.time()) % 2 == 0:
        try:
            msg.edit(
                f"📥 **Descargando**\n\n"
                f"📁 `{filename}`\n"
                f"{progress}\n"
                f"📊 {sizeof_fmt(current)} / {sizeof_fmt(total)}"
            )
        except:
            pass

@bot.on_message(filters.document | filters.video | filters.audio | filters.photo)
async def handle_media(client: Client, message: Message):
    username = message.from_user.username
    if not await verificar_usuario(username):
        return
        
    if username not in user_files:
        user_files[username] = []
        
    user_files[username].append(message)
    count = len(user_files[username])
    
    await message.reply(
        f"✅ **Archivo recibido**\n\n"
        f"📊 **En cola:** {count} archivo{'s' if count != 1 else ''}\n\n"
        f"Usa `/download` para descargar"
    )

# ===== DESCARGA DE ENLACES =====
@bot.on_message(filters.regex(r"https?://") & filters.private)
async def download_link(client: Client, message: Message):
    username = message.from_user.username
    if not await verificar_usuario(username):
        return
        
    url = message.text.strip()
    msg = await message.reply("🔍 **Analizando enlace...**")
    
    try:
        if "youtube.com" in url or "youtu.be" in url:
            await download_youtube(url, msg, username)
        elif "mega.nz" in url:
            await download_mega(url, msg, username)
        else:
            await download_direct(url, msg, username)
            
    except Exception as e:
        await msg.edit(f"❌ **Error:**\n`{str(e)[:200]}`")

async def download_youtube(url, msg, username):
    await msg.edit("🎬 **Descargando YouTube...**")
    
    user_dir = user_roots.get(username, f"downloads/{username}")
    
    ydl_opts = {
        'outtmpl': f'{user_dir}/%(title)s.%(ext)s',
        'format': 'best[height<=720]',
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            await msg.edit(f"✅ **Video descargado:**\n`{os.path.basename(filename)}`")
            await list_files(bot, msg)
    except Exception as e:
        await msg.edit(f"❌ **Error YouTube:**\n`{str(e)[:200]}`")

async def download_mega(url, msg, username):
    await msg.edit("🌀 **Descargando Mega...**")
    
    try:
        mega = pymegatools.Megatools()
        filename = mega.filename(url)
        await msg.edit(f"🔍 **Archivo:** `{filename}`")
        
        user_dir = user_roots.get(username, f"downloads/{username}")
        os.chdir(user_dir)
        
        mega.download(url, progress=None)
        
        if os.path.exists(filename):
            await msg.edit(f"✅ **Descargado:**\n`{filename}`")
        else:
            files = os.listdir(user_dir)
            new_files = [f for f in files if f.endswith(('.mp4', '.avi', '.mkv', '.zip', '.rar', '.7z'))]
            if new_files:
                latest = max(new_files, key=os.path.getctime)
                await msg.edit(f"✅ **Descargado:**\n`{latest}`")
            else:
                await msg.edit("⚠️ **Descarga completada, archivo no encontrado**")
                
        await list_files(bot, msg)
        
    except Exception as e:
        await msg.edit(f"❌ **Error Mega:**\n`{str(e)[:200]}`")

async def download_direct(url, msg, username):
    """Descarga archivos desde enlaces directos CON PROXY"""
    await msg.edit("⬇️ **Descargando enlace...**")
    
    # Determinar si necesita SSL desactivado
    ssl_verify = True
    if "rev16deabril" in url or "sld.cu" in url:
        ssl_verify = False
        
    # Obtener connector con proxy
    connector = await proxy_manager.get_connector(username, ssl_verify=ssl_verify)
    
    try:
        timeout = aiohttp.ClientTimeout(total=300)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get(url, timeout=timeout) as response:
                if response.status == 200:
                    # Obtener nombre del archivo
                    filename = None
                    
                    if 'Content-Disposition' in response.headers:
                        content_disp = response.headers['Content-Disposition']
                        if 'filename=' in content_disp:
                            filename = content_disp.split('filename=')[1]
                            filename = filename.strip('"\'')
                            filename = unquote_plus(filename)
                            
                    if not filename:
                        filename = unquote_plus(url.split('/')[-1].split('?')[0])
                        if not filename or len(filename) > 100 or '/' in filename:
                            content_type = response.headers.get('Content-Type', '')
                            extension = mimetypes.guess_extension(content_type.split(';')[0]) or '.bin'
                            filename = f"archivo_{int(time.time())}_{randint(1000, 9999)}.{extension.lstrip('.')}"
                            
                    user_dir = user_roots.get(username, f"downloads/{username}")
                    filepath = os.path.join(user_dir, filename)
                    
                    # Descargar con progreso
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    start_time = time.time()
                    last_update = start_time
                    
                    with open(filepath, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                
                                current_time = time.time()
                                if current_time - last_update > 2 and total_size > 0:
                                    progress = update_progress_bar(downloaded, total_size)
                                    speed = downloaded / (current_time - start_time)
                                    
                                    await msg.edit(
                                        f"⬇️ **Descargando**\n\n"
                                        f"📁 `{filename}`\n"
                                        f"{progress}\n"
                                        f"📊 {sizeof_fmt(downloaded)} / {sizeof_fmt(total_size)}\n"
                                        f"⚡ {sizeof_fmt(speed)}/s"
                                    )
                                    last_update = current_time
                                    
                    await msg.edit(f"✅ **Descargado:**\n`{filename}`")
                    await list_files(bot, msg)
                    
                else:
                    await msg.edit(f"❌ **Error HTTP:** {response.status}")
                    
    except asyncio.TimeoutError:
        await msg.edit("❌ **Tiempo agotado**")
    except aiohttp.ClientError as e:
        await msg.edit(f"❌ **Error conexión:**\n`{str(e)[:200]}`")
    except Exception as e:
        await msg.edit(f"❌ **Error:**\n`{str(e)[:200]}`")

# ===== SUBIDA A REVISTAS =====
def upload_progress(current, total, start, filename, msg):
    elapsed = time.time() - start
    if elapsed > 0:
        speed = current / elapsed
    else:
        speed = 0
        
    progress = update_progress_bar(current, total)
    
    if int(time.time() - start) % 2 == 0:
        try:
            msg.edit(
                f"⬆️ **Subiendo**\n\n"
                f"📁 `{filename}`\n"
                f"{progress}\n"
                f"📊 {sizeof_fmt(current)} / {sizeof_fmt(total)}\n"
                f"⚡ {sizeof_fmt(speed)}/s"
            )
        except:
            pass

# ===== SUBIDA A REVISTAS =====
async def upload_revistas(filepath, msg, username):
    """Sube archivo al sistema de revistas con compresión si es necesario"""
    config = user_configs.get(username, {})
    
    if not config.get("revistas_host"):
        await msg.edit("❌ **Configura revistas con** `/rv`")
        return False
        
    host = config["revistas_host"]
    user = config["revistas_user"]
    password = config["revistas_pass"]
    upid = config["revistas_upid"]
    zips_mb = config["revistas_zips"]
    mode = config["revistas_mode"]
    
    filename_original = os.path.basename(filepath)
    file_size = os.path.getsize(filepath)
    
    await msg.edit(f"📊 **Analizando archivo:**\n`{filename_original}`\n📦 Tamaño: {sizeof_fmt(file_size)}")
    
    # ===== 1. CREAR TEMP DIR =====
    user_dir = f"downloads/{username}"
    temp_dir = os.path.join(user_dir, "temp_zips")
    os.makedirs(temp_dir, exist_ok=True)
    
    # ===== 2. COMPRIMIR Y DIVIDIR SI ES NECESARIO =====
    archivos_a_subir = []
    
    if file_size > (zips_mb * 1024 * 1024):
        await msg.edit(f"📦 **Archivo muy grande, dividiendo en partes de {zips_mb}MB...**")
        
        try:
            archivos_zip = comprimir_y_dividir(filepath, zips_mb, username)
            
            if not archivos_zip:
                await msg.edit("❌ **Error al comprimir el archivo**")
                return False
                
            await msg.edit(f"✅ **Dividido en {len(archivos_zip)} partes**")
            archivos_a_subir = archivos_zip
            
        except Exception as e:
            await msg.edit(f"❌ **Error en compresión:**\n`{str(e)[:200]}`")
            print(f"DEBUG - Error compresión: {e}")
            return False
    else:
        # No necesita división, comprimir directamente
        await msg.edit(f"📦 **Comprimiendo archivo...**")
        
        try:
            filename_base = os.path.splitext(filename_original)[0]
            zip_path = os.path.join(temp_dir, f"{filename_base}.zip")
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(filepath, filename_original)
                
            archivos_a_subir = [zip_path]
            zip_size = os.path.getsize(zip_path)
            await msg.edit(f"✅ **Comprimido:** {sizeof_fmt(zip_size)}")
            
        except Exception as e:
            await msg.edit(f"❌ **Error al comprimir:**\n`{str(e)[:200]}`")
            print(f"DEBUG - Error compresión simple: {e}")
            return False
            
    # ===== 3. SUBIR CADA ARCHIVO =====
    total_archivos = len(archivos_a_subir)
    exitos = 0
    fallos = 0
    urls_descarga = []
    errores_detallados = []
    
    print(f"DEBUG - Total archivos a subir: {total_archivos}")
    
    for i, archivo_path in enumerate(archivos_a_subir, 1):
        archivo_name = os.path.basename(archivo_path)
        archivo_size = os.path.getsize(archivo_path)
        
        print(f"DEBUG - Procesando parte {i}: {archivo_name} ({archivo_size} bytes)")
        
        await msg.edit(
            f"⬆️ **Subiendo parte {i}/{total_archivos}**\n"
            f"📁 `{archivo_name}`\n"
            f"📦 {sizeof_fmt(archivo_size)}\n"
            f"🔄 Preparando..."
        )
        
        # Renombrar a .jpg para cada parte
        jpg_filepath = archivo_path.rsplit('.', 1)[0] + '.jpg'
        
        try:
            shutil.copy2(archivo_path, jpg_filepath)
            use_filepath = jpg_filepath
            use_filename = os.path.basename(jpg_filepath)
            print(f"DEBUG - Renombrado a: {use_filename}")
        except Exception as e:
            print(f"DEBUG - Error renombrando: {e}")
            use_filepath = archivo_path
            use_filename = archivo_name
            
        # Subir esta parte
        url_descarga = await subir_parte_revistas_mejorado(
            use_filepath, use_filename, host, user, password, upid, 
            username, msg, i, total_archivos
        )
        
        if url_descarga:
            urls_descarga.append(url_descarga)
            exitos += 1
            print(f"DEBUG - Parte {i} SUBIDA EXITOSA: {url_descarga}")
        else:
            fallos += 1
            errores_detallados.append(f"Parte {i} falló")
            print(f"DEBUG - Parte {i} FALLÓ")
            
        # Limpiar archivo temporal .jpg
        if os.path.exists(jpg_filepath):
            try:
                os.remove(jpg_filepath)
            except:
                pass
                
        # Pequeña pausa entre subidas
        if i < total_archivos:
            await asyncio.sleep(1)
            
    print(f"DEBUG - Resultados: {exitos} exitos, {fallos} fallos")
    
    # ===== 4. CREAR ARCHIVO DE RESUMEN =====
    await msg.edit(f"📝 **Creando resumen de subida...**")
    
    resumen_path = os.path.join(temp_dir, "resumen_subida.txt")
    with open(resumen_path, 'w', encoding='utf-8') as f:
        f.write(f"RESUMEN DE SUBIDA\n")
        f.write(f"="*50 + "\n")
        f.write(f"Archivo original: {filename_original}\n")
        f.write(f"Tamaño original: {sizeof_fmt(file_size)}\n")
        f.write(f"Partes creadas: {total_archivos}\n")
        f.write(f"Tamaño por parte: {zips_mb} MB\n")
        f.write(f"Subidas exitosas: {exitos}\n")
        f.write(f"Subidas fallidas: {fallos}\n")
        
        if errores_detallados:
            f.write(f"\nERRORES DETALLADOS:\n")
            for error in errores_detallados:
                f.write(f"• {error}\n")
                
        f.write(f"="*50 + "\n\n")
        
        if urls_descarga:
            f.write(f"URLS DE DESCARGA:\n")
            f.write(f"="*50 + "\n")
            for idx, url in enumerate(urls_descarga, 1):
                f.write(f"Parte {idx}: {url}\n")
        else:
            f.write(f"NO HAY URLS DE DESCARGA DISPONIBLES\n")
            
    # ===== 5. ENVIAR RESUMEN AL USUARIO =====
    mensaje_resumen = (
        f"🎉 **PROCESO COMPLETADO**\n\n"
        f"📁 **Archivo:** `{filename_original}`\n"
        f"📦 **Tamaño:** {sizeof_fmt(file_size)}\n"
        f"📊 **Partes:** {total_archivos} ({zips_mb}MB cada una)\n"
        f"✅ **Exitosas:** {exitos}\n"
        f"❌ **Fallidas:** {fallos}\n\n"
    )
    
    if urls_descarga:
        mensaje_resumen += f"🔗 **URLs generadas:** {len(urls_descarga)}\n"
        for idx, url in enumerate(urls_descarga[:3], 1):
            mensaje_resumen += f"{idx}. `{url[:50]}...`\n"
        if len(urls_descarga) > 3:
            mensaje_resumen += f"... y {len(urls_descarga)-3} más\n"
    else:
        mensaje_resumen += f"⚠️ **No se obtuvieron URLs de descarga**\n"
        if fallos > 0:
            mensaje_resumen += f"Posibles causas:\n"
            mensaje_resumen += f"• Credenciales incorrectas\n"
            mensaje_resumen += f"• UpID inválido\n"
            mensaje_resumen += f"• Error de conexión/proxy\n"
            
    await msg.edit(mensaje_resumen)
    
    # Enviar archivo de resumen
    try:
        await bot.send_document(
            msg.chat.id,
            resumen_path,
            caption=f"📋 Resumen de subida: {filename_original}"
        )
    except Exception as e:
        print(f"DEBUG - Error enviando resumen: {e}")
        
    # ===== 6. LIMPIAR TEMPORALES =====
    try:
        limpiar_archivos_temporales(username)
        if os.path.exists(resumen_path):
            os.remove(resumen_path)
    except Exception as e:
        print(f"DEBUG - Error limpiando temporales: {e}")
        
    return exitos > 0  # Retorna True si al menos una subida fue exitosa

#######sube las partes divididas a la revista

async def subir_parte_revistas_mejorado(filepath, filename, host, user, password, upid, 
                                        username, msg, parte_actual, total_partes):
    """Sube una parte individual a revistas - VERSIÓN MEJORADA"""
    print(f"DEBUG - Iniciando subida parte {parte_actual}")
    
    connector = await proxy_manager.get_connector(username, ssl_verify=False)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'es-ES,es;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }
    
    try:
        timeout = aiohttp.ClientTimeout(total=600)
        async with aiohttp.ClientSession(headers=headers, connector=connector, timeout=timeout) as session:
            print(f"DEBUG - Parte {parte_actual}: Obteniendo token CSRF...")
            
            # 1. Obtener página de login
            async with session.get(f"{host}login", timeout=30) as response:
                if response.status != 200:
                    error_msg = f"Error conexión login: HTTP {response.status}"
                    print(f"DEBUG - {error_msg}")
                    await msg.edit(f"❌ Parte {parte_actual}: {error_msg}")
                    return None
                    
                html = await response.text()
                
            # Buscar token CSRF de múltiples formas
            csrf_token = None
            
            # Método 1: Input hidden
            csrf_match = re.search(r'name="csrfToken"\s+value="([^"]+)"', html)
            if csrf_match:
                csrf_token = csrf_match.group(1)
                
            # Método 2: Meta tag
            if not csrf_token:
                meta_match = re.search(r'<meta[^>]+name="csrf-token"[^>]+content="([^"]+)"', html)
                if meta_match:
                    csrf_token = meta_match.group(1)
                    
            # Método 3: JavaScript variable
            if not csrf_token:
                js_match = re.search(r'csrfToken["\']?\s*:\s*["\']([^"\']+)["\']', html)
                if js_match:
                    csrf_token = js_match.group(1)
                    
            if not csrf_token:
                csrf_token = "no-token"
                print(f"DEBUG - Parte {parte_actual}: No se encontró token CSRF, usando placeholder")
                
            print(f"DEBUG - Parte {parte_actual}: Token CSRF: {csrf_token[:20]}...")
            
            # 2. Hacer login
            print(f"DEBUG - Parte {parte_actual}: Iniciando login...")
            
            login_data = {
                'csrfToken': csrf_token,
                'source': '',
                'username': user,
                'password': password,
                'remember': '1'
            }
            
            async with session.post(f"{host}login/signIn", data=login_data, timeout=30) as resp:
                if resp.status not in [200, 302, 303]:
                    error_msg = f"Login falló: HTTP {resp.status}"
                    print(f"DEBUG - {error_msg}")
                    await msg.edit(f"❌ Parte {parte_actual}: {error_msg}")
                    return None
                    
                print(f"DEBUG - Parte {parte_actual}: Login exitoso")
                
            # 3. Verificar sesión
            try:
                async with session.get(f"{host}user/profile", timeout=20, allow_redirects=False) as profile_resp:
                    if profile_resp.status in [302, 401]:
                        print(f"DEBUG - Parte {parte_actual}: Sesión no válida")
                    else:
                        print(f"DEBUG - Parte {parte_actual}: Sesión verificada")
            except:
                pass  # Ignorar errores de verificación
                
            # 4. Configurar progreso
            filesize = os.path.getsize(filepath)
            start_time = time.time()
            
            def progress_callback(current, total):
                if total == 0:
                    return
                    
                elapsed = time.time() - start_time
                if elapsed > 0:
                    speed = current / elapsed
                else:
                    speed = 0
                    
                progress = update_progress_bar(current, total)
                
                # Actualizar solo cada 2 segundos
                if int(time.time() - start_time) % 2 == 0:
                    try:
                        msg.edit(
                            f"⬆️ **Subiendo parte {parte_actual}/{total_partes}**\n\n"
                            f"📁 `{filename}`\n"
                            f"{progress}\n"
                            f"📊 {sizeof_fmt(current)} / {sizeof_fmt(total)}\n"
                            f"⚡ {sizeof_fmt(speed)}/s"
                        )
                    except:
                        pass
                        
            # 5. Leer archivo con progreso
            reader = ProgressReader(filepath, lambda c, t, s, n: progress_callback(c, t))
            
            # 6. Preparar datos para subida
            form_data = aiohttp.FormData()
            form_data.add_field("fileStage", "2")
            form_data.add_field("name[es_ES]", filename)
            form_data.add_field("name[en_US]", filename)
            form_data.add_field("file", reader, filename=filename, content_type='image/jpeg')
            
            upload_headers = headers.copy()
            upload_headers["X-Csrf-Token"] = csrf_token
            upload_headers["X-Requested-With"] = "XMLHttpRequest"
            upload_headers["Referer"] = f"{host}submissions/{upid}"
            
            upload_url = f"{host}api/v1/submissions/{upid}/files"
            
            print(f"DEBUG - Parte {parte_actual}: Subiendo a {upload_url}")
            
            # 7. Subir archivo
            async with session.post(upload_url, data=form_data, headers=upload_headers, timeout=300) as upload_resp:
                print(f"DEBUG - Parte {parte_actual}: Respuesta HTTP {upload_resp.status}")
                
                response_text = await upload_resp.text()
                
                if upload_resp.status == 200:
                    print(f"DEBUG - Parte {parte_actual}: Subida exitosa, analizando respuesta...")
                    
                    # Intentar extraer URL de diferentes formas
                    url_descarga = None
                    
                    # Método 1: JSON parsing
                    try:
                        data = json.loads(response_text)
                        print(f"DEBUG - Parte {parte_actual}: Respuesta JSON: {json.dumps(data, indent=2)[:200]}...")
                        
                        if 'url' in data:
                            url_descarga = data['url']
                        elif 'data' in data and 'url' in data['data']:
                            url_descarga = data['data']['url']
                        elif 'fileUrl' in data:
                            url_descarga = data['fileUrl']
                        elif 'downloadUrl' in data:
                            url_descarga = data['downloadUrl']
                            
                    except json.JSONDecodeError:
                        print(f"DEBUG - Parte {parte_actual}: No es JSON, buscando URLs en texto")
                        
                    # Método 2: Buscar URLs en texto
                    if not url_descarga:
                        url_patterns = [
                            r'"url"\s*:\s*"([^"]+)"',
                            r'"downloadUrl"\s*:\s*"([^"]+)"',
                            r'"fileUrl"\s*:\s*"([^"]+)"',
                            r'https?://[^\s"\']+/download/[^\s"\']+',
                            r'https?://[^\s"\']+/files/[^\s"\']+',
                            r'https?://[^\s"\']+/api/[^\s"\']+'
                        ]
                        
                        for pattern in url_patterns:
                            matches = re.findall(pattern, response_text)
                            if matches:
                                url_descarga = matches[0]
                                break
                                
                    # Método 3: Construir URL manualmente si tenemos ID
                    if not url_descarga:
                        # Intentar extraer fileId
                        file_id_match = re.search(r'"id"\s*:\s*(\d+)', response_text)
                        if file_id_match:
                            file_id = file_id_match.group(1)
                            url_descarga = f"{host}api/v1/submissions/{upid}/files/{file_id}/download"
                            
                    # Método 4: URL genérica
                    if not url_descarga:
                        url_descarga = f"{host}submissions/{upid}/files"
                        
                    # Asegurar que la URL sea completa
                    if url_descarga and not url_descarga.startswith(('http://', 'https://')):
                        url_descarga = host.rstrip('/') + url_descarga
                        
                    print(f"DEBUG - Parte {parte_actual}: URL encontrada: {url_descarga}")
                    return url_descarga
                    
                else:
                    error_msg = f"Error HTTP {upload_resp.status}: {response_text[:200]}"
                    print(f"DEBUG - {error_msg}")
                    await msg.edit(f"❌ Parte {parte_actual}: Error {upload_resp.status}")
                    return None
                    
    except asyncio.TimeoutError:
        error_msg = f"Timeout en parte {parte_actual}"
        print(f"DEBUG - {error_msg}")
        await msg.edit(f"❌ Parte {parte_actual}: Timeout")
        return None
    except aiohttp.ClientError as e:
        error_msg = f"Error de conexión: {e}"
        print(f"DEBUG - {error_msg}")
        await msg.edit(f"❌ Parte {parte_actual}: Error conexión")
        return None
    except Exception as e:
        error_msg = f"Error inesperado: {e}"
        print(f"DEBUG - {error_msg}")
        print(f"DEBUG - Traceback: {traceback.format_exc()}")
        await msg.edit(f"❌ Parte {parte_actual}: Error inesperado")
        return None

@bot.on_message(filters.command("up") & filters.private)
async def upload_file(client: Client, message: Message):
    username = message.from_user.username
    if not await verificar_usuario(username):
        return
        
    config = user_configs.get(username, {})
    if not config.get("revistas_host"):
        await message.reply("❌ **Configura revistas con** `/rv`")
        return
        
    if active_uploads.get(username, False):
        await message.reply("⚠️ **Ya hay una subida en proceso**")
        return
        
    try:
        partes = message.text.split()
        if len(partes) < 2:
            await message.reply("❌ **Especifica el número del archivo**")
            return
            
        idx = int(partes[1])
        current_dir = user_roots.get(username, f"downloads/{username}")
        items = listar_archivos(current_dir)
        
        if idx < 0 or idx >= len(items):
            await message.reply("❌ **Índice inválido**")
            return
            
        filename = items[idx]
        filepath = os.path.join(current_dir, filename)
        
        if os.path.isdir(filepath):
            await message.reply("❌ **Solo archivos, no carpetas**")
            return
            
        filesize = os.path.getsize(filepath)
        max_size = 500 * 1024 * 1024
        
        if filesize > max_size:
            await message.reply(
                f"❌ **Archivo muy grande**\n\n"
                f"📁 `{filename}`\n"
                f"📦 {sizeof_fmt(filesize)}\n"
                f"📏 Límite: {sizeof_fmt(max_size)}"
            )
            return
            
        active_uploads[username] = True
        
        # Informar que se renombrará a .jpg
        jpg_filename = filename.rsplit('.', 1)[0] + '.jpg'
        msg = await message.reply(
            f"🚀 **Preparando subida:**\n\n"
            f"📁 Original: `{filename}`\n"
            f"🔄 Se subirá como: `{jpg_filename}`\n\n"
            f"📦 Tamaño: {sizeof_fmt(filesize)}"
        )
        
        success = await upload_revistas(filepath, msg, username)
        
        active_uploads[username] = False
        
        if not success:
            await message.reply("❌ **La subida falló**")
            
    except ValueError:
        await message.reply("❌ **El índice debe ser número**")
    except Exception as e:
        active_uploads[username] = False
        await message.reply(f"❌ **Error:**\n`{str(e)[:200]}`")

@bot.on_message(filters.command("cancel") & filters.private)
async def cancel_upload(client: Client, message: Message):
    username = message.from_user.username
    if not await verificar_usuario(username):
        return
        
    if active_uploads.get(username, False):
        active_uploads[username] = False
        await message.reply("🛑 **Subida cancelada**")
    else:
        await message.reply("ℹ️ **No hay subidas activas**")

@bot.on_message(filters.command("debug") & filters.private)
async def debug_cmd(client: Client, message: Message):
    username = message.from_user.username
    if not await verificar_usuario(username):
        return
        
    config = user_configs.get(username, {})
    proxy_stats = proxy_manager.get_stats()
    proxy_info = proxy_manager.get_user_proxy_info(username)
    
    debug_info = f"🔧 **INFORMACIÓN DE DEPURACIÓN**\n\n"
    debug_info += f"👤 **Usuario:** `{username}`\n"
    debug_info += f"📁 **Directorio:** `{user_roots.get(username)}`\n"
    debug_info += f"📂 **Archivos en cola:** {len(user_files.get(username, []))}\n"
    debug_info += f"🔄 **Subida activa:** {'Sí' if active_uploads.get(username, False) else 'No'}\n\n"
    
    if config:
        debug_info += "**⚙️ CONFIGURACIÓN REVISTAS:**\n"
        debug_info += f"• **Host:** `{config.get('revistas_host', 'No')}`\n"
        debug_info += f"• **Usuario:** `{config.get('revistas_user', 'No')}`\n"
        debug_info += f"• **UpID:** `{config.get('revistas_upid', 'No')}`\n"
        debug_info += f"• **Zips:** `{config.get('revistas_zips', 'No')} MB`\n"
        debug_info += f"• **Modo:** `{config.get('revistas_mode', 'No')}`\n"
    else:
        debug_info += "❌ **No hay configuración**\n"
        
    debug_info += f"\n**🔧 PROXIES:**\n"
    debug_info += f"• **Disponibles:** {proxy_stats['total_proxies']}\n"
    debug_info += f"• **Tu proxy:** `{proxy_info['personal_proxy']}`\n"
    debug_info += f"• **Activado:** {'Sí' if proxy_info['use_proxy'] else 'No'}\n"
    debug_info += f"• **Última actualización:** {proxy_stats['last_fetch']}\n"
    
    total, used, free = shutil.disk_usage(".")
    debug_info += f"\n**💻 SISTEMA:**\n"
    debug_info += f"• **Espacio total:** {sizeof_fmt(total)}\n"
    debug_info += f"• **Espacio usado:** {sizeof_fmt(used)}\n"
    debug_info += f"• **Espacio libre:** {sizeof_fmt(free)}"
    
    await message.reply(debug_info)

# ===== INICIO DEL BOT =====
async def inicializar_proxies():
    """Inicializa el sistema de proxies al arrancar"""
    print("🔧 Inicializando sistema de proxies...")
    await proxy_manager.fetch_proxies()

def main():
    print("=" * 60)
    print("🤖 BOT DE SUBIDA A REVISTAS")
    print("=" * 60)
    
    if API_ID == 1234567:
        print("❌ ERROR: Configura API_ID")
        exit(1)
        
    if not os.path.exists("downloads"):
        os.makedirs("downloads", exist_ok=True)
        print("📁 Carpeta 'downloads' creada")
        
    # Cargar configuraciones guardadas
    config_files = [f for f in os.listdir(".") if f.startswith("config_") and f.endswith(".json")]
    for config_file in config_files:
        try:
            username = config_file[7:-5]
            if username:
                with open(config_file, "r") as f:
                    user_configs[username] = loads(f.read())
                    print(f"✅ Configuración cargada: {username}")
        except Exception as e:
            print(f"❌ Error cargando {config_file}: {e}")
            
    print(f"👥 Usuarios autorizados: {USUARIOS_AUTORIZADOS}")
    
    # Inicializar proxies
    loop = asyncio.get_event_loop()
    loop.run_until_complete(inicializar_proxies())
    
    print("🚀 Iniciando bot...")
    print("=" * 60)
    print("📝 **COMANDOS DISPONIBLES:**")
    print("• /start - Iniciar bot")
    print("• /rv - Configurar revistas")
    print("• /ls - Listar archivos")
    print("• /up N - Subir archivo")
    print("• /proxies - Gestionar proxies")
    print("=" * 60)
    
    try:
        bot.run()
    except KeyboardInterrupt:
        print("\n👋 Bot detenido")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    # Instalar dependencia para proxies si no está
    try:
        import aiohttp_socks
    except ImportError:
        print("📦 Instalando aiohttp_socks...")
        import subprocess
        subprocess.check_call(["pip", "install", "aiohttp_socks"])
        
    main()
