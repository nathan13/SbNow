# Navios na barra — TECON SANTOS, na nuvem (prototipo)

## Objetivo

Publicar a lista de navios na barra do TECON SANTOS em um site responsivo, sem depender de um PC ligado, Pomerado ou navegadores abertos nos dispositivos dos visitantes.

## Importante: limite de acesso ao site de origem

O usuario confirmou que a coleta local com Chromium **visivel** funciona e que com `--headless` houve `Access Denied`. Este projeto usa Chromium em modo **normal**, mas dentro de um *display virtual* no Linux (`xvfb-run`). Assim, nao aparece janela para o visitante nem precisa de PC pessoal. **Isso nao garante acesso a partir do servidor do GitHub**: a origem pode negar acesso por IP, politica de acesso ou outras razoes. Se houver bloqueio, o workflow falha e NAO publica um JSON enganoso. **Nao tente contornar restricoes de acesso.** Nesse caso, solicite acesso autorizado a API ou uma fonte de dados permitida da Santos Brasil.

## Para colocar no ar pelo GitHub (recomendado para o primeiro teste)

1. Tenha uma conta em https://github.com.
2. Crie um repositorio **publico** (por exemplo `navios-tecon-santos`).
3. Carregue **todos** os arquivos e diretorios desta pasta na **raiz** do repositorio. **Inclua `.github/workflows/atualizar-navios.yml`**: esse nome inicia com ponto e pode ficar oculto no Explorador. Uma opcao segura e usar Git ou `git push` para preservar esse diretorio.
4. Abra o repositorio > **Settings** > **Pages** > **Build and deployment** > **Source: GitHub Actions**.
5. Abra **Actions** > workflow **Atualizar navios na barra (TECON SANTOS)** > **Run workflow**.
6. Aguarde o workflow terminar. Se as etapas **Coletar dados publicos** e **Publicar site** ficarem verdes, abra o endereco exibido no ambiente `github-pages`. Exemplo de formato (substitua pelos dados reais): `https://USUARIO.github.io/REPOSITORIO/navios-na-barra.html`.
7. O workflow esta configurado para executar a cada **30 minutos**, com atrasos possiveis conforme a disponibilidade dos executores GitHub. O site verifica atualizacoes do JSON a cada 60 segundos, mas isso NAO significa coletar dados da origem a cada minuto.

Se a etapa de coleta falhar, o painel anterior publicado permanece no ar, com aviso visual quando os dados tiverem mais de 75 minutos. Para diagnostico: na execucao do workflow abra **Artifacts** e baixe `diagnostico-coleta` se existir, alem de ler o log `Consultar Santos Brasil com navegador em tela virtual`.

## No seu site ja existente

Se a coleta no GitHub funcionar, incorpore o painel responsivo com um iframe:

```html
<iframe
  src="https://USUARIO.github.io/REPOSITORIO/navios-na-barra.html"
  title="Navios na barra - TECON SANTOS"
  style="display:block;width:100%;min-height:450px;border:0"
  loading="lazy"></iframe>
```

Substitua `USUARIO` e `REPOSITORIO`.

## Conteudo

- `extrair_navios_barra.py`: coleta com Playwright, seleciona TECON SANTOS (ja padrao) e `Na barra` automaticamente.
- `.github/workflows/atualizar-navios.yml`: executa na nuvem com tela virtual e publica os dados pelo Pages.
- `validar_json.py`: valida dados e evita publicar JSON sem resultados confirmados.
- `site/navios-na-barra.html`: painel responsivo para celular/PC.
- `site/dados/navios_na_barra.json`: criado durante a coleta; nao e enviado preenchido artificialmente.

## Teste local opcional

```powershell
py -m pip install -r requirements.txt
py -m playwright install chromium
py extrair_navios_barra.py
py validar_json.py
py -m http.server 8000 --directory site
```

Visite http://localhost:8000/navios-na-barra.html. O GitHub Pages so sera publicado automaticamente se a coleta real no executor remoto funcionar.

## Se o GitHub bloquear

Nao e um problema do celular ou do seu site: o servidor de coleta nao conseguiu obter permissao para ler a origem. Ha duas opcoes sustentaveis: requisicao autorizada a API oficial ou dados provenientes de uma fonte cuja consulta automatica seja permitida. A requisicao interna `POST /app/_jx/lst.asp?lista=atracacao` encontrada no diagnostico anterior ainda nao foi validada para execucao autonomamente em nuvem.

**Limite conhecido:** o coletor atual nao confirma uma tabela legitimamente vazia: se nao houver navios, ele deixa de publicar novos dados para evitar falsos resultados. Essa situacao exigira aperfeicoar o detector de lista vazia.
