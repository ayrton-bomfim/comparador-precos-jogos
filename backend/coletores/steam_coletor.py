import asyncio
import requests
import json
import re
from datetime import datetime
from .coletor_base import ColetorBase
from lista_jogos import JOGOS_DEMO 

class SteamColetor(ColetorBase):
    """Coletor para Steam usando API oficial + scraping direto"""
    
    def __init__(self):
        super().__init__()
        self.timeout = 30000
        self.url_base = "https://store.steampowered.com"
        self.api_base = "https://store.steampowered.com/api"
        # Cache para evitar scraping repetido
        self._cache_precos = {}
    
    def _formatar_preco(self, valor):
        #Formata o preço corretamente (converte centavos para reais)
        
        # Caso 1: valor é None
        if valor is None:
            return "N/A"  # ← Mudança: retorna "N/A" em vez de None
        
        # Caso 2: valor é número (int ou float)
        if isinstance(valor, (int, float)):
            if valor == 0:
                return "Grátis"
            if valor < 1000:
                return f"R$ {valor:.2f}".replace('.', ',')
            else:
                return f"R$ {valor/100:.2f}".replace('.', ',')
        
        # Caso 3: valor é string
        if isinstance(valor, str):
            # Tenta extrair números
            match = re.search(r'[\d,.]+', valor)
            if match:
                num = match.group().replace('.', '').replace(',', '.')
                try:
                    return f"R$ {float(num):.2f}".replace('.', ',')
                except:
                    pass
            
            # Verifica se é gratuito
            if 'grátis' in valor.lower() or 'free' in valor.lower():
                return "Grátis"
            
            # Se chegou aqui, retorna a string original (sem R$)
            return valor.strip()
        
        # Caso 4: qualquer outro tipo (fallback)
        return "N/A"
    
    async def _scrape_preco_direto(self, jogo_id):
        """Faz scraping direto da página do jogo APENAS quando necessário"""
        # Verifica cache primeiro
        if jogo_id in self._cache_precos:
            return self._cache_precos[jogo_id]
        
        try:
            url = f"https://store.steampowered.com/app/{jogo_id}/"
            playwright = None
            browser = None
            page = None
            
            try:
                playwright, browser, page = await self._abrir_pagina(url)
                
                # Aguarda o preço carregar
                await page.wait_for_selector(".game_purchase_action", timeout=15000)
                
                # Tenta vários seletores de preço
                preco = None
                
                # 1. Tenta preço com desconto
                try:
                    preco = await page.locator(".discount_final_price").text_content()
                except:
                    pass
                
                # 2. Tenta preço normal
                if not preco:
                    try:
                        preco = await page.locator(".game_purchase_price").text_content()
                    except:
                        pass
                
                # 3. Tenta o preço na área de compra
                if not preco:
                    try:
                        preco = await page.locator(".game_purchase_action .price").text_content()
                    except:
                        pass
                
                # 4. Verifica se é gratuito
                if not preco:
                    try:
                        botao = await page.locator(".game_purchase_action .btn_add_to_cart").text_content()
                        if botao and ("Jogar" in botao or "Play" in botao or "Instalar" in botao):
                            preco = "Grátis"
                    except:
                        pass
                
                # 5. Último recurso: verificar se tem "Free" em algum lugar
                if not preco:
                    try:
                        html = await page.content()
                        if "Grátis" in html or "Free" in html:
                            preco = "Grátis"
                    except:
                        pass
                
                resultado = preco.strip() if preco else "N/A"
                self._cache_precos[jogo_id] = resultado
                return resultado
                
            finally:
                if page:
                    await page.close()
                if browser:
                    await browser.close()
                if playwright:
                    await playwright.stop()
                    
        except Exception as e:
            print(f"   ⚠️ Scraping falhou: {e}")
            return "N/A"
    
    async def coletar_jogo(self, jogo_id):
    
        # Coleta um jogo específico usando a API da Steam.
        # Retorna SEMPRE um dicionário com os dados ou com uma chave 'erro'.
       
    
        print(f"🔍 Buscando jogo na Steam: {jogo_id}")

        # Define um dicionário de erro padrão
        erro_padrao = {"plataforma": "Steam", "erro": "Erro desconhecido"}

        try:
            url = f"{self.api_base}/appdetails?appids={jogo_id}&l=portuguese&cc=br"
            response = requests.get(url, timeout=15)
            response.raise_for_status()  # Levanta exceção para códigos HTTP de erro (4xx, 5xx)
            data = response.json()

            # --- VERIFICAÇÃO ROBUSTA DA RESPOSTA ---
            # 1. Verifica se a chave do jogo existe
            if str(jogo_id) not in data:
                print(f"   ⚠️ Jogo {jogo_id} não encontrado na resposta da API.")
                return {"plataforma": "Steam", "erro": "Jogo não encontrado na API"}

            app_data_bruto = data[str(jogo_id)]

            # 2. Verifica se 'success' é True e se 'data' existe
            if not app_data_bruto or not app_data_bruto.get('success', False):
                print(f"   ⚠️ Jogo {jogo_id} não encontrado (success=False ou dados vazios).")
                return {"plataforma": "Steam", "erro": "Jogo não encontrado"}

            app_data = app_data_bruto.get('data')
            if not app_data:
                print(f"   ⚠️ Jogo {jogo_id} não possui dados (data vazio).")
                return {"plataforma": "Steam", "erro": "Dados do jogo vazios"}

            # --- EXTRAÇÃO DE DADOS COM FALLBACKS ---
            preco_data = app_data.get('price_overview', {})
            is_free = app_data.get('is_free', False)

            preco_final = "N/A"
            preco_initial = "N/A"
            desconto = "0%"

            if is_free:
                preco_final = "Grátis"
                preco_initial = "Grátis"
            elif preco_data:
                # Usa a formatação que já deve tratar None
                preco_final = self._formatar_preco(preco_data.get('final'))
                preco_initial = self._formatar_preco(preco_data.get('initial'))
                desconto = f"{preco_data.get('discount_percent', 0)}%"

            # Garante que preco_final/initial nunca sejam None
            if preco_final is None:
                preco_final = "N/A"
            if preco_initial is None:
                preco_initial = "N/A"

            # Monta o dicionário com os dados
            resultado = {
                "plataforma": "Steam",
                "id": str(jogo_id),
                "nome": app_data.get('name', 'N/A'),
                "preco": preco_final,
                "preco_sem_desconto": preco_initial,
                "desconto": desconto,
                "descricao": (
                    app_data.get('about_the_game', '') or
                    app_data.get('detailed_description', '') or
                    app_data.get('short_description', '') or
                    'N/A'
                ),
                "url": f"https://store.steampowered.com/app/{jogo_id}/",
                "gratuito": is_free,
                "desenvolvedor": app_data.get('developers', ['N/A'])[0] if app_data.get('developers') else 'N/A',
                "publicadora": app_data.get('publishers', ['N/A'])[0] if app_data.get('publishers') else 'N/A',
                "genero": ', '.join([g['description'] for g in app_data.get('genres', [])]) if app_data.get('genres') else 'N/A',
                "data_lancamento": app_data.get('release_date', {}).get('date', None),
                "url_imagem": app_data.get('header_image', 'N/A'),
            }

            # Avaliação
            if 'metacritic' in app_data:
                resultado['avaliacao'] = f"{app_data['metacritic'].get('score', 'N/A')}/100"
            else:
                resultado['avaliacao'] = "N/A"

            return resultado

        # --- TRATAMENTO DE EXCEÇÕES ESPECÍFICAS ---
        except requests.exceptions.Timeout:
            print(f"   ⏰ Timeout para o jogo {jogo_id}")
            return {"plataforma": "Steam", "erro": "Timeout"}
        except requests.exceptions.RequestException as e:
            print(f"   ⚠️ Erro de conexão: {e}")
            return {"plataforma": "Steam", "erro": f"Erro de conexão: {e}"}
        except Exception as e:
            print(f"   ❌ Erro inesperado ao buscar jogo {jogo_id}: {e}")
            return {"plataforma": "Steam", "erro": f"Erro inesperado: {e}"}
    
    async def coletar_precos(self):
        """Coleta jogos populares usando a API da Steam"""
        print("🎮 Coletando dados da Steam...")
        
        try:
            jogos_populares = JOGOS_DEMO

            resultados = []
            for jogo_id in jogos_populares:
                jogo_data = await self.coletar_jogo(jogo_id)
                if 'erro' not in jogo_data and jogo_data.get('nome') != 'N/A':
                    resultados.append(jogo_data)

                await asyncio.sleep(1.5)  # Espera 1 segundo entre cada requisição
            
            return {"plataforma": "Steam", "jogos": resultados}
            
        except Exception as e:
            print(f"❌ Erro na coleta da Steam: {e}")
            return {"plataforma": "Steam", "erro": str(e)}
    
    async def coletar_promocoes(self):
        """Coleta jogos em promoção usando a API da Steam"""
        print("🔥 Coletando promoções da Steam...")
        
        try:
            url = "https://store.steampowered.com/api/featuredcategories?l=portuguese&cc=br"
            response = requests.get(url)
            data = response.json()
            
            promocoes = []
            
            featured = data.get('featured', {}).get('items', [])
            if not featured:
                featured = data.get('specials', {}).get('items', [])
            
            for jogo in featured[:10]:
                if jogo.get('id'):
                    jogo_id = jogo['id']
                    detalhes = await self.coletar_jogo(jogo_id)
                    if 'erro' not in detalhes:
                        promocoes.append({
                            "nome": detalhes.get('nome', 'N/A'),
                            "preco_promocional": detalhes.get('preco', 'N/A'),
                            "desconto": detalhes.get('desconto', 'N/A'),
                            "url": f"https://store.steampowered.com/app/{jogo_id}/"
                        })
            
            return {"plataforma": "Steam", "promocoes": promocoes, "total": len(promocoes)}
            
        except Exception as e:
            print(f"❌ Erro ao coletar promoções da Steam: {e}")
            return {"plataforma": "Steam", "erro": str(e)}


# Função para testar o scraper
async def testar_steam():
    """Função de teste para o scraper da Steam"""
    coletor = SteamColetor()
    
    print("=" * 50)
    print("🧪 TESTANDO SCRAPER DA STEAM")
    print("=" * 50)
    
    # Teste: Coletar jogos em destaque
    print("\n📌 Coletando jogos em destaque...")
    destaques = await coletor.coletar_precos()
    print(f"✅ {len(destaques.get('jogos', []))} jogos coletados")
    if destaques.get('jogos'):
        print("\n   📊 JOGOS COLETADOS:")
        for jogo in destaques['jogos']:
            gratuito = "🎁 GRÁTIS" if jogo.get('gratuito') else ""
            preco = jogo.get('preco', 'N/A')
            desconto = jogo.get('desconto', '0%')
            print(f"   - {jogo['nome']}: {preco} {gratuito} ({desconto})")
    
    print("\n" + "=" * 50)
    print("🎉 TESTE CONCLUÍDO!")
    print("=" * 50)
    
    return destaques


if __name__ == "__main__":
    import asyncio
    asyncio.run(testar_steam())