#!/usr/bin/env python3
"""
proxy_manager.py
Sistema automático de gestión de proxies
"""

import asyncio
import aiohttp
import aiohttp_socks
from time import time
from datetime import datetime
import random
import ssl

class ProxyManager:
    """Gestor automático de proxies para el bot"""
    
    # Fuentes de proxies gratuitos
    PROXY_SOURCES = [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
        "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks5.txt",
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5&timeout=10000&country=all",
        "https://www.proxy-list.download/api/v1/get?type=socks5",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5.txt"
    ]
    
    def __init__(self):
        self.proxies = []  # Lista de proxies funcionando
        self.current_index = 0
        self.last_fetch = 0
        self.proxy_timeout = 10  # Timeout para pruebas
        self.max_proxies = 50    # Máximo de proxies a guardar
        
        # Cache de proxies por usuario
        self.user_proxies = {}
        self.user_settings = {}  # use_proxy por usuario
    
    async def fetch_proxies(self):
        """Obtiene proxies de múltiples fuentes"""
        print("🔄 Buscando proxies funcionales...")
        
        all_proxies = []
        async with aiohttp.ClientSession() as session:
            tasks = []
            for source in self.PROXY_SOURCES:
                task = self._fetch_from_source(session, source)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, list):
                    all_proxies.extend(result)
        
        # Eliminar duplicados
        all_proxies = list(set(all_proxies))
        print(f"📊 Proxies encontrados: {len(all_proxies)}")
        
        # Probar proxies y guardar los que funcionan
        working_proxies = await self._test_proxies_list(all_proxies[:100])  # Probar máximo 100
        
        self.proxies = working_proxies
        self.current_index = 0
        self.last_fetch = time()
        
        print(f"✅ Proxies funcionales: {len(self.proxies)}")
        if self.proxies:
            print(f"📋 Ejemplos: {self.proxies[:3]}")
        
        return len(self.proxies)
    
    async def _fetch_from_source(self, session, source):
        """Obtiene proxies de una fuente específica"""
        try:
            async with session.get(source, timeout=10) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    proxies = []
                    for line in text.strip().split('\n'):
                        line = line.strip()
                        if ':' in line and not line.startswith('#'):
                            parts = line.split(':')
                            if len(parts) == 2 and parts[1].isdigit():
                                proxies.append(f"socks5://{line}")
                    return proxies
        except Exception as e:
            print(f"  ❌ Error en {source}: {e}")
        return []
    
    async def _test_proxies_list(self, proxies_list):
        """Prueba una lista de proxies"""
        working_proxies = []
        tasks = []
        
        for proxy in proxies_list:
            task = self.test_proxy(proxy)
            tasks.append(task)
        
        # Ejecutar pruebas en paralelo
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for proxy, result in zip(proxies_list, results):
            if result is True:  # Proxy funciona
                working_proxies.append(proxy)
                if len(working_proxies) >= self.max_proxies:
                    break
        
        return working_proxies
    
    async def test_proxy(self, proxy_url):
        """Prueba si un proxy funciona"""
        try:
            # Crear contexto SSL sin verificación para pruebas
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp_socks.ProxyConnector.from_url(proxy_url, ssl=ssl_context)
            timeout = aiohttp.ClientTimeout(total=self.proxy_timeout)
            
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                # Probar con un sitio rápido
                async with session.get('http://httpbin.org/ip', timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'origin' in data:
                            return True
        except:
            pass
        return False
    
    def get_proxy_for_user(self, username):
        """Obtiene proxy para un usuario específico"""
        # Si el usuario tiene proxy fijo, usarlo
        if username in self.user_proxies and self.user_proxies[username]:
            return self.user_proxies[username]
        
        # Si no hay proxies, devolver None (sin proxy)
        if not self.proxies:
            return None
        
        # Rotar entre proxies disponibles
        proxy = self.proxies[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.proxies)
        return proxy
    
    def set_user_proxy(self, username, proxy_url):
        """Fija un proxy específico para un usuario"""
        if proxy_url and not proxy_url.startswith(("socks5://", "socks4://", "http://")):
            proxy_url = "socks5://" + proxy_url
        self.user_proxies[username] = proxy_url
    
    def set_user_setting(self, username, setting, value):
        """Configura una opción para el usuario"""
        if username not in self.user_settings:
            self.user_settings[username] = {}
        self.user_settings[username][setting] = value
    
    def get_user_setting(self, username, setting, default=None):
        """Obtiene una configuración del usuario"""
        if username in self.user_settings and setting in self.user_settings[username]:
            return self.user_settings[username][setting]
        return default
    
    async def get_connector(self, username=None, ssl_verify=True):
        """Obtiene un connector aiohttp con proxy configurado"""
        # Configuración SSL
        if ssl_verify:
            ssl_context = None  # Usar SSL normal
        else:
            # Crear contexto SSL sin verificación
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        
        # Verificar si el usuario quiere usar proxy
        use_proxy = self.get_user_setting(username, 'use_proxy', True)
        
        if not use_proxy:
            # Conexión directa
            return aiohttp.TCPConnector(ssl=ssl_context)
        
        # Obtener proxy para el usuario
        proxy_url = self.get_proxy_for_user(username)
        
        if proxy_url:
            try:
                connector = aiohttp_socks.ProxyConnector.from_url(
                    proxy_url, 
                    ssl=ssl_context
                )
                return connector
            except Exception as e:
                print(f"❌ Error con proxy {proxy_url}: {e}")
                # Fallback a conexión directa
                return aiohttp.TCPConnector(ssl=ssl_context)
        
        # Sin proxy disponible
        return aiohttp.TCPConnector(ssl=ssl_context)
    
    def get_stats(self):
        """Obtiene estadísticas del proxy manager"""
        return {
            "total_proxies": len(self.proxies),
            "last_fetch": datetime.fromtimestamp(self.last_fetch).strftime('%H:%M:%S'),
            "user_count": len(self.user_proxies)
        }
    
    def get_user_proxy_info(self, username):
        """Obtiene información de proxy para un usuario"""
        user_proxy = self.user_proxies.get(username)
        use_proxy = self.get_user_setting(username, 'use_proxy', True)
        
        return {
            "personal_proxy": user_proxy if user_proxy else "Auto-rotación",
            "use_proxy": use_proxy,
            "proxies_available": len(self.proxies)
        }

# Instancia global del proxy manager
proxy_manager = ProxyManager()
